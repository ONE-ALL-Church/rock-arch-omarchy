from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

from .auth import (
    DEFAULT_REDIRECT_URI,
    DEFAULT_SCOPES,
    ConfigStore,
    OidcConfig,
    SecretToolStore,
    default_config_path,
)
from .contracts import Context
from .server import BrokerServer


def configure(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Configure a Rock OAuth client without placing secrets in argv"
    )
    parser.add_argument(
        "--context",
        choices=[context.value for context in Context],
        default=Context.DEV.value,
    )
    parser.add_argument("--config-file", type=Path, default=default_config_path())
    args = parser.parse_args(argv)

    context = Context(args.context)
    issuer = input("Rock issuer URL (Public Application Root): ").strip()
    client_id = input("Rock OpenID client ID: ").strip()
    redirect_uri = (
        input(f"Loopback redirect URI [{DEFAULT_REDIRECT_URI}]: ").strip()
        or DEFAULT_REDIRECT_URI
    )
    scope_text = input(f"Scopes [{' '.join(DEFAULT_SCOPES)}]: ").strip()
    scopes = tuple(scope_text.split()) if scope_text else DEFAULT_SCOPES
    client_secret = getpass.getpass("Client secret (blank for a PKCE public client): ")

    config = OidcConfig.from_dict(
        {
            "issuer": issuer,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
        }
    )
    secrets_store = SecretToolStore()
    if not secrets_store.available():
        raise SystemExit(
            "Secret Service is unavailable; OAuth configuration was not saved."
        )
    if client_secret:
        secrets_store.store(context, "client_secret", client_secret)
    else:
        secrets_store.clear(context, "client_secret")
    ConfigStore(args.config_file).set(context, config)
    print(
        f"Rock Lens {context.value} OAuth configuration saved with owner-only permissions."
    )


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "configure":
        configure(sys.argv[2:])
        return

    runtime = (
        Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        / "rock-lens"
    )
    state = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "rock-lens"
    )
    parser = argparse.ArgumentParser(
        description="Owner-local, read-only Rock Lens broker"
    )
    parser.add_argument("--socket", type=Path, default=runtime / "broker.sock")
    parser.add_argument("--state-file", type=Path, default=state / "context")
    args = parser.parse_args()
    asyncio.run(BrokerServer(args.socket, args.state_file).run())


if __name__ == "__main__":
    main()
