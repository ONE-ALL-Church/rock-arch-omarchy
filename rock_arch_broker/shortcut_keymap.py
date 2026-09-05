"""Resolve physical Hyprland bindings with the keyboards' reported XKB layouts."""

from __future__ import annotations

import ctypes as c
import json
from typing import Any


class KeymapError(Exception):
    pass


class RuleNames(c.Structure):
    _fields_ = [
        (name, c.c_char_p)
        for name in ("rules", "model", "layout", "variant", "options")
    ]


def keyboard_symbols(raw: str, codes: set[int]) -> dict[int, set[str]]:
    try:
        devices = json.loads(raw)
        keyboards = devices["keyboards"]
        if not isinstance(keyboards, list) or not 1 <= len(keyboards) <= 128:
            raise KeymapError()
        layouts = set()
        for keyboard in keyboards:
            names = tuple(keyboard[name] for name, _ in RuleNames._fields_)
            if any(not isinstance(value, str) or len(value) > 512 for value in names):
                raise KeymapError()
            if not names[2]:
                raise KeymapError()
            layouts.add(names)
        if len(layouts) > 16 or any(code < 8 or code > 767 for code in codes):
            raise KeymapError()
        # libxkbcommon is already a Hyprland runtime dependency.
        library = c.CDLL("libxkbcommon.so.0")
        return _symbols(library, layouts, codes)
    except (OSError, KeyError, TypeError, ValueError, AttributeError, RecursionError) as error:
        raise KeymapError() from error


def _symbols(
    library: Any, layouts: set[tuple[str, ...]], codes: set[int]
) -> dict[int, set[str]]:
    signatures = {
        "xkb_context_new": ([c.c_int], c.c_void_p),
        "xkb_context_unref": ([c.c_void_p], None),
        "xkb_context_set_log_level": ([c.c_void_p, c.c_int], None),
        "xkb_keymap_new_from_names": (
            [c.c_void_p, c.POINTER(RuleNames), c.c_int],
            c.c_void_p,
        ),
        "xkb_keymap_unref": ([c.c_void_p], None),
        "xkb_keymap_num_layouts_for_key": ([c.c_void_p, c.c_uint32], c.c_uint32),
        "xkb_keymap_num_levels_for_key": (
            [c.c_void_p, c.c_uint32, c.c_uint32],
            c.c_uint32,
        ),
        "xkb_keymap_key_get_syms_by_level": (
            [
                c.c_void_p,
                c.c_uint32,
                c.c_uint32,
                c.c_uint32,
                c.POINTER(c.POINTER(c.c_uint32)),
            ],
            c.c_int,
        ),
        "xkb_keysym_get_name": ([c.c_uint32, c.c_char_p, c.c_size_t], c.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(library, name)
        function.argtypes, function.restype = args, result
    context = library.xkb_context_new(0)
    if not context:
        raise KeymapError()
    result: dict[int, set[str]] = {code: set() for code in codes}
    try:
        library.xkb_context_set_log_level(
            context, 10
        )  # Critical only; no device details in logs.
        for values in layouts:
            names = RuleNames(*(value.encode() for value in values))
            keymap = library.xkb_keymap_new_from_names(context, c.byref(names), 0)
            if not keymap:
                raise KeymapError()
            try:
                for code in codes:
                    layout_count = library.xkb_keymap_num_layouts_for_key(keymap, code)
                    if not 1 <= layout_count <= 16:
                        raise KeymapError()
                    for layout in range(layout_count):
                        level_count = library.xkb_keymap_num_levels_for_key(
                            keymap, code, layout
                        )
                        if not 1 <= level_count <= 32:
                            raise KeymapError()
                        for level in range(level_count):
                            symbols = c.POINTER(c.c_uint32)()
                            count = library.xkb_keymap_key_get_syms_by_level(
                                keymap, code, layout, level, c.byref(symbols)
                            )
                            if not 0 <= count <= 16:
                                raise KeymapError()
                            for index in range(count):
                                name = c.create_string_buffer(64)
                                length = library.xkb_keysym_get_name(
                                    symbols[index], name, len(name)
                                )
                                if 0 < length < len(name):
                                    result[code].add(name.value.decode("ascii").upper())
            finally:
                library.xkb_keymap_unref(keymap)
    finally:
        library.xkb_context_unref(context)
    return result
