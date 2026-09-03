import json
import tempfile
import unittest
import urllib.error
from contextlib import contextmanager
from email.message import Message
from pathlib import Path

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

    def post_json(self, origin, path, cookie):
        self.calls.append(("post", origin, path, cookie))
        value = self.responses.get(path, {})
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
        self.assertEqual(
            validate_file_path("/FileContent/theme/hello%20world.lava"),
            "/FileContent/theme/hello%20world.lava",
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
            "api/TriumphTech/Magnus/GetTreeItems/%2e%2e/secrets",
            "api/TriumphTech/Magnus/GetTreeItems/%252e%252e/secrets",
            "api/TriumphTech/Magnus/Delete/root",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(MagnusError):
                validate_tree_path(invalid)
        for invalid in (
            "/FileContent/../secrets",
            "/FileContent/%2e%2e/secrets",
            "/FileContent/%252e%252e/secrets",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(MagnusError):
                validate_file_path(invalid)

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
            adapter.status()["capabilities"],
            [
                "browse",
                "preview",
                "hash",
                "download",
                "copy",
                "open",
                "mobile_app_build",
            ],
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

    def test_switching_accounts_on_one_origin_resets_magnus_access(self):
        adapter = MagnusReadOnlyAdapter(
            FakeCookieProvider(),
            CANONICAL_MAGNUS_SERVER,
            FakeMagnusHttp({MAGNUS_API_PREFIX + "/GetServer": {"ok": True}}),
        )
        adapter.set_profile("first-profile", CANONICAL_MAGNUS_SERVER)
        self.assertTrue(adapter.probe())
        self.assertEqual(adapter.status()["state"], "available")

        adapter.set_profile("second-profile", CANONICAL_MAGNUS_SERVER)
        self.assertEqual(adapter.status()["state"], "unknown")

    def test_tree_descriptors_drive_controlled_capabilities_and_use_opaque_ids(self):
        tree = [
            {
                "DisplayName": "ONE&ALL Mobile",
                "IsFolder": True,
                "Uri": "/api/TriumphTech/Magnus/GetTreeItems/mobileapps/app/14",
                "BuildUri": "/api/TriumphTech/Magnus/Build/mobileapps/14",
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
        description = adapter.describe(browser["items"][0]["safeId"])
        self.assertEqual(description["expires"], "broker_restart")
        self.assertNotIn("path", description)
        self.assertNotIn("url", str(description).lower())
        serialized = json.dumps(browser)
        self.assertNotIn("GetTreeItems", serialized)
        self.assertNotIn("FileContent", serialized)
        self.assertNotIn("attacker.example", serialized)
        self.assertNotIn("Build/mobileapps", serialized)

    def test_only_exact_mobile_app_build_descriptors_are_enabled(self):
        tree = [
            {
                "DisplayName": "App",
                "IsFolder": True,
                "Uri": "/api/TriumphTech/Magnus/GetTreeItems/mobileapps/app/14",
                "BuildUri": "/api/TriumphTech/Magnus/Build/mobileapps/14",
            },
            {
                "DisplayName": "Theme",
                "IsFolder": True,
                "Uri": "/api/TriumphTech/Magnus/GetTreeItems/Themes",
                "BuildUri": "/api/TriumphTech/Magnus/Build/Themes",
            },
            {
                "DisplayName": "Foreign",
                "IsFolder": True,
                "Uri": "/api/TriumphTech/Magnus/GetTreeItems/mobileapps/app/15",
                "BuildUri": "https://attacker.example/api/TriumphTech/Magnus/Build/mobileapps/15",
            },
        ]
        adapter = MagnusReadOnlyAdapter(
            FakeCookieProvider(),
            CANONICAL_MAGNUS_SERVER,
            FakeMagnusHttp({"/" + DEFAULT_TREE_PATH: tree}),
        )

        rows = adapter.browse()["items"]

        self.assertEqual(rows[0]["actions"], ["build"])
        self.assertEqual(rows[1]["actions"], [])
        self.assertEqual(rows[2]["actions"], [])

    def test_generic_uri_is_discriminated_by_folder_type(self):
        tree = [
            {
                "DisplayName": "Theme",
                "IsFolder": True,
                "Uri": "/api/TriumphTech/Magnus/GetTreeItems/Theme",
            },
            {
                "DisplayName": "File.lava",
                "IsFolder": False,
                "Uri": "/api/TriumphTech/Magnus/FileContent/Theme/File.lava",
            },
        ]
        adapter = MagnusReadOnlyAdapter(
            FakeCookieProvider(),
            CANONICAL_MAGNUS_SERVER,
            FakeMagnusHttp({"/" + DEFAULT_TREE_PATH: tree}),
        )

        listed = adapter.list_tree()

        self.assertIn("path", listed[0])
        self.assertNotIn("filePath", listed[0])
        self.assertNotIn("path", listed[1])
        self.assertEqual(listed[1]["filePath"], "/FileContent/Theme/File.lava")
        self.assertEqual(
            [item["kind"] for item in adapter.browse()["items"]],
            ["folder", "file"],
        )

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
        binary = adapter.preview(safe_id)
        self.assertFalse(binary["previewAvailable"])
        self.assertEqual(binary["content"], "")
        self.assertEqual(binary["actions"], ["download", "copyHash"])

    def test_download_copy_and_remote_view_are_bounded_and_private(self):
        tree = [
            {
                "DisplayName": "mobile.json",
                "IsFolder": False,
                "FileContentUri": "/api/TriumphTech/Magnus/FileContent/mobileapps/14/mobile.json",
                "RemoteViewUri": "/page/123?file=mobile.json",
            }
        ]
        path = MAGNUS_API_PREFIX + "/FileContent/mobileapps/14/mobile.json"
        http = FakeMagnusHttp(
            {"/" + DEFAULT_TREE_PATH: tree, path: b'{"name":"ONE&ALL"}'}
        )
        with tempfile.TemporaryDirectory() as temporary:
            downloads = Path(temporary) / "Downloads"
            adapter = MagnusReadOnlyAdapter(
                FakeCookieProvider(), CANONICAL_MAGNUS_SERVER, http, downloads
            )
            row = adapter.browse()["items"][0]
            self.assertEqual(row["actions"], ["download", "copyHash", "view"])
            safe_id = row["safeId"]
            self.assertEqual(adapter.copy_value(safe_id, "content"), '{"name":"ONE&ALL"}')
            self.assertEqual(len(adapter.copy_value(safe_id, "hash")), 64)
            file_hash = adapter.file_hash(safe_id)
            self.assertEqual(file_hash["title"], "mobile.json")
            self.assertEqual(file_hash["sizeBytes"], 18)
            self.assertEqual(len(file_hash["sha256"]), 64)
            first = adapter.download(safe_id)
            second = adapter.download(safe_id)
            self.assertEqual(first["savedAs"], "mobile.json")
            self.assertEqual(second["savedAs"], "mobile (1).json")
            self.assertEqual((downloads / "mobile.json").read_bytes(), b'{"name":"ONE&ALL"}')
            self.assertEqual((downloads / "mobile.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                adapter.view_target(safe_id).url,
                CANONICAL_MAGNUS_SERVER + "/page/123?file=mobile.json",
            )
            self.assertNotIn(str(downloads), json.dumps(first))

    def test_mobile_app_build_posts_descriptor_uri_and_returns_repeat_target(self):
        tree = [
            {
                "DisplayName": "ONE&ALL Mobile",
                "IsFolder": True,
                "Uri": "/api/TriumphTech/Magnus/GetTreeItems/mobileapps/app/14",
                "BuildUri": "/api/TriumphTech/Magnus/Build/mobileapps/14",
            }
        ]
        build_path = "/api/TriumphTech/Magnus/Build/mobileapps/14"
        http = FakeMagnusHttp(
            {
                "/" + DEFAULT_TREE_PATH: tree,
                build_path: {
                    "ActionSuccessful": True,
                    "ResponseMessage": "Build queued.",
                },
            }
        )
        adapter = MagnusReadOnlyAdapter(
            FakeCookieProvider(), CANONICAL_MAGNUS_SERVER, http
        )
        safe_id = adapter.browse()["items"][0]["safeId"]

        outcome = adapter.build(safe_id)

        self.assertEqual(outcome.public_dict(), {"title": "ONE&ALL Mobile", "message": "Build queued."})
        self.assertEqual(outcome.target.kind, "Magnus Build")
        self.assertEqual(outcome.target.url, CANONICAL_MAGNUS_SERVER + build_path)
        self.assertEqual(http.calls[-1][0], "post")
        repeated = adapter.build_recent(outcome.target.url, outcome.title)
        self.assertEqual(repeated.target.url, outcome.target.url)
        with self.assertRaisesRegex(MagnusError, "not_allowed"):
            adapter.build_recent(
                CANONICAL_MAGNUS_SERVER + "/api/TriumphTech/Magnus/Build/Themes",
                "Theme",
            )

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
                    "https://rock.example", 403, "Forbidden", Message(), None
                )
            )
        )
        with self.assertRaises(MagnusUnavailableError):
            denied.get_json(
                CANONICAL_MAGNUS_SERVER,
                MAGNUS_API_PREFIX + "/GetServer",
                ".ROCK=test-session",
            )

        post_opener = FakeOpener(b'{"ActionSuccessful":true}')
        post_client = MagnusHttpClient(post_opener)
        post_client.post_json(
            CANONICAL_MAGNUS_SERVER,
            "/api/TriumphTech/Magnus/Build/mobileapps/14",
            ".ROCK=test-session",
        )
        post_request, _ = post_opener.calls[0]
        self.assertEqual(post_request.get_method(), "POST")
        self.assertEqual(post_request.data, b"")

    def test_http_client_rejects_unregistered_routes_before_network_access(self):
        opener = FakeOpener()
        client = MagnusHttpClient(opener)
        for path in (
            "/api/TriumphTech/Magnus/Delete/root",
            "/api/TriumphTech/Magnus/GetTreeItems/%252e%252e/secrets",
            "/api/People",
        ):
            with self.subTest(path=path), self.assertRaises(MagnusError):
                client.get_json(
                    CANONICAL_MAGNUS_SERVER, path, ".ROCK=test-session"
                )
        with self.assertRaises(MagnusError):
            client.post_json(
                CANONICAL_MAGNUS_SERVER,
                "/api/TriumphTech/Magnus/Build/Themes",
                ".ROCK=test-session",
            )
        self.assertEqual(opener.calls, [])

    def test_http_client_reports_deep_json_as_a_stable_failure(self):
        payload = b"[" * 100_000 + b"]" * 100_000
        client = MagnusHttpClient(FakeOpener(payload))
        with self.assertRaisesRegex(MagnusError, "invalid_magnus_response"):
            client.get_json(
                CANONICAL_MAGNUS_SERVER,
                MAGNUS_API_PREFIX + "/GetServer",
                ".ROCK=test-session",
            )

    def test_file_mutation_methods_are_not_exposed(self):
        adapter = MagnusReadOnlyAdapter(FakeCookieProvider(), CANONICAL_MAGNUS_SERVER)
        for name in ("write_file", "delete_resource", "create_file", "create_folder", "upload_files"):
            self.assertFalse(hasattr(adapter, name), name)


if __name__ == "__main__":
    unittest.main()
