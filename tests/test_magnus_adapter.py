import json
import unittest
import urllib.error
from contextlib import contextmanager

from rock_lens_broker.magnus_adapter import (
    CANONICAL_MAGNUS_SERVER,
    DEFAULT_TREE_PATH,
    MAGNUS_API_PREFIX,
    MAX_FILE_BYTES,
    MagnusError,
    MagnusHttpClient,
    MagnusReadOnlyAdapter,
    MagnusUnavailableError,
    validate_file_path,
    validate_magnus_server,
    validate_tree_path,
)


class FakeCookieProvider:
    def __init__(self, configured=True):
        self.configured = configured
        self.invalidated = False

    def status(self):
        return {"configured": self.configured}

    @contextmanager
    def authenticated_cookie(self):
        if not self.configured:
            raise MagnusError("rock_login_required")
        yield ".ROCK=test-session"

    def invalidate_authenticated_cookie(self):
        self.invalidated = True


class FakeMagnusHttp:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def get_json(self, origin, path, cookie):
        self.calls.append(("json", origin, path, cookie))
        value = self.responses.get(path, [])
        if isinstance(value, Exception):
            raise value
        return value

    def get_bytes(self, origin, path, cookie):
        self.calls.append(("bytes", origin, path, cookie))
        value = self.responses.get(path, b"")
        if isinstance(value, Exception):
            raise value
        return value


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, maximum):
        return self.payload[:maximum]


class FakeOpener:
    def __init__(self, payload=b"{}", failure=None):
        self.payload = payload
        self.failure = failure
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.failure:
            raise self.failure
        return FakeResponse(self.payload)


