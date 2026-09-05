import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rock_arch_broker.broker import Broker
from rock_arch_broker.profiles import ProfileError
from rock_arch_broker.shortcut_keymap import KeymapError, keyboard_symbols
from rock_arch_broker.shortcuts import (
    COMMAND,
    DESCRIPTION,
    MODIFIERS,
    ShortcutError,
    ShortcutManager,
    matching_binds,
    normalize_combo,
    parse_binds,
    render_block,
)


def binding(combo, description="Other action", *, dispatcher="__lua", arg="9", **extra):
    parts = combo.split(" + ")
    fields = {
        "modmask": str(sum(MODIFIERS[mod] for mod in parts[:-1])),
        "submap": "",
        "key": parts[-1],
        "keycode": "0",
        "catchall": "false",
        "description": description,
        "dispatcher": dispatcher,
        "arg": arg,
        **extra,
    }
    return (
        "bindd\n"
        + "".join(f"\t{key}: {value}\n" for key, value in fields.items())
        + "\n"
    )


class FakeHyprland:
    def __init__(self, path):
        self.path = path
        self.stock = binding("SUPER + SPACE", "Launcher") + binding(
            "SUPER + CTRL + R", "Reminder"
        )
        self.active = self.stock
        self.errors = ""
        self.reloads = 0
        self.fail_new_config = False
        self.ignore_reload = False
        self.concurrent_edit = False

    def __call__(self, command):
        if command == "devices":
            return json.dumps(
                {
                    "keyboards": [
                        {
                            "rules": "",
                            "model": "",
                            "layout": "us",
                            "variant": "",
                            "options": "",
                        }
                    ]
                }
            )
        if command == "kb_file":
            return "str: \nset: false\n"
        if command == "binds":
            return self.active
        if command == "configerrors":
            return self.errors
        if command != "reload":
            raise AssertionError(command)
        self.reloads += 1
        if self.ignore_reload:
            return "ok"
        source = self.path.read_text()
        self.errors = (
            "synthetic Lua error"
            if self.fail_new_config and DESCRIPTION in source
            else ""
        )
        if self.concurrent_edit and DESCRIPTION in source:
            self.path.write_text(source + "-- concurrent personal edit\n")
        if not self.errors:
            self.active = self.stock
            for combo, description in re.findall(
                r'^o\.bind\("([^"]+)", "([^"]+)",', source, re.MULTILINE
            ):
                self.active += binding(combo, description)
        return "ok"


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.path = self.directory / "bindings.lua"
        self.original = b'-- Personal config retained byte for byte\no.bind("SUPER + T", "Terminal", "alacritty")\n'
        self.path.write_bytes(self.original)
        self.path.chmod(0o644)
        (self.directory / "hyprland.lua").write_text('require("hypr.bindings")\n')
        self.hypr = FakeHyprland(self.path)
        self.hypr("reload")
        self.hypr.reloads = 0
        self.manager = ShortcutManager(self.directory, self.hypr, installed=True)
        self.sleep = patch("rock_arch_broker.shortcuts.time.sleep")
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def status(self, combo=""):
        return self.manager.request("shortcut_status", combo=combo)

    def change(self, operation="shortcut_install", combo="SUPER + R"):
        status = self.status(combo)
        return self.manager.request(
            operation, combo=combo, revision=status.get("revision"), confirmed=True
        )

    def test_add_change_remove_preserves_personal_file_and_backups(self):
        self.assertEqual(self.status()["state"], "available")
        installed = self.change()
        self.assertTrue(installed["saved"])
        self.assertTrue(installed["managed"])
        self.assertTrue(installed["currentActive"])
        self.assertEqual(
            self.path.read_bytes(), self.original + render_block("SUPER + R").encode()
        )
        changed = self.change(combo="Super+Shift+R")
        self.assertEqual(changed["currentCombo"], "SUPER + SHIFT + R")
        self.assertEqual(self.status("SUPER + R")["state"], "available")
        removed = self.change("shortcut_remove", "SUPER + SHIFT + R")
        self.assertTrue(removed["saved"])
        self.assertFalse(removed["managed"])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o644)
        backups = list(self.directory.glob(".rock-arch-shortcut-backup-*.lua"))
        self.assertEqual(len(backups), 3)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in backups))
        self.assertIn(self.original, [path.read_bytes() for path in backups])
        self.assertEqual(self.hypr.reloads, 3)

    def test_no_trailing_newline_is_preserved_after_removal(self):
        self.path.write_bytes(self.original.rstrip())
        original = self.path.read_bytes()
        self.change()
        self.change("shortcut_remove")
        self.assertEqual(self.path.read_bytes(), original)

    def test_existing_manual_binding_is_recognized_and_never_adopted(self):
        self.path.write_text(
            self.original.decode()
            + f'hl.unbind("SUPER + R")\no.bind("SUPER + R", "Rock Arch", "{COMMAND}")\n'
        )
        self.hypr("reload")
        original = self.path.read_bytes()
        status = self.status()
        self.assertEqual(status["state"], "configured")
        self.assertFalse(status["managed"])
        self.assertEqual(self.change()["state"], "configured")
        self.assertEqual(self.change("shortcut_remove")["error"], "not_managed")
        self.assertEqual(self.change(combo="SUPER + SHIFT + R")["error"], "not_managed")
        self.assertEqual(self.path.read_bytes(), original)

    def test_description_alone_does_not_identify_rock_arch(self):
        self.hypr.active += binding("SUPER + R", "Rock Arch")
        self.assertEqual(self.status()["state"], "conflict")
        self.assertEqual(self.change()["error"], "shortcut_conflict")

    def test_workspace_physical_keys_do_not_conflict_with_unrelated_letters(self):
        self.hypr.active += binding("SUPER + 1", "Workspace 1", key="SUPER + code:10")
        self.assertEqual(self.status("SUPER + R")["state"], "available")
        self.assertEqual(self.status("SUPER + 1")["state"], "conflict")

    def test_xkb_checks_all_configured_layouts_and_rejects_unknown_layouts(self):
        raw = json.dumps(
            {
                "keyboards": [
                    {
                        "rules": "",
                        "model": "",
                        "layout": "us,de",
                        "variant": "",
                        "options": "",
                    }
                ]
            }
        )
        symbols = keyboard_symbols(raw, {10, 27, 29})
        self.assertIn("1", symbols[10])
        self.assertIn("R", symbols[27])
        self.assertTrue({"Y", "Z"} <= symbols[29])
        for invalid in [
            "{}",
            "[]",
            raw.replace("us,de", "rock_arch_nonexistent_layout"),
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(KeymapError):
                keyboard_symbols(invalid, {27})

    def test_conflict_and_reminder_are_not_overwritten(self):
        status = self.status("SUPER + CTRL + R")
        self.assertEqual(status["state"], "conflict")
        self.assertEqual(status["conflict"], "Reminder")
        self.assertEqual(
            self.change(combo="SUPER + CTRL + R")["error"], "shortcut_conflict"
        )
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.hypr.reloads, 0)

    def test_save_rechecks_both_active_and_file_changes(self):
        for change_file in [False, True]:
            with self.subTest(change_file=change_file):
                status = self.status()
                if change_file:
                    self.path.write_bytes(self.original + b"-- new edit\n")
                else:
                    self.hypr.active += binding("SUPER + R", "New assignment")
                before = self.path.read_bytes()
                result = self.manager.request(
                    "shortcut_install",
                    combo="SUPER + R",
                    revision=status["revision"],
                    confirmed=True,
                )
                self.assertEqual(result["error"], "config_changed")
                self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.hypr.reloads, 0)

    def test_manual_edits_to_managed_block_are_not_rewritten(self):
        self.change()
        self.path.write_text(self.path.read_text().replace(COMMAND, "other-command"))
        before = self.path.read_bytes()
        self.assertEqual(self.status()["error"], "managed_block_changed")
        self.assertEqual(
            self.change("shortcut_remove")["error"], "managed_block_changed"
        )
        self.assertEqual(self.path.read_bytes(), before)

    def test_duplicate_blocks_are_not_rewritten(self):
        self.path.write_text(render_block("SUPER + R") * 2)
        self.assertEqual(self.change()["error"], "managed_block_changed")

    def test_reload_errors_roll_back_original_bytes(self):
        self.hypr.fail_new_config = True
        result = self.change()
        self.assertEqual(result["error"], "change_rolled_back")
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.hypr.reloads, 2)
        self.assertEqual(self.hypr.errors, "")

    def test_reload_must_activate_binding_before_reporting_success(self):
        self.hypr.ignore_reload = True
        result = self.change()
        self.assertEqual(result["error"], "change_rolled_back")
        self.assertNotIn("saved", result)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_rollback_never_overwrites_a_concurrent_personal_edit(self):
        self.hypr.fail_new_config = True
        self.hypr.concurrent_edit = True
        result = self.change()
        self.assertEqual(result["error"], "rollback_conflict")
        self.assertTrue(
            self.path.read_bytes().endswith(b"-- concurrent personal edit\n")
        )
        self.assertEqual(
            next(self.directory.glob(".rock-arch-shortcut-backup-*.lua")).read_bytes(),
            self.original,
        )

    def test_existing_config_errors_block_changes(self):
        self.hypr.errors = "pre-existing syntax error"
        self.assertFalse(self.status()["editable"])
        self.assertEqual(self.change()["error"], "config_errors")
        self.assertEqual(self.hypr.reloads, 0)

    def test_unsafe_and_unsupported_files_are_read_only(self):
        self.path.chmod(0o666)
        self.assertEqual(self.change()["error"], "unsafe_config")
        self.path.chmod(0o644)
        target = self.directory / "personal.lua"
        self.path.rename(target)
        self.path.symlink_to(target)
        self.assertEqual(self.change()["error"], "unsafe_config")
        self.path.unlink()
        target.rename(self.path)
        (self.directory / "hyprland.lua").write_text("-- custom loader\n")
        self.assertEqual(self.change()["error"], "unsupported_config")
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_source_checkout_and_unconfirmed_requests_cannot_write(self):
        status = self.status()
        result = self.manager.request(
            "shortcut_install", combo="SUPER + R", revision=status["revision"]
        )
        self.assertEqual(result["error"], "confirmation_required")
        self.manager.installed = False
        self.assertEqual(self.change()["error"], "source_checkout")
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.hypr.reloads, 0)

    def test_key_validation_and_modifier_normalization(self):
        self.assertEqual(normalize_combo("shift + super + r"), "SUPER + SHIFT + R")
        for value in [
            None,
            {},
            "R",
            "SUPER+SUPER+R",
            "SUPER+R;exec bad",
            "SUPER+F13",
            "SUPER+R\no.bind()",
            "SUPER+CTRL+",
            "SUPER+code:20",
        ]:
            with self.subTest(value=value), self.assertRaises(ShortcutError):
                normalize_combo(value)
        for value in ["super+1", "super+F12", "super+alt+ctrl+shift+F1"]:
            self.assertTrue(normalize_combo(value).startswith("SUPER + "))

    def test_bind_parser_handles_quoted_descriptions_submaps_codes_and_duplicates(self):
        for extra in [
            {"submap": "resize"},
            {"keycode": "27"},
            {"catchall": "true"},
            {"key": "SUPER + code:27"},
        ]:
            with self.subTest(extra=extra):
                self.hypr.active = self.hypr.stock + binding(
                    "SUPER + R", 'An "action"', **extra
                )
                self.assertEqual(self.status()["state"], "conflict")
        data = parse_binds(binding("SUPER + R") * 2)
        self.assertEqual(len(matching_binds(data, "SUPER + R")), 2)
        for output in ["", "could not connect", "bindd\n\tmodmask: invalid\n"]:
            with self.subTest(output=output), self.assertRaises(ShortcutError):
                parse_binds(output)

    def test_broker_routes_shortcut_errors_without_changing_onboarding(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.directory)}):
            broker = Broker(
                self.directory / "context",
                instance_file=self.directory / "instance.json",
                shortcuts=self.manager,
            )
        response = broker.handle({"op": "shortcut_install", "combo": "SUPER + R"})
        self.assertTrue(response["ok"])
        self.assertEqual(response["shortcut"]["error"], "confirmation_required")
        response = broker.handle({"op": "shortcut_status"})
        self.assertEqual(response["shortcut"]["state"], "available")
        with patch.object(
            self.manager,
            "request",
            side_effect=AssertionError("preview must not inspect host"),
        ):
            broker._developer_mode = True
            broker.handle({"op": "set_context", "context": "DEV"})
            for operation in ["shortcut_status", "shortcut_install", "shortcut_remove"]:
                response = broker.handle({"op": operation, "confirmed": True})
                self.assertEqual(response["shortcut"]["error"], "preview_mode")

    def test_broker_persists_menu_icon_before_removing_shortcut(self):
        broker = Broker(
            self.directory / "context",
            instance_file=self.directory / "instance.json",
            shortcuts=self.manager,
        )
        broker._profile_store.update_preferences({"showMenuBar": False})
        self.change()
        status = self.status()
        request = {
            "op": "shortcut_remove",
            "combo": "SUPER + R",
            "revision": status["revision"],
            "confirmed": True,
        }
        with patch.object(
            broker._profile_store,
            "update_preferences",
            side_effect=ProfileError("synthetic_failure"),
        ):
            response = broker.handle(request)
        self.assertEqual(response["shortcut"]["error"], "icon_restore_failed")
        self.assertIn(DESCRIPTION.encode(), self.path.read_bytes())
        response = broker.handle(request)
        self.assertTrue(response["shortcut"]["saved"])
        self.assertTrue(broker._profile_store.preferences()["showMenuBar"])
        self.assertEqual(self.path.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
