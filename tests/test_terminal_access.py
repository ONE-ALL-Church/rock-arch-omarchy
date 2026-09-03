import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rock_lens_broker.terminal_access import (
    CLI_LAUNCHER_MARKER,
    TerminalAccessManager,
)


class TerminalAccessManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir(mode=0o700)
        self.launcher = self.bin / "rock-arch"
        self.plugin_root = Path(__file__).resolve().parents[1]

    def test_launcher_is_atomic_executable_and_reports_status(self):
        manager = TerminalAccessManager(
            self.plugin_root, self.launcher, installed_root=self.plugin_root
        )

        manager.ensure_launcher()

        self.assertEqual(self.launcher.stat().st_mode & 0o777, 0o755)
        content = self.launcher.read_text(encoding="utf-8")
        self.assertIn(CLI_LAUNCHER_MARKER, content)
        self.assertIn(str(self.plugin_root), content)
        with patch(
            "rock_lens_broker.terminal_access.shutil.which",
            return_value=str(self.launcher),
        ):
            status = manager.status(enabled=True)
        self.assertTrue(status["enabled"])
        self.assertTrue(status["installed"])
        self.assertTrue(status["inPath"])
        self.assertEqual(status["error"], "")

    def test_launcher_does_not_replace_an_unmanaged_command(self):
        self.launcher.write_text("#!/bin/sh\necho existing\n", encoding="utf-8")
        self.launcher.chmod(0o755)
        manager = TerminalAccessManager(
            self.plugin_root, self.launcher, installed_root=self.plugin_root
        )

        manager.ensure_launcher()

        self.assertEqual(
            self.launcher.read_text(encoding="utf-8"),
            "#!/bin/sh\necho existing\n",
        )
        self.assertEqual(manager.status(enabled=True)["error"], "cli_launcher_conflict")

    def test_launcher_refuses_a_writable_or_foreign_shape(self):
        self.bin.chmod(0o777)
        manager = TerminalAccessManager(
            self.plugin_root, self.launcher, installed_root=self.plugin_root
        )
        manager.ensure_launcher()
        self.assertFalse(self.launcher.exists())
        self.assertEqual(
            manager.status(enabled=True)["error"], "cli_launcher_unavailable"
        )

        self.bin.chmod(0o700)
        target = self.root / "target"
        target.write_text("keep", encoding="utf-8")
        os.symlink(target, self.launcher)
        manager.ensure_launcher()
        self.assertTrue(self.launcher.is_symlink())
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    def test_source_checkout_does_not_install_managed_launcher(self):
        manager = TerminalAccessManager(
            self.plugin_root,
            self.launcher,
            installed_root=self.root / "different-install",
        )

        manager.ensure_launcher()

        self.assertFalse(self.launcher.exists())
        self.assertEqual(
            manager.status(enabled=True)["error"],
            "cli_launcher_managed_manually",
        )


if __name__ == "__main__":
    unittest.main()
