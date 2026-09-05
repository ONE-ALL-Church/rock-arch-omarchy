import QtQuick
import QtTest
import "../../plugin/oneall.rock-arch/RockArchResponses.js" as Responses

TestCase {
  name: "BrokerResponses"
  property var state
  property var ui
  property var calls

  function init() {
    calls = []
    state = {
      contextName: "PROD", viewMode: "search", opened: true,
      query: "", results: [], resultsQuery: "", resultCursor: -1, recentCursor: -1,
      searchInFlight: false, searchPending: false, searchInFlightQuery: "",
      knowledgeQuery: "", knowledgeResults: [], knowledgeHistory: [], knowledgeDetail: null,
      knowledgeSearchInFlight: false, knowledgeSearchPending: false, knowledgeSearchInFlightQuery: "",
      knowledgeBusy: false, pendingKnowledgeNavigation: false,
      quickReturns: [], showRecentLinks: false, linkCursor: -1, navigationCount: 0,
      profiles: [], activeProfileId: "", newProfileName: "", newProfileDomain: "",
      rockConfigured: true, searchCapabilitiesReady: true, searchCapabilitiesInFlight: false,
      availableSearchCategories: ["People"], searchCapabilitiesState: "ready",
      magnusState: "ready", magnusBusy: false, magnusActionBusy: false,
      showMagnus: true, magnusItems: [], magnusCursor: -1,
      onboardingInProgress: false, onboardingSetupPending: false,
      finishSetupOnboardingRequired: false, onboardingFlowActive: false,
      preferenceRecentLinks: true, preferenceCloseAfterOpen: true,
      setupPassword: "", pendingSuccessText: "", feedbackText: "", currentVersion: "test",
      finishSetup: function() { this.setupBusy = false; calls.push("finishSetup") },
      resetSearchCapabilities: function() {
        this.searchCapabilitiesState = "unknown"
        this.availableSearchCategories = []
        calls.push("resetCapabilities")
      },
      refreshSearch: function() { calls.push("refreshSearch") },
      refreshKnowledgeSearch: function() { calls.push("refreshKnowledge") },
      refreshQuickReturns: function() { calls.push("refreshRecent") },
      refreshPersonalLinks: function() { calls.push("refreshPersonal") },
      probeSearchCapabilities: function() { calls.push("probeCapabilities") },
      initializeOnboardingSetup: function() { calls.push("initializeOnboarding") },
      activeProfileName: function() { return "Synthetic profile" },
      focusSearch: function() { this.viewMode = "search"; calls.push("focusSearch") },
      revealItem: function(item) { calls.push("reveal:" + item.index) },
      revealFocusedControl: function() { calls.push("revealControl") },
      request: function(payload) { calls.push(payload.op) },
      close: function() { calls.push("close") },
      friendlyError: function() { return "Safe error" },
      applyUiHandoff: function() { calls.push("handoff") }
    }
    function focusable(name) {
      return {forceActiveFocus: function() { calls.push("focus:" + name) }}
    }
    var repeater = {itemAt: function(index) { return {index: index} }}
    ui = {
      panelFlick: {contentY: 80}, keyCatcher: focusable("keys"),
      searchField: focusable("search"), searchPanel: {resultRepeater: repeater},
      personalPanel: {repeater: repeater},
      knowledgePanel: {resultRepeater: repeater, backButton: focusable("knowledgeBack")},
      magnusPanel: {repeater: repeater, previewPrimaryButton: focusable("magnusPreview")},
      onboardingForm: {profileNameField: focusable("profileName")},
      finishSetupPanel: {primaryButton: focusable("finishSetup")},
      magnusProbeTimer: {restart: function() { calls.push("probeMagnus") }}
    }
  }

  function accept(response) {
    Responses.accept(state, ui, JSON.stringify(response))
    wait(1) // Run the real Qt.callLater focus and refresh callbacks.
  }

  function test_stale_search_never_replaces_current_results() {
    state.query = "new"
    state.searchInFlightQuery = "old"
    state.searchInFlight = true
    state.searchPending = true
    state.results = [{safeId: "current"}]
    state.feedbackText = "current feedback"
    accept({ok: true, results: [{safeId: "stale"}], source: "unavailable"})
    compare(state.results, [{safeId: "current"}])
    compare(state.feedbackText, "current feedback")
    compare(state.searchInFlight, false)
    verify(calls.indexOf("refreshSearch") >= 0)
  }

  function test_shortcut_error_stays_local_to_shortcut_controls() {
    state.setupBusy = true
    state.onboardingSetupPending = true
    state.shortcut = {accept: function(value) { calls.push(value.error) }}
    accept({ok: true, shortcut: {state: "conflict", error: "shortcut_conflict"}})
    compare(calls, ["shortcut_conflict"])
    verify(state.setupBusy)
    verify(state.onboardingSetupPending)
    compare(state.feedbackText, "")
  }

  function test_refresh_preserves_selected_record_after_reordering() {
    state.query = state.resultsQuery = state.searchInFlightQuery = "query"
    state.searchInFlight = true
    state.results = [{safeId: "first"}, {safeId: "selected"}]
    state.resultCursor = 1
    accept({ok: true, results: [{safeId: "selected"}, {safeId: "first"}]})
    compare(state.resultCursor, 0)
    compare(state.resultsQuery, "query")
    compare(ui.panelFlick.contentY, 80)
    verify(calls.indexOf("reveal:0") >= 0)
  }

  function test_new_query_selects_first_result_and_resets_scroll() {
    state.query = state.searchInFlightQuery = "new"
    state.resultsQuery = "old"
    state.searchInFlight = true
    state.resultCursor = 1
    accept({ok: true, results: [{safeId: "new-first"}]})
    compare(state.resultCursor, 0)
    compare(state.resultsQuery, "new")
    compare(ui.panelFlick.contentY, 0)
    compare(state.recentCursor, -1)
  }

  function test_stale_knowledge_retries_without_replacing_results() {
    state.viewMode = "knowledge"
    state.knowledgeQuery = "new"
    state.knowledgeSearchInFlightQuery = "old"
    state.knowledgeSearchInFlight = true
    state.knowledgeResults = [{safeId: "current"}]
    accept({ok: true, knowledgeResults: [{safeId: "old"}], knowledgeSource: "unavailable"})
    compare(state.knowledgeResults, [{safeId: "current"}])
    verify(calls.indexOf("refreshKnowledge") >= 0)
  }

  function test_profile_change_clears_previous_permissions() {
    state.activeProfileId = "previous"
    accept({ok: true, profiles: {activeProfileId: "next", profiles: [{id: "next"}], preferences: {}}})
    compare(state.activeProfileId, "next")
    compare(state.availableSearchCategories, [])
    compare(state.preferenceAutomaticUpdates, false)
    verify(calls.indexOf("resetCapabilities") >= 0)
  }

  function test_capability_success_restarts_waiting_search() {
    state.query = "pending"
    state.searchCapabilitiesInFlight = true
    accept({ok: true, searchCapabilities: {state: "ready", availableCategories: ["Groups"]}})
    compare(state.availableSearchCategories, ["Groups"])
    compare(state.searchCapabilitiesInFlight, false)
    verify(calls.indexOf("refreshSearch") >= 0)
  }

  function test_status_applies_profile_before_final_capability_state() {
    state.activeProfileId = "old"
    state.searchCapabilitiesReady = false
    accept({
      ok: true, context: "PROD", categories: ["Groups"],
      rock: {available: true, configured: true},
      profiles: {activeProfileId: "new", profiles: [{id: "new"}], preferences: {terminalAccess: false}},
      searchCapabilities: {state: "ready", availableCategories: ["Groups"]},
      terminal: {installed: true, inPath: false},
      update: {managed: true, state: "available", currentVersion: "test", availableVersion: "next", updateAvailable: true}
    })
    compare(state.activeProfileId, "new")
    compare(state.searchCapabilitiesState, "ready")
    compare(state.availableSearchCategories, ["Groups"])
    compare(state.preferenceTerminalAccess, false)
    compare(state.terminalInstalled, true)
    compare(state.updateAvailable, true)
    compare(state.statusLoaded, true)
  }

  function test_login_refresh_clears_password_and_refreshes_views() {
    state.setupPassword = "synthetic secret"
    state.onboardingInProgress = true
    state.finishSetupOnboardingRequired = true
    state.profiles = [{id: "new"}]
    accept({ok: true, refreshLive: true})
    compare(state.setupPassword, "")
    verify(calls.indexOf("focus:finishSetup") >= 0)
    for (var action of ["refreshSearch", "refreshRecent", "refreshPersonal", "status"])
      verify(calls.indexOf(action) >= 0)
  }

  function test_update_polling_keeps_status_out_of_the_footer() {
    for (var updateState of ["checking", "current", "available", "updating", "updated",
                            "error", "modified", "diverged", "manual"]) {
      accept({ok: true, update: {managed: true, state: updateState}})
      compare(state.updateState, updateState)
      compare(state.feedbackText, "", updateState)
    }
  }

  function test_update_polling_preserves_unrelated_feedback() {
    state.feedbackText = "Connection successful"
    for (var updateState of ["checking", "current", "updating", "updated", "error"]) {
      accept({ok: true, update: {managed: true, state: updateState}})
      compare(state.updateState, updateState)
      compare(state.feedbackText, "Connection successful", updateState)
    }
  }

  function test_recent_links_select_first_and_knowledge_detail_gets_focus() {
    state.showRecentLinks = true
    accept({ok: true, quickReturns: [{safeId: "recent-first"}]})
    compare(state.recentCursor, 0)
    compare(state.resultCursor, -1)
    state.viewMode = "knowledge"
    state.pendingKnowledgeNavigation = true
    accept({ok: true, knowledgeDetail: {title: "Public fixture", links: []}})
    compare(state.pendingKnowledgeNavigation, false)
    compare(state.knowledgeDetail.title, "Public fixture")
    verify(calls.indexOf("focus:knowledgeBack") >= 0)
  }

  function test_failed_knowledge_navigation_restores_history() {
    state.pendingKnowledgeNavigation = true
    state.knowledgeBusy = true
    state.knowledgeHistory = [{safeId: "parent"}, {safeId: "failed"}]
    accept({ok: false, error: "private backend detail"})
    compare(state.knowledgeHistory, [{safeId: "parent"}])
    compare(state.knowledgeBusy, false)
    compare(state.feedbackText, "Safe error")
  }

  function test_malformed_response_releases_busy_state() {
    state.setupBusy = state.searchInFlight = state.knowledgeSearchInFlight = true
    Responses.accept(state, ui, "not JSON")
    compare(state.setupBusy, false)
    compare(state.searchInFlight, false)
    compare(state.knowledgeSearchInFlight, false)
    verify(state.feedbackText.length > 0)
  }

  function test_magnus_preview_focus_and_build_acceptance() {
    state.viewMode = "magnus"
    state.magnusBusy = true
    accept({ok: true, magnusPreview: {content: "synthetic text"}})
    compare(state.magnusBusy, false)
    verify(calls.indexOf("focus:magnusPreview") >= 0)
    state.magnusActionBusy = true
    state.pendingMagnusBuildId = "opaque-app"
    accept({ok: true, magnusBuild: {message: "Build request accepted", previewOnly: true}})
    compare(state.pendingMagnusBuildId, "")
    compare(state.magnusActionBusy, false)
    compare(state.feedbackText, "Build request accepted")
    verify(calls.indexOf("magnus_build") === -1)
  }

  function test_sign_out_clears_form_and_open_respects_close_preference() {
    state.setupPassword = "synthetic secret"
    accept({ok: true, connection: "signed_out"})
    compare(state.setupPassword, "")
    state.preferenceCloseAfterOpen = false
    accept({ok: true, opened: true})
    verify(calls.indexOf("close") === -1)
    state.preferenceCloseAfterOpen = true
    accept({ok: true, opened: true})
    verify(calls.indexOf("close") >= 0)
  }
}
