import unittest
from pathlib import Path

QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugin"
    / "oneall.rock-lens"
    / "RockLens.qml"
)


class QmlNavigationTests(unittest.TestCase):
    def test_first_recent_and_search_results_are_selected_automatically(self):
        source = QML_PATH.read_text(encoding="utf-8")

        self.assertIn("resultCursor = results.length ? 0 : -1", source)
        self.assertIn("recentCursor = quickReturns.length ? 0 : -1", source)
        self.assertIn(
            'request({op: "status"})\n'
            "    refreshQuickReturns()\n"
            "    refreshPersonalLinks()",
            source,
        )
        self.assertIn(
            'viewMode === "search" && searchField.activeFocus && activeSearchCount',
            source,
        )
        self.assertIn(
            'if (searchField.activeFocus) {\n'
            "        if (dy > 0 && activeSearchCount) selectSearchItem(0)",
            source,
        )

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

    def test_magnus_actions_and_recent_builds_are_explicit(self):
        source = QML_PATH.read_text(encoding="utf-8")

        for operation in (
            '"magnus_download"',
            '"magnus_copy"',
            '"magnus_open"',
            '"magnus_build"',
            '"activate_recent"',
        ):
            self.assertIn(operation, source)
        self.assertIn('text: "Deploy now"', source.replace('root.magnusActionBusy ? "Deploying…" : ', ''))
        self.assertIn('item.kind === "Magnus Build"', source)
        self.assertIn("confirmed: true", source)
        self.assertIn('key === "b"', source)
        self.assertIn('text: "B · Deploy"', source)
        self.assertIn('"Press Enter to deploy, or Esc to cancel."', source)
        self.assertIn('"Last deployed " + root.relativeTime', source)
        self.assertIn('function deploymentSummary(title)', source)
        self.assertIn(
            "magnusBuildConfirmButton.forceActiveFocus(Qt.TabFocusReason)", source
        )
        self.assertIn(
            "recentBuildConfirmButton.forceActiveFocus(Qt.TabFocusReason)", source
        )
        self.assertGreaterEqual(source.count("focusable: true"), 4)
        self.assertGreaterEqual(
            source.count("Keys.onEscapePressed: root.cancelMagnusBuild()"), 4
        )
        self.assertNotIn("Server actions:", source)

    def test_footer_copy_is_user_centered(self):
        source = QML_PATH.read_text(encoding="utf-8")

        self.assertIn('text: root.feedbackText || root.guidanceText()', source)
        self.assertIn('"Changes save automatically. Press Esc to return to Search."', source)
        self.assertIn('"Getting your Rock workspace ready…"', source)
        self.assertIn("Any ID or GUID checks every category.", source)
        for old_copy in (
            "Checking saved Rock login",
            "Tab Search · Shift+Tab previous",
            "↑↓ browse · Enter opens",
            "Try g: groups or w: workflow types",
        ):
            self.assertNotIn(old_copy, source)


if __name__ == "__main__":
    unittest.main()
