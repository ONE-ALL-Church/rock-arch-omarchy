import json
import tomllib
import unittest
from pathlib import Path

from rock_arch_broker.version import HTTP_USER_AGENT, VERSION

ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_versions_stay_synchronized(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        pyproject = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        plugin_root = ROOT / "plugin/oneall.rock-arch"
        qml = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(plugin_root.glob("*.qml"))
        )

        self.assertEqual(manifest["version"], VERSION)
        self.assertEqual(pyproject["project"]["version"], VERSION)
        self.assertIn(f'property string currentVersion: "{VERSION}"', qml)
        self.assertEqual(HTTP_USER_AGENT, f"Rock-Arch/{'.'.join(VERSION.split('.')[:2])}")

    def test_root_manifest_describes_a_distributable_plugin(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        entry_point = manifest["entryPoints"]["barWidget"]

        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["id"], "oneall.rock-arch")
        self.assertEqual(manifest["name"], "Rock Arch")
        self.assertEqual(manifest["description"], "Bridging Rock RMS and Omarchy")
        self.assertTrue((ROOT / entry_point).is_file())
        self.assertTrue(
            (ROOT / "plugin/oneall.rock-arch/assets/rock-arch.svg").is_file()
        )
        self.assertFalse((ROOT / "plugin/oneall.rock-arch/manifest.json").exists())

    def test_terminal_cli_is_packaged_and_documented(self):
        pyproject = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual(
            pyproject["project"]["scripts"]["rock-arch"],
            "rock_arch_broker.cli:main",
        )
        self.assertTrue((ROOT / "rock_arch_broker/cli.py").is_file())
        self.assertTrue((ROOT / "rock_arch_broker/terminal_access.py").is_file())
        self.assertTrue((ROOT / "docs/CLI.md").is_file())
        self.assertIn("docs/CLI.md", readme)

    def test_public_install_url_is_not_a_placeholder(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "https://github.com/ONE-ALL-Church/rock-arch-omarchy.git",
            readme,
        )
        self.assertNotIn("github.com/OWNER/", readme)
        self.assertIn("# Rock Arch — Bridging Rock RMS and Omarchy", readme)

    def test_obsolete_openid_surface_is_not_distributed(self):
        self.assertFalse((ROOT / "rock_arch_broker/auth.py").exists())
        self.assertFalse((ROOT / "tests/test_auth.py").exists())
        main = (ROOT / "rock_arch_broker/__main__.py").read_text(encoding="utf-8")
        self.assertNotIn('sys.argv[1] == "configure"', main)

    def test_ci_dependencies_and_broker_interpreter_are_pinned(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        qml = (ROOT / "plugin/oneall.rock-arch/RockArchBroker.qml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("uses: actions/checkout@v", workflow)
        self.assertNotIn("uses: actions/setup-python@v", workflow)
        self.assertNotIn("uses: astral-sh/setup-uv@v", workflow)
        self.assertIn("uvx --from ruff==", workflow)
        self.assertIn("uvx --from ty==", workflow)
        self.assertIn(
            'command: ["/usr/bin/python3", "-m", "rock_arch_broker"]', qml
        )


if __name__ == "__main__":
    unittest.main()
