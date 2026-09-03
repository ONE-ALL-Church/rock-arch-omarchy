import unittest
from pathlib import Path

QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugin"
    / "oneall.rock-lens"
    / "RockLens.qml"
)
SELECTION_PATH = QML_PATH.with_name("RockLensSelectionChrome.qml")
KEY_CATCHER_PATH = QML_PATH.with_name("RockLensKeyCatcher.qml")


class QmlNavigationTests(unittest.TestCase):
    def test_first_recent_and_search_results_are_selected_automatically(self):
        source = QML_PATH.read_text(encoding="utf-8")

        self.assertIn("resultCursor = results.length ? 0 : -1", source)
        self.assertIn("recentCursor = quickReturns.length ? 0 : -1", source)
        self.assertIn(
            "readonly property bool rowSelected: index === root.resultCursor ||\n"
            "                    (root.resultCursor < 0 && index === 0 && searchField.activeFocus && root.results.length > 0)",
            source,
        )
        self.assertIn(
            "readonly property bool rowSelected: index === root.recentCursor ||\n"
            "                    (root.recentCursor < 0 && index === 0 && searchField.activeFocus && root.quickReturns.length > 0)",
            source,
        )
        self.assertEqual(source.count("RockLensSelectionChrome {"), 4)

    def test_all_navigable_rows_share_safe_selection_spacing(self):
        source = QML_PATH.read_text(encoding="utf-8")
        selection = SELECTION_PATH.read_text(encoding="utf-8")

        self.assertEqual(source.count("readonly property bool rowSelected:"), 4)
        self.assertEqual(source.count("height: Style.space(52)"), 4)
        self.assertGreaterEqual(source.count("anchors.leftMargin: 16"), 4)
        self.assertGreaterEqual(source.count("anchors.rightMargin:"), 4)
        self.assertIn("border.width: 2", selection)
        self.assertIn("border.color: Color.accent", selection)
        self.assertIn("color: Qt.rgba(Color.accent.r", selection)

    def test_settings_fold_connection_and_magnus_into_active_profile(self):
        source = QML_PATH.read_text(encoding="utf-8")

        self.assertNotIn('text: "Connection"', source)
        self.assertIn('"Login saved · Magnus available"', source)
        self.assertIn('"Login saved · No Magnus access"', source)
        self.assertIn('text: "Sign in to " + root.activeProfileName()', source)
        self.assertIn('text: root.addProfileMode ? "Cancel" : "Add profile"', source)
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

    def test_signed_out_onboarding_is_a_three_field_login(self):
        source = QML_PATH.read_text(encoding="utf-8")
        start = source.index("id: onboardingForm")
        end = source.index(
            'visible: !root.onboardingRequired && root.viewMode === "search"',
            start,
        )
        form = source[start:end]

        self.assertIn(
            'readonly property bool onboardingRequired: contextName === "PROD"',
            source,
        )
        self.assertIn("model: root.onboardingRequired ? [] :", source)
        self.assertIn(
            'visible: !root.onboardingRequired && root.viewMode === "settings"',
            source,
        )
        self.assertEqual(form.count("TextField {"), 3)
        self.assertIn('placeholderText: "Rock domain (rock.example.org)"', form)
        self.assertIn('placeholderText: "Rock username"', form)
        self.assertIn('placeholderText: "Rock password"', form)
        self.assertNotIn("profileNameField", form)
        self.assertIn("KeyNavigation.backtab: onboardingConnectButton", form)
        self.assertIn("KeyNavigation.tab: onboardingDomainField", form)
        self.assertIn("function completeOnboarding()", source)
        self.assertIn('"profile_add" : "rock_configure"', source)

    def test_unsent_credentials_are_purged_from_the_retry_queue(self):
        source = QML_PATH.read_text(encoding="utf-8")

        self.assertIn("function dropQueuedCredentialRequests()", source)
        self.assertIn("if (!isCredentialRequest(requestQueue[index]))", source)
        self.assertIn(
            "else dropQueuedCredentialRequests()",
            source,
        )
        timeout = source[source.index("id: setupTimeoutTimer") :]
        self.assertIn("root.dropQueuedCredentialRequests()", timeout[:500])

    def test_tab_ring_includes_settings_in_both_directions(self):
        source = QML_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'else if (viewMode === "personal" || viewMode === "magnus")\n'
            "        openSettings(false)",
            source,
        )
        self.assertIn(
            'if (viewMode === "settings") {\n'
            "      if (showMagnus) openMagnus()\n"
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

    def test_settings_controls_use_native_keyboard_focus_chain(self):
        source = QML_PATH.read_text(encoding="utf-8")
        key_catcher = KEY_CATCHER_PATH.read_text(encoding="utf-8")

        self.assertIn("property bool formMode: false", key_catcher)
        self.assertLess(
            key_catcher.index("if (event.key === Qt.Key_Escape)"),
            key_catcher.index("if (blocked || formMode) return"),
        )
        self.assertIn(
            'formMode: root.onboardingRequired || root.viewMode === "settings"',
            source,
        )
        self.assertIn(
            "settingsAddProfileButton.forceActiveFocus(Qt.TabFocusReason)",
            source,
        )
        for control_id in (
            "settingsAddProfileButton",
            "useProfileButton",
            "removeProfileButton",
            "changeLoginButton",
            "testProfileButton",
            "signOutButton",
            "addProfileButton",
            "saveLoginButton",
        ):
            start = source.index(f"id: {control_id}")
            self.assertIn("focusable: true", source[start : start + 350])
        self.assertGreaterEqual(
            source.count("onActiveFocusChanged: root.revealFocusedControl"),
            16,
        )
        self.assertEqual(
            source.count("Keys.onReturnPressed: root.toggle"),
            4,
        )
        self.assertEqual(
            source.count("Keys.onEnterPressed: root.toggle"),
            4,
        )

    def test_every_panel_has_a_keyboard_route_and_contextual_guidance(self):
        source = QML_PATH.read_text(encoding="utf-8")
        key_catcher = KEY_CATCHER_PATH.read_text(encoding="utf-8")

        for sequence in ("Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4"):
            self.assertIn(f'Shortcut {{ sequence: "{sequence}"', source)
        self.assertGreaterEqual(source.count("context: Qt.ApplicationShortcut"), 12)
        self.assertIn(
            'readonly property bool showMagnus: contextName === "PROD" && magnusAvailable',
            source,
        )
        self.assertIn(
            'root.showMagnus ? ["search", "personal", "magnus"]',
            source,
        )
        self.assertIn('text: "X · Clear"', source.replace(
            'root.pendingClearRecent ? "Confirm clear" : ', ""
        ))
        self.assertIn("onDeleteRequested: root.deleteCurrentItem()", source)
        self.assertIn("event.key === Qt.Key_Delete", key_catcher)
        self.assertIn(
            '"Use Up/Down to choose a Personal Link. Enter opens it in Rock."',
            source,
        )
        self.assertIn("if (changedView) panelFlick.contentY = 0", source)

    def test_magnus_preview_actions_are_tabbable_and_keep_shortcuts(self):
        source = QML_PATH.read_text(encoding="utf-8")
        key_catcher = KEY_CATCHER_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'root.pendingClearRecent || root.pendingMagnusBuildId !== "" || root.magnusPreview !== null',
            source,
        )
        self.assertIn(
            "magnusDownloadButton.forceActiveFocus(Qt.TabFocusReason)",
            source,
        )
        for control_id in (
            "magnusBackButton",
            "magnusRefreshButton",
            "magnusDownloadButton",
            "magnusCopyButton",
            "magnusHashButton",
            "magnusOpenButton",
        ):
            start = source.index(f"id: {control_id}")
            self.assertIn("focusable: true", source[start : start + 350])
        self.assertIn("commandMode: root.magnusPreviewCommandsEnabled", source)
        self.assertIn('"dchor".indexOf(event.text.toLowerCase())', key_catcher)
        for key in ("d", "c", "h", "o", "r"):
            self.assertIn(f'key === "{key}"', source)
        for label in (
            "D · Download",
            "C · Copy",
            "H · Copy hash",
            "O · Open in Rock",
            "R · Refresh",
        ):
            self.assertIn(label, source)

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
        self.assertIn("KeyNavigation.tab: magnusBuildCancelButton", source)
        self.assertIn("KeyNavigation.backtab: magnusBuildConfirmButton", source)
        self.assertIn("KeyNavigation.tab: recentBuildCancelButton", source)
        self.assertIn("KeyNavigation.backtab: recentBuildConfirmButton", source)
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

        self.assertIn(
            'text: root.feedbackText || (root.onboardingRequired ? "" : root.guidanceText())',
            source,
        )
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
