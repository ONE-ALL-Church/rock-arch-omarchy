import json
import tomllib
import unittest
from pathlib import Path

from rock_lens_broker.version import HTTP_USER_AGENT, VERSION

ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_versions_stay_synchronized(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        pyproject = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        qml = (ROOT / "plugin/oneall.rock-lens/RockLens.qml").read_text(
            encoding="utf-8"
        )

        self.assertEqual(manifest["version"], VERSION)
        self.assertEqual(pyproject["project"]["version"], VERSION)
        self.assertIn(f"Rock Lens {VERSION} ", qml)
        self.assertEqual(HTTP_USER_AGENT, f"Rock-Lens/{'.'.join(VERSION.split('.')[:2])}")

    def test_root_manifest_describes_a_distributable_plugin(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        entry_point = manifest["entryPoints"]["barWidget"]

        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["id"], "oneall.rock-lens")
        self.assertTrue((ROOT / entry_point).is_file())
        self.assertFalse((ROOT / "plugin/oneall.rock-lens/manifest.json").exists())

    def test_public_install_url_is_not_a_placeholder(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "https://github.com/bscottdavis/rock-lens-omarchy.git",
            readme,
        )
        self.assertNotIn("github.com/OWNER/", readme)

    def test_obsolete_openid_surface_is_not_distributed(self):
        self.assertFalse((ROOT / "rock_lens_broker/auth.py").exists())
        self.assertFalse((ROOT / "tests/test_auth.py").exists())
        main = (ROOT / "rock_lens_broker/__main__.py").read_text(encoding="utf-8")
        self.assertNotIn('sys.argv[1] == "configure"', main)


if __name__ == "__main__":
    unittest.main()
