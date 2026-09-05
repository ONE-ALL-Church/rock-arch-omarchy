"""Exercise a fresh runtime layout without the user's shell, keyring, or Rock."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from rock_arch_broker.terminal_access import TerminalAccessManager, render_launcher

ROOT = Path(__file__).resolve().parents[1]
BROKER_DRIVER = """
import runpy
import sys
from pathlib import Path
from unittest.mock import patch
from rock_arch_broker.secret_store import SecretToolStore

fixture_home = Path(sys.argv[1])
sys.argv = ["rock_arch_broker"]
with (
    patch.object(Path, "home", return_value=fixture_home),
    patch.object(SecretToolStore, "lookup", side_effect=AssertionError("keyring access")),
    patch.object(SecretToolStore, "store", side_effect=AssertionError("keyring access")),
    patch.object(SecretToolStore, "clear", side_effect=AssertionError("keyring access")),
    patch("socket.create_connection", side_effect=AssertionError("network access")),
):
    runpy.run_module("rock_arch_broker", run_name="__main__")
"""


class DistributionTests(unittest.TestCase):
    def test_fresh_launcher_broker_restart_and_removal(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture_home = Path(temporary)
            install = fixture_home / ".config/omarchy/plugins/oneall.rock-arch"
            install.mkdir(parents=True)
            for folder in ("rock_arch_broker", "plugin"):
                shutil.copytree(
                    ROOT / folder, install / folder,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
            shutil.copy2(ROOT / "manifest.json", install / "manifest.json")
            launcher = fixture_home / ".local/bin/rock-arch"
            # An existing managed launcher must migrate to the renamed package
            # before it can launch or communicate with the installed broker.
            launcher.parent.mkdir(parents=True, mode=0o700)
            launcher.write_bytes(
                render_launcher(install).replace(b"rock_arch_broker", b"rock_lens_broker")
            )
            launcher.chmod(0o755)
            manager = TerminalAccessManager(install, launcher, installed_root=install)
            manager.ensure_launcher()
            self.assertEqual(launcher.read_bytes(), render_launcher(install))

            # Do not replace HOME. Only the broker driver's Path.home is patched;
            # every other path is scoped through the supported XDG variables.
            environment = dict(os.environ)
            environment.update({
                "XDG_RUNTIME_DIR": str(fixture_home / "run"),
                "XDG_CONFIG_HOME": str(fixture_home / ".config"),
                "XDG_STATE_HOME": str(fixture_home / ".local/state"),
                "ROCK_ARCH_DEVELOPER_MODE": "0",
                "PYTHONPATH": str(install),
            })
            socket_path = fixture_home / "run/rock-arch/broker.sock"
            tab_order = ["knowledge", "search", "magnus", "personal"]
            for startup in range(2):
                # Second startup must reclaim the first broker's private socket.
                process = subprocess.Popen(
                    [sys.executable, "-c", BROKER_DRIVER, str(fixture_home)],
                    cwd=install, env=environment,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                try:
                    deadline = time.monotonic() + 5
                    while True:
                        if process.poll() is not None:
                            self.fail("isolated broker exited during startup")
                        result = subprocess.run(
                            [str(launcher), "--no-start", "status"],
                            cwd=fixture_home, env=environment,
                            capture_output=True, text=True, timeout=5, check=False,
                        )
                        if result.returncode == 0:
                            break
                        if time.monotonic() >= deadline:
                            self.fail("isolated launcher could not reach broker")
                        time.sleep(0.02)
                    status = json.loads(result.stdout)
                    self.assertEqual(status["context"], "PROD")
                    self.assertFalse(status["rock"]["configured"])
                    self.assertEqual(status["profiles"]["profiles"], [])
                    self.assertTrue(status["terminal"]["installed"])
                    self.assertEqual(socket_path.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(socket_path.parent.stat().st_mode & 0o777, 0o700)

                    def command(*args, input_value=None, expected=0):
                        result = subprocess.run(
                            [str(launcher), "--no-start", *args],
                            cwd=fixture_home, env=environment,
                            input=input_value, capture_output=True, text=True, timeout=8, check=False,
                        )
                        self.assertEqual(result.returncode, expected, result.stderr)
                        return json.loads(result.stdout if expected == 0 else result.stderr)

                    settings = command("settings", "get")["settings"]
                    self.assertEqual(settings["tabOrder"], tab_order if startup else ["search", "personal", "knowledge", "magnus"])
                    command("settings", "set", "tabOrder", json.dumps(tab_order))
                    command("settings", "set", "--stdin", input_value='{"recentLinks":false,"tabOrder":[]}', expected=4)
                    settings = command("settings", "get")["settings"]
                    self.assertTrue(settings["recentLinks"])
                    self.assertEqual(settings["tabOrder"], tab_order)
                    command("settings", "set", "terminalAccess", "false")
                    self.assertEqual(command("status", expected=3)["error"], "terminal_access_disabled")
                    self.assertFalse(command("settings", "get")["settings"]["terminalAccess"])
                    command("settings", "set", "terminalAccess", "true")
                finally:
                    process.terminate()
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate(timeout=5)

            # Follow the documented cleanup only for this fixture's known files.
            self.assertEqual(launcher.read_bytes(), render_launcher(install))
            launcher.unlink()
            shutil.rmtree(install)
            self.assertFalse(launcher.exists())
            self.assertFalse(install.exists())


if __name__ == "__main__":
    unittest.main()
