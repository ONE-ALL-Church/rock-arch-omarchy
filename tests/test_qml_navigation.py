import unittest
from pathlib import Path

QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugin"
    / "oneall.rock-arch"
    / "RockLens.qml"
)
SELECTION_PATH = QML_PATH.with_name("RockLensSelectionChrome.qml")
BAR_BUTTON_PATH = QML_PATH.with_name("RockArchBarButton.qml")
ICON_PATH = QML_PATH.with_name("RockArchIcon.qml")
HERO_PATH = QML_PATH.with_name("RockLensHero.qml")
KEY_CATCHER_PATH = QML_PATH.with_name("RockLensKeyCatcher.qml")
LOGIN_PATH = QML_PATH.with_name("RockLensLoginPanel.qml")
FINISH_SETUP_PATH = QML_PATH.with_name("RockLensFinishSetupPanel.qml")
MAGNUS_PATH = QML_PATH.with_name("RockLensMagnusPanel.qml")
NAVIGATION_PATH = QML_PATH.with_name("RockLensNavigationTabs.qml")
PERSONAL_PATH = QML_PATH.with_name("RockLensPersonalPanel.qml")
SEARCH_PATH = QML_PATH.with_name("RockLensSearchPanel.qml")
KNOWLEDGE_PATH = QML_PATH.with_name("RockLensKnowledgePanel.qml")
SETTINGS_PATH = QML_PATH.with_name("RockLensSettingsPanel.qml")
SCOPES_PATH = QML_PATH.with_name("RockLensSearchScopes.js")
PANEL_PATHS = (
    BAR_BUTTON_PATH,
    ICON_PATH,
    HERO_PATH,
    LOGIN_PATH,
    FINISH_SETUP_PATH,
    MAGNUS_PATH,
    NAVIGATION_PATH,
    PERSONAL_PATH,
    SEARCH_PATH,
    KNOWLEDGE_PATH,
    SETTINGS_PATH,
    SCOPES_PATH,
)


def all_qml_source() -> str:
    return QML_PATH.read_text(encoding="utf-8") + "\n" + "\n".join(
        path.read_text(encoding="utf-8") for path in PANEL_PATHS
    )


