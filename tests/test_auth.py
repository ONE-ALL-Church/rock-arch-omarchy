import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

from rock_lens_broker.auth import (
    ConfigStore,
    DiscoveryDocument,
    OAuthManager,
    OidcConfig,
    SecretToolStore,
    TokenSet,
    build_authorization_url,
)
from rock_lens_broker.contracts import Context


class FakeSecretStore:
    def __init__(self):
        self.values = {}

    def available(self):
        return True

    def lookup(self, context, kind):
        return self.values.get((context, kind))

    def store(self, context, kind, value):
        self.values[(context, kind)] = value

    def clear(self, context, kind):
        self.values.pop((context, kind), None)


class FakeHttp:
    def __init__(self, issuer="https://rock.example/"):
        self.issuer = issuer
        self.forms = []

    def get_json(self, url):
        self.discovery_url = url
        return {
            "issuer": self.issuer,
            "authorization_endpoint": self.issuer + "Auth/Authorize",
            "token_endpoint": self.issuer + "Auth/Token",
        }

    def post_form(self, url, fields):
        self.forms.append((url, dict(fields)))
        if fields["grant_type"] == "refresh_token":
            return {
                "access_token": "refreshed-access",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        return {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "token_type": "Bearer",
            "expires_in": 3600,
        }


def unused_port():
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "config" / "oidc.json"
        self.config_store = ConfigStore(self.config_path)
        self.secret_store = FakeSecretStore()

    def tearDown(self):
        self.tmp.cleanup()

    def configure(self, port=None):
        config = OidcConfig.from_dict(
            {
                "issuer": "https://rock.example/",
                "client_id": "rock-lens-client",
                "redirect_uri": f"http://127.0.0.1:{port or unused_port()}/oauth/callback",
                "scopes": ["openid", "offline_access"],
            }
        )
        self.config_store.set(Context.DEV, config)
        return config

    def wait_for(self, manager, expected, timeout=3):
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = manager.public_status(Context.DEV, allow_refresh=False)
            if status["state"] == expected:
                return status
            time.sleep(0.02)
        self.fail(f"OAuth state did not become {expected}")

    def test_config_is_owner_only_and_rejects_non_https_or_remote_callback(self):
        config = self.configure()
        self.assertEqual(self.config_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.config_path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.config_store.get(Context.DEV), config)
        with self.assertRaises(ValueError):
            OidcConfig.from_dict({**config.to_dict(), "issuer": "http://rock.example/"})
        with self.assertRaises(ValueError):
            OidcConfig.from_dict(
                {
                    **config.to_dict(),
                    "redirect_uri": "https://attacker.example/callback",
                }
            )

    def test_authorization_request_uses_code_flow_state_nonce_and_s256_pkce(self):
        config = self.configure()
        discovery = DiscoveryDocument(
            config.issuer,
            config.issuer + "Auth/Authorize",
            config.issuer + "Auth/Token",
        )
        url = build_authorization_url(
            config, discovery, "state-value", "nonce-value", "challenge-value"
        )
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["state"], ["state-value"])
        self.assertEqual(query["nonce"], ["nonce-value"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["code_challenge"], ["challenge-value"])
        self.assertNotIn("client_secret", query)

    def test_browser_callback_exchanges_code_and_keeps_secrets_out_of_public_status(
        self,
    ):
        config = self.configure()
        self.secret_store.store(Context.DEV, "client_secret", "private-client-secret")
        http = FakeHttp()

        def browser_open(url):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            callback = (
                config.redirect_uri
                + "?"
                + urllib.parse.urlencode(
                    {"code": "short-lived-code", "state": query["state"][0]}
                )
            )

            def visit_callback():
                with urllib.request.urlopen(callback, timeout=2) as response:
                    response.read()

            threading.Thread(target=visit_callback, daemon=True).start()
            return True

        manager = OAuthManager(
            self.config_store, self.secret_store, http=http, browser_open=browser_open
        )
        self.assertEqual(manager.begin_login(Context.DEV)["state"], "starting")
        status = self.wait_for(manager, "authenticated")
        public = json.dumps(status).lower()
        for forbidden in (
            "private-client-secret",
            "short-lived-code",
            "new-access",
            "new-refresh",
            "rock.example",
            "rock-lens-client",
        ):
            self.assertNotIn(forbidden, public)

        endpoint, fields = http.forms[0]
        self.assertEqual(endpoint, "https://rock.example/Auth/Token")
        self.assertEqual(fields["grant_type"], "authorization_code")
        self.assertEqual(fields["client_secret"], "private-client-secret")
        self.assertTrue(fields["code_verifier"])
        stored = TokenSet.from_json(self.secret_store.lookup(Context.DEV, "tokens"))
        self.assertEqual(stored.access_token, "new-access")
        self.assertEqual(manager.disconnect(Context.DEV)["state"], "signed_out")
        self.assertIsNone(self.secret_store.lookup(Context.DEV, "tokens"))

    def test_expired_access_token_refreshes_without_browser(self):
        self.configure()
        expired = TokenSet(
            "old-access", "old-refresh", "Bearer", int(time.time()) - 1, "openid"
        )
        self.secret_store.store(Context.DEV, "tokens", expired.to_json())
        http = FakeHttp()
        manager = OAuthManager(
            self.config_store,
            self.secret_store,
            http=http,
            browser_open=lambda _: False,
        )

        self.assertEqual(manager.public_status(Context.DEV)["state"], "refreshing")
        self.wait_for(manager, "authenticated")
        _, fields = http.forms[0]
        self.assertEqual(
            fields,
            {
                "grant_type": "refresh_token",
                "refresh_token": "old-refresh",
                "client_id": "rock-lens-client",
            },
        )
        refreshed = TokenSet.from_json(self.secret_store.lookup(Context.DEV, "tokens"))
        self.assertEqual(refreshed.access_token, "refreshed-access")
        self.assertEqual(refreshed.refresh_token, "old-refresh")

    def test_secret_tool_passes_secret_only_on_stdin(self):
        store = SecretToolStore("/usr/bin/secret-tool")
        with patch("subprocess.run") as run:
            run.return_value.returncode = 0
            store.store(Context.DEV, "client_secret", "never-in-argv")
        args = run.call_args.args[0]
        self.assertNotIn("never-in-argv", args)
        self.assertEqual(run.call_args.kwargs["input"], b"never-in-argv")


if __name__ == "__main__":
    unittest.main()