class MagnusAdapterTests(unittest.TestCase):
    def test_server_and_paths_are_strictly_same_origin(self):
        self.assertEqual(
            validate_magnus_server(CANONICAL_MAGNUS_SERVER + "/"),
            CANONICAL_MAGNUS_SERVER,
        )
        self.assertEqual(
            validate_magnus_server("rock.example.org"), "https://rock.example.org"
        )
        self.assertEqual(
            validate_tree_path(DEFAULT_TREE_PATH), DEFAULT_TREE_PATH
        )
        self.assertEqual(
            validate_file_path(
                "/api/TriumphTech/Magnus/FileContent/block-handler/5/content.lava"
            ),
            "/FileContent/block-handler/5/content.lava",
        )
        for invalid in (
            "http://rock.example.org",
            "https://user:pass@rock.example.org",
            "https://rock.example.org/api",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(MagnusError):
                validate_magnus_server(invalid)
        for invalid in (
            "https://attacker.example/tree",
            "api/TriumphTech/Magnus/GetTreeItems/../secrets",
            "api/TriumphTech/Magnus/Delete/root",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(MagnusError):
                validate_tree_path(invalid)
        with self.assertRaises(MagnusError):
            validate_file_path("/FileContent/../secrets")

    def test_probe_is_optional_and_distinguishes_missing_access(self):
        provider = FakeCookieProvider()
        available_http = FakeMagnusHttp(
            {MAGNUS_API_PREFIX + "/GetServer": {"DisplayName": "Rock"}}
        )
        adapter = MagnusReadOnlyAdapter(
            provider, CANONICAL_MAGNUS_SERVER, available_http
        )
        self.assertEqual(adapter.status()["state"], "unknown")
        self.assertTrue(adapter.probe())
        self.assertEqual(adapter.status()["state"], "available")
        self.assertEqual(
            adapter.status()["capabilities"], ["browse", "preview", "hash"]
        )

        denied = MagnusReadOnlyAdapter(
            provider,
            CANONICAL_MAGNUS_SERVER,
            FakeMagnusHttp(
                {
                    MAGNUS_API_PREFIX + "/GetServer": MagnusUnavailableError(
                        "magnus_unavailable_for_user"
                    )
                }
            ),
        )
        self.assertFalse(denied.probe())
        self.assertEqual(denied.status()["state"], "unavailable")

    def test_tree_descriptors_drive_read_only_capabilities_and_use_opaque_ids(self):
        tree = [
            {
                "DisplayName": "Themes",
                "IsFolder": True,
                "Uri": "/api/TriumphTech/Magnus/GetTreeItems/Themes",
                "BuildUri": "/api/TriumphTech/Magnus/Build/Themes",
                "DeleteUri": "https://attacker.example/delete",
            },
            {
                "DisplayName": "Site.lava",
                "IsFolder": False,
                "FileContentUri": "/api/TriumphTech/Magnus/FileContent/theme/Site.lava",
            },
        ]
        http = FakeMagnusHttp({"/" + DEFAULT_TREE_PATH: tree})
        adapter = MagnusReadOnlyAdapter(
            FakeCookieProvider(), CANONICAL_MAGNUS_SERVER, http
        )
        listed = adapter.list_tree()
        self.assertEqual(listed[0]["actions"], ["build"])
        self.assertNotIn("deleteUri", listed[0])
        self.assertEqual(listed[1]["filePath"], "/FileContent/theme/Site.lava")

        browser = adapter.browse()
        self.assertEqual(len(browser["items"]), 2)
        self.assertTrue(all(row["safeId"].startswith("magnus-") for row in browser["items"]))
        serialized = json.dumps(browser)
        self.assertNotIn("GetTreeItems", serialized)
        self.assertNotIn("FileContent", serialized)
        self.assertNotIn("attacker.example", serialized)

    def test_text_preview_is_bounded_and_includes_a_hash(self):
        tree = [
            {
                "displayName": "content.lava",
                "isFolder": False,
                "filePath": "/FileContent/block-handler/5/content.lava",
            }
        ]
        path = MAGNUS_API_PREFIX + "/FileContent/block-handler/5/content.lava"
        http = FakeMagnusHttp(
            {"/" + DEFAULT_TREE_PATH: tree, path: b"Hello {{ Person.NickName }}"}
        )
        adapter = MagnusReadOnlyAdapter(
            FakeCookieProvider(), CANONICAL_MAGNUS_SERVER, http
        )
        safe_id = adapter.browse()["items"][0]["safeId"]
        preview = adapter.preview(safe_id)
        self.assertEqual(preview["content"], "Hello {{ Person.NickName }}")
        self.assertEqual(len(preview["sha256"]), 64)

        http.responses[path] = b"\x00binary"
        with self.assertRaisesRegex(MagnusError, "preview_unavailable"):
            adapter.preview(safe_id)

    def test_http_client_bounds_responses_and_never_follows_action_urls(self):
        opener = FakeOpener(b"x" * (MAX_FILE_BYTES + 1))
        client = MagnusHttpClient(opener)
        with self.assertRaisesRegex(MagnusError, "out_of_bounds"):
            client.get_bytes(
                CANONICAL_MAGNUS_SERVER,
                MAGNUS_API_PREFIX + "/FileContent/test.txt",
                ".ROCK=test-session",
            )
        request, _ = opener.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Cookie"), ".ROCK=test-session")
        self.assertTrue(request.full_url.startswith(CANONICAL_MAGNUS_SERVER))

        denied = MagnusHttpClient(
            FakeOpener(
                failure=urllib.error.HTTPError(
                    "https://rock.example", 403, "Forbidden", {}, None
                )
            )
        )
        with self.assertRaises(MagnusUnavailableError):
            denied.get_json(
                CANONICAL_MAGNUS_SERVER,
                MAGNUS_API_PREFIX + "/GetServer",
                ".ROCK=test-session",
            )

    def test_no_mutating_methods_are_exposed(self):
        adapter = MagnusReadOnlyAdapter(FakeCookieProvider(), CANONICAL_MAGNUS_SERVER)
        for name in ("write_file", "build", "delete_resource", "create_file", "create_folder", "upload_files"):
            self.assertFalse(hasattr(adapter, name), name)


if __name__ == "__main__":
    unittest.main()