class QmlNavigationTests(unittest.TestCase):
    def test_first_recent_and_search_results_are_selected_automatically(self):
        source = all_qml_source()

        self.assertIn(
            "resultCursor = preservedCursor >= 0 ? preservedCursor : "
            "(results.length ? 0 : -1)",
            source,
        )
        self.assertIn("recentCursor = quickReturns.length ? 0 : -1", source)
        self.assertIn(
            "readonly property bool rowSelected: resultRow.index === searchPanel.controller.resultCursor ||",
            source,
        )
        self.assertIn(
            "readonly property bool rowSelected: recentRow.index === searchPanel.controller.recentCursor ||",
            source,
        )
        self.assertEqual(source.count("RockLensSelectionChrome {"), 5)

    def test_all_navigable_rows_share_safe_selection_spacing(self):
        source = all_qml_source()
        selection = SELECTION_PATH.read_text(encoding="utf-8")

        self.assertEqual(source.count("readonly property bool rowSelected:"), 5)
        self.assertEqual(source.count("height: Style.space(54)"), 5)
        self.assertGreaterEqual(
            source.count("anchors.leftMargin: Style.spacing.rowPaddingX"), 4
        )
        self.assertGreaterEqual(source.count("anchors.rightMargin:"), 4)
        self.assertIn('Border.controlSpec("hover-cursor"', selection)
        self.assertIn("Style.hoverFillFor(Color.foreground, Color.accent)", selection)
        self.assertNotIn("border.width:", selection)

    def test_settings_fold_connection_and_magnus_into_active_profile(self):
        source = all_qml_source()

        self.assertNotIn('text: "Connection"', source)
        self.assertIn('"Connected · Magnus available"', source)
        self.assertIn('"Connected · Search and Personal Links"', source)
        self.assertIn(
            'text: "Sign in to " + settingsPanel.controller.activeProfileName()',
            source,
        )
        self.assertIn(
            'text: settingsPanel.controller.addProfileMode ? "Cancel" : "Add profile"',
            source,
        )
        self.assertIn(
            'request({op: "status"})\n'
            "    refreshQuickReturns()",
            source,
        )
        self.assertIn("if (changedView) refreshPersonalLinks()", source)
        self.assertIn(
            'viewMode === "search" && searchField.activeFocus && activeSearchCount',
            source,
        )
        self.assertIn(
            'if (searchField.activeFocus) {\n'
            "        if (dy > 0 && activeSearchCount) selectSearchItem(0)",
            source,
        )

    def test_signed_out_onboarding_collects_a_profile_name_first(self):
        source = all_qml_source()
        form = LOGIN_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'readonly property bool onboardingRequired: contextName === "PROD"',
            source,
        )
        navigation = NAVIGATION_PATH.read_text(encoding="utf-8")
        self.assertIn("model: navigation.controller.onboardingFlowActive ? [] :", navigation)
        self.assertIn(
            'visible: !root.onboardingFlowActive && root.viewMode === "settings"',
            source,
        )
        self.assertEqual(form.count("TextField {"), 4)
        self.assertIn('PanelSectionHeader { text: "PROFILE NAME" }', form)
        self.assertIn('placeholderText: "Rock Solid Church Production"', form)
        self.assertIn('PanelSectionHeader { text: "ROCK DOMAIN" }', form)
        self.assertIn('placeholderText: "rock.example.org"', form)
        self.assertIn('placeholderText: "Rock username"', form)
        self.assertIn('placeholderText: "Rock password"', form)
        self.assertIn("property alias profileNameField", form)
        self.assertIn("KeyNavigation.backtab: onboardingProfileNameField", form)
        self.assertIn("KeyNavigation.tab: onboardingProfileNameField", form)
        self.assertIn("focusTarget: root.finishSetupOnboardingRequired", source)
        self.assertIn(
            ": (root.onboardingRequired ? onboardingForm.profileNameField : searchField)",
            source,
        )
        self.assertIn("function completeOnboarding()", source)
        self.assertIn('"profile_add" : "rock_configure"', source)

    def test_one_time_finish_setup_follows_successful_login(self):
        source = all_qml_source()
        prompt = FINISH_SETUP_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'readonly property bool finishSetupOnboardingRequired: contextName === "PROD"',
            source,
        )
        self.assertIn(
            "!preferenceOnboardingSetupCompleted",
            source,
        )
        self.assertIn('text: "Finish setup"', prompt)
        self.assertIn('PanelSectionHeader { text: "SEARCH CATEGORIES" }', prompt)
        self.assertIn('PanelSectionHeader { text: "UPDATES" }', prompt)
        self.assertIn('"Automatic updates · On"', prompt)
        self.assertIn('"Continue to Search"', prompt)
        self.assertIn("controller.availableCategoryOptions()", prompt)
        self.assertIn("searchCapabilitiesInFlight", prompt)
        self.assertGreaterEqual(prompt.count("Keys.onEscapePressed:"), 3)
        self.assertIn(
            'op: "onboarding_setup_complete"',
            source,
        )
        self.assertIn(
            "finishSetupPanel.primaryButton.forceActiveFocus(Qt.TabFocusReason)",
            source,
        )

    def test_search_category_model_includes_type_entities_and_shortcuts(self):
        source = all_qml_source()

        self.assertIn('{key: "Group Types", label: "Group Types"}', source)
        self.assertIn(
            '{key: "Content Channel Types", label: "Content Channel Types"}',
            source,
        )
        self.assertIn('sequence: "Alt+Shift+G"', source)
        self.assertIn('onActivated: root.applyScope("gt")', source)
        self.assertIn('sequence: "Alt+Shift+C"', source)
        self.assertIn('onActivated: root.applyScope("ct")', source)

    def test_public_knowledge_panel_is_dedicated_private_and_keyboard_complete(self):
        source = all_qml_source()
        search = SEARCH_PATH.read_text(encoding="utf-8")
        knowledge = KNOWLEDGE_PATH.read_text(encoding="utf-8")

        self.assertIn('prefix === "kb" || prefix === "knowledge"', source)
        self.assertIn('sequence: "Alt+K"', source)
        self.assertIn('onActivated: root.openKnowledge()', source)
        self.assertIn('{ key: "knowledge", label: "Knowledge", shortcut: "Alt+K" }', source)
        self.assertIn('root.scopeKeyForQuery(text) === "kb"', source)
        self.assertNotIn("Knowledge", search)
        self.assertIn(
            "Your query is sent to Rock Agent KB. Don't include names or private church data.",
            knowledge,
        )
        for hint in ("mm:", "is:", "idea:", "lava:", "recipe:", "guide:"):
            self.assertIn(hint, knowledge)
        self.assertIn('request({op: "knowledge_search", query: knowledgeQuery})', source)
        self.assertIn('request({op: "knowledge_result", safeId: knowledgeResults[index].safeId})', source)
        self.assertIn('request({op: "knowledge_result", safeId: knowledgeDetail.links[index].safeId})', source)
        self.assertIn('op: "knowledge_open_source", safeId: knowledgeDetail.safeId', source)
        self.assertIn("function closeKnowledgeDetail()", source)
        self.assertIn("knowledgePanel.backButton.forceActiveFocus", source)
        self.assertIn('text: "Back"', source)
        self.assertIn('text: knowledgePanel.controller.knowledgeBusy ? "Opening…" : "Open source"', source)
        self.assertIn("Keys.onEscapePressed: knowledgePanel.controller.closeKnowledgeDetail()", source)

    def test_cli_ui_handoff_is_one_time_and_build_copy_is_honest(self):
        source = all_qml_source()

        self.assertIn('function handoff(): void', source)
        self.assertIn('root.request({op: "ui_handoff_take"})', source)
        self.assertIn("function applyUiHandoff(handoff)", source)
        self.assertIn('"Last started " + relativeTime(acceptedAt)', source)
        self.assertNotIn('"Last deployed "', source)

    def test_search_categories_follow_the_active_accounts_detected_access(self):
        source = all_qml_source()
        settings = SETTINGS_PATH.read_text(encoding="utf-8")
        finish = FINISH_SETUP_PATH.read_text(encoding="utf-8")

        self.assertIn('op: "search_capabilities"', source)
        self.assertIn("root.searchCapabilitiesReady", source)
        self.assertIn(
            'root.effectiveCategoryEnabled("Jobs")',
            source,
        )
        self.assertIn("controller.availableCategoryOptions()", settings)
        self.assertIn("controller.availableCategoryOptions()", finish)
        self.assertIn('text: "Check again"', settings)

    def test_existing_profiles_have_a_keyboard_accessible_rename_form(self):
        source = all_qml_source()

        for control_id in (
            "renameProfileButton",
            "profileRenameField",
            "saveProfileNameButton",
            "cancelProfileRenameButton",
        ):
            start = source.index(f"id: {control_id}")
            excerpt = source[start : start + 500]
            self.assertTrue(
                "focusable: true" in excerpt or "activeFocusOnTab: true" in excerpt
            )
        self.assertIn('request({op: "profile_rename", profileId: profileId, name: name})', source)
        self.assertIn("Keys.onEscapePressed:", source)

    def test_unsent_credentials_are_purged_from_the_retry_queue(self):
        source = all_qml_source()

        self.assertIn("function dropQueuedCredentialRequests()", source)
        self.assertIn("if (!isCredentialRequest(requestQueue[index]))", source)
        self.assertIn(
            "else { dropQueuedCredentialRequests(); panelCleanupTimer.restart() }",
            source,
        )
        timeout = source[source.index("id: setupTimeoutTimer") :]
        self.assertIn("root.dropQueuedCredentialRequests()", timeout[:500])

    def test_startup_status_retries_until_the_broker_responds(self):
        source = QML_PATH.read_text(encoding="utf-8")
        timer = source[source.index("id: startupStatusTimer") :]

        self.assertIn("repeat: true", timer[:220])
        self.assertIn("running: !root.statusLoaded", timer[:220])
        self.assertIn('request({op: "status"})', timer[:220])
        self.assertNotIn("probeMagnus: true", timer[:220])

    def test_search_refreshes_keep_selection_and_do_not_yield_to_magnus(self):
        source = QML_PATH.read_text(encoding="utf-8")
        key_catcher = KEY_CATCHER_PATH.read_text(encoding="utf-8")

        self.assertIn("if (query !== searchInFlightQuery) searchPending = true", source)
        self.assertIn("completedSearchQuery === resultsQuery", source)
        self.assertIn("results.findIndex(function(item)", source)
        self.assertIn("if (preservedCursor < 0) panelFlick.contentY = 0", source)
        self.assertIn("setupBusy || searchInFlight || searchTimer.running", source)
        self.assertIn("id: searchTimer; interval: 160", source)
        self.assertIn("magnusProbeTimer.restart()", source)
        self.assertIn("clip: true", key_catcher)
        self.assertIn("id: panelCleanupTimer; interval: 180", source)
        self.assertIn("readonly property bool resultsAreCurrent:", source)
        self.assertIn("if (!resultsAreCurrent || index < 0", source)
        text_edit = source[source.index("onTextEdited: {") :]
        text_edit = text_edit[: text_edit.index("Keys.priority:")]
        self.assertNotIn("root.results = []", text_edit)
        self.assertNotIn('root.resultsQuery = ""', text_edit)
        reset = source[source.index("function resetPanel()") :]
        reset = reset[: reset.index("onOpenedChanged:")]
        self.assertNotIn("refreshPersonalLinks()", reset)

    def test_tab_ring_includes_settings_in_both_directions(self):
        source = all_qml_source()

        self.assertIn(
            'else if (viewMode === "knowledge" || viewMode === "magnus")\n'
            "        openSettings(false)",
            source,
        )
        self.assertIn(
            'if (viewMode === "settings") {\n'
            "      if (showMagnus) openMagnus()\n"
            "      else openKnowledge()",
            source,
        )
        self.assertIn('else if (viewMode === "personal")\n        openKnowledge()', source)
        self.assertIn('} else if (viewMode === "magnus") {\n      openKnowledge()', source)
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

    def test_settings_controls_use_omarchy_keyboard_focus_chain(self):
        source = all_qml_source()
        key_catcher = KEY_CATCHER_PATH.read_text(encoding="utf-8")

        self.assertIn("import qs.Ui", SETTINGS_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("CheckBox {", source)
        self.assertIn("Toggle {", source)
        self.assertIn("property bool formMode: false", key_catcher)
        self.assertLess(
            key_catcher.index("if (event.key === Qt.Key_Escape)"),
            key_catcher.index("if (blocked || formMode) return"),
        )
        self.assertIn(
            'formMode: root.onboardingFlowActive || root.viewMode === "settings"',
            source,
        )
        self.assertIn(
            "settingsPanel.primaryButton.forceActiveFocus(Qt.TabFocusReason)",
            source,
        )
        for control_id in (
            "settingsAddProfileButton",
            "useProfileButton",
            "renameProfileButton",
            "removeProfileButton",
            "changeLoginButton",
            "testProfileButton",
            "signOutButton",
            "addProfileButton",
            "saveLoginButton",
        ):
            start = source.index(f"id: {control_id}")
            self.assertIn("focusable: true", source[start : start + 500])
        self.assertGreaterEqual(
            source.count("onActiveFocusChanged:"),
            16,
        )
        self.assertGreaterEqual(source.count("focusable: true"), 18)

    def test_menu_bar_item_can_be_hidden_without_removing_shortcut_access(self):
        source = all_qml_source()

        self.assertIn('label: "Show in the menu bar"', source)
        self.assertIn("implicitWidth: preferenceShowMenuBar ? button.implicitWidth : 0", source)
        self.assertIn("visible: controller.preferenceShowMenuBar", source)
        self.assertIn(
            'updatePreference("showMenuBar", controller.preferenceShowMenuBar)', source
        )
        self.assertIn("Super+R still opens Rock Arch", source)

    def test_menu_bar_uses_the_theme_colored_rock_arch_mark(self):
        source = all_qml_source()

        self.assertIn("ShapePath.OddEvenFill", ICON_PATH.read_text(encoding="utf-8"))
        self.assertIn("hasVisualContent: true", source)
        self.assertIn(
            "color: button.active ? button.activeColor : button.foreground", source
        )
        self.assertIn('tooltipText: "Rock Arch"', source)

    def test_settings_exposes_bounded_opt_in_plugin_updates(self):
        source = all_qml_source()

        self.assertIn('text: "Settings" + (navigation.controller.updateAvailable ? "  •" : "")', source)
        self.assertIn('label: "Install updates automatically"', source)
        self.assertIn('request({op: "update_check"})', source)
        self.assertIn('request({op: "update_start"})', source)
        self.assertIn('property bool preferenceAutomaticUpdates: false', source)
        self.assertIn("interval: 86400000", source)
        self.assertIn('"Check daily and install only after Omarchy validation."', source)

    def test_terminal_and_agent_access_is_on_by_default_and_settings_only(self):
        source = all_qml_source()
        finish_setup = FINISH_SETUP_PATH.read_text(encoding="utf-8")

        self.assertIn('property bool preferenceTerminalAccess: true', source)
        self.assertIn('label: "Allow terminal and agent access"', source)
        self.assertIn('updatePreference("terminalAccess", preferenceTerminalAccess)', source)
        self.assertIn('"Use rock-arch from this account; no network listener is opened."', source)
        self.assertNotIn("terminal", finish_setup.lower())

    def test_every_panel_has_a_keyboard_route_and_contextual_guidance(self):
        source = all_qml_source()
        key_catcher = KEY_CATCHER_PATH.read_text(encoding="utf-8")

        for sequence in ("Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4"):
            self.assertIn(f'Shortcut {{ sequence: "{sequence}"', source)
        self.assertGreaterEqual(source.count("context: Qt.ApplicationShortcut"), 12)
        self.assertIn(
            'readonly property bool showMagnus: contextName === "PROD" && magnusAvailable',
            source,
        )
        self.assertIn('{ key: "magnus", label: "Magnus", shortcut: "Ctrl+3" }', source)
        self.assertIn('tooltipText: "Clear Recent Links · X"', source)
        self.assertIn("onDeleteRequested: root.deleteCurrentItem()", source)
        self.assertIn("event.key === Qt.Key_Delete", key_catcher)
        self.assertIn('text: "PERSONAL LINKS"', source)
        self.assertIn("if (changedView) panelFlick.contentY = 0", source)

    def test_magnus_preview_actions_are_tabbable_and_keep_shortcuts(self):
        source = all_qml_source()
        key_catcher = KEY_CATCHER_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'root.pendingClearRecent || root.pendingMagnusBuildId !== "" || root.magnusPreview !== null',
            source,
        )
        self.assertIn(
            "magnusPanel.previewPrimaryButton.forceActiveFocus(Qt.TabFocusReason)",
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
            self.assertIn("focusable: true", source[start : start + 500])
        self.assertIn("commandMode: root.magnusPreviewCommandsEnabled", source)
        self.assertIn('"dchor".indexOf(event.text.toLowerCase())', key_catcher)
        for key in ("d", "c", "h", "o", "r"):
            self.assertIn(f'key === "{key}"', source)
        for label in (
            "D · Download",
            "C · Copy",
            "H · Hash",
            "O · Open",
        ):
            self.assertIn(label, source)
        self.assertIn('tooltipText: "Refresh Magnus · R"', source)

    def test_magnus_actions_and_recent_builds_are_explicit(self):
        source = all_qml_source()

        for operation in (
            '"magnus_download"',
            '"magnus_copy"',
            '"magnus_open"',
            '"magnus_build"',
            '"activate_recent"',
        ):
            self.assertIn(operation, source)
        self.assertIn('"Deploy now"', source)
        self.assertIn('item.kind === "Magnus Build"', source)
        self.assertIn("confirmed: true", source)
        self.assertIn('key === "b"', source)
        self.assertIn('text: "B · Deploy"', source)
        self.assertIn('". This starts a production mobile-app build."', source)
        self.assertIn('"Last started " + searchPanel.controller.relativeTime', source)
        self.assertIn('function deploymentSummary(title)', source)
        self.assertIn(
            "magnusPanel.buildConfirmButton.forceActiveFocus(Qt.TabFocusReason)", source
        )
        self.assertIn("KeyNavigation.tab: magnusBuildCancelButton", source)
        self.assertIn("KeyNavigation.backtab: magnusBuildConfirmButton", source)
        self.assertIn("KeyNavigation.tab: recentBuildCancelButton", source)
        self.assertIn("KeyNavigation.backtab: recentBuildConfirmButton", source)
        self.assertIn(
            "searchPanel.buildConfirmButton.forceActiveFocus(Qt.TabFocusReason)", source
        )
        self.assertGreaterEqual(source.count("focusable: true"), 4)
        self.assertGreaterEqual(
            source.count("Keys.onEscapePressed:"), 4
        )
        self.assertNotIn("Server actions:", source)

    def test_footer_is_reserved_for_transient_status(self):
        source = all_qml_source()

        self.assertIn(
            'text: root.feedbackText || (root.onboardingFlowActive ? "" : root.guidanceText())',
            source,
        )
        self.assertIn("height: Math.max(Style.space(18), implicitHeight)", source)
        self.assertIn("opacity: text.length > 0 ? 1 : 0", source)
        self.assertIn('"Getting your Rock workspace ready…"', source)
        self.assertIn('if (updateState === "updating")', source)
        self.assertIn('return ""', source[source.index("function guidanceText()") :])
        for persistent_tutorial in (
            "Changes save automatically. Press Esc",
            "Use Up/Down to choose a Personal Link",
            "Any ID or GUID checks every category",
            "Checking saved Rock login",
            "Tab Search · Shift+Tab previous",
            "↑↓ browse · Enter opens",
            "Try g: groups or w: workflow types",
        ):
            self.assertNotIn(persistent_tutorial, source)

    def test_panel_matches_first_party_omarchy_anatomy(self):
        source = all_qml_source()

        self.assertIn("RockLensHero {", source)
        self.assertIn("PanelSeparator {}", source)
        self.assertIn("panel.fittedContentWidth(Style.space(430))", source)
        self.assertIn("panel.fittedContentHeight(content.implicitHeight, Style.space(600))", source)
        self.assertIn("spacing: Style.spacing.panelGap", source)
        self.assertIn("Border.controlSpec", source)
        self.assertNotIn('color: "#14532d"', source)
        self.assertNotIn('color: "#86efac"', source)

    def test_panels_are_composed_from_focused_components(self):
        source = QML_PATH.read_text(encoding="utf-8")

        for component in (
            "RockLensLoginPanel",
            "RockLensFinishSetupPanel",
            "RockLensSearchPanel",
            "RockLensPersonalPanel",
            "RockLensKnowledgePanel",
            "RockLensMagnusPanel",
            "RockLensSettingsPanel",
            "RockLensNavigationTabs",
            "RockLensHero",
            "RockArchBarButton",
        ):
            self.assertIn(f"{component} {{", source)
        self.assertLess(len(source.splitlines()), 2_000)


if __name__ == "__main__":
    unittest.main()
