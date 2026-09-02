from pathlib import Path
import unittest


QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugin"
    / "oneall.rock-lens"
    / "RockLens.qml"
)


class QmlNavigationTests(unittest.TestCase):
    def test_tab_ring_includes_settings_in_both_directions(self):
        source = QML_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'else if (viewMode === "personal" || viewMode === "magnus")\n'
            "        openSettings(false)",
            source,
        )
        self.assertIn(
            'if (viewMode === "settings") {\n'
            "      if (magnusAvailable) openMagnus()\n"
            "      else selectPersonalLink(Math.max(0, navigationCount - 1))",
            source,
        )
        self.assertIn(
            'if (viewMode === "settings")\n        focusSearch()',
            source,
        )
        self.assertIn(
            '} else if (resultCursor >= 0 || recentCursor >= 0) {\n'
            "      focusSearch()\n"
            "    } else {\n"
            "      openSettings(false)",
            source,
        )


if __name__ == "__main__":
    unittest.main()
