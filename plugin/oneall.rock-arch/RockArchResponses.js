.pragma library
.import "RockArchAccountResponses.js" as Account
.import "RockArchSearchResponses.js" as Search
.import "RockArchMagnusResponses.js" as Magnus

// Preserve ordering: one broker response can carry several related updates.
function accept(root, ui, line) {
    var response
    try { response = JSON.parse(line) } catch (e) {
      root.finishSetup()
      root.onboardingInProgress = false
      root.onboardingSetupPending = false
      root.searchInFlight = false
      root.searchPending = false
      root.searchInFlightQuery = ""
      root.knowledgeBusy = false
      root.knowledgeSearchInFlight = false
      root.knowledgeSearchPending = false
      root.knowledgeSearchInFlightQuery = ""
      root.magnusActionBusy = false
      root.feedbackText = "Rock Arch couldn't read Rock's response. Try again."
      return
    }
    if (response && response.shortcut) {
      root.shortcut.accept(response.shortcut)
      return
    }
    if (!response || response.ok !== true) {
      var onboardingSetupFailed = root.onboardingSetupPending
      root.onboardingSetupPending = false
      root.finishSetup()
      root.onboardingInProgress = false
      root.searchInFlight = false
      root.searchPending = false
      root.searchInFlightQuery = ""
      root.knowledgeBusy = false
      root.knowledgeSearchInFlight = false
      root.knowledgeSearchPending = false
      root.knowledgeSearchInFlightQuery = ""
      if (root.pendingKnowledgeNavigation && root.knowledgeHistory.length)
        root.knowledgeHistory = root.knowledgeHistory.slice(0, root.knowledgeHistory.length - 1)
      root.pendingKnowledgeNavigation = false
      root.magnusBusy = false
      root.magnusActionBusy = false
      root.magnusProbeInFlight = false
      if (root.magnusState === "checking") root.magnusState = "error"
      root.pendingSuccessText = ""
      root.feedbackText = root.friendlyError(response && response.error ? response.error : "")
      if (onboardingSetupFailed)
        Qt.callLater(function() { ui.finishSetupPanel.primaryButton.forceActiveFocus(Qt.TabFocusReason) })
      return
    }
    var frame = Search.begin(root, response)
    Account.context(root, ui, response, frame)
    Magnus.status(root, ui, response, frame)
    Account.update(root, ui, response, frame)
    Magnus.content(root, ui, response, frame)
    if (response.uiHandoff) root.applyUiHandoff(response.uiHandoff)
    Search.knowledgeDetail(root, ui, response, frame)
    Account.profiles(root, ui, response, frame)
    Account.capabilities(root, ui, response, frame)
    Account.terminal(root, ui, response, frame)
    Account.status(root, ui, response, frame)
    Search.results(root, ui, response, frame)
    Search.knowledgeResults(root, ui, response, frame)
    Search.links(root, ui, response, frame)
    Account.refresh(root, ui, response, frame)
    Account.connection(root, ui, response, frame)
    feedback(root, ui, response, frame)
    Search.knowledgeFeedback(root, ui, response, frame)
    if (frame.staleSearch) Qt.callLater(function() { root.refreshSearch() })
    if (frame.staleKnowledgeSearch) Qt.callLater(function() { root.refreshKnowledgeSearch() })
}

function feedback(root, ui, response, frame) {
    if (!frame.staleSearch && Array.isArray(response.unavailable) && response.unavailable.length)
      root.feedbackText = "Couldn't search " + response.unavailable.join(", ") + "."
    else if (response.opened === true) {
      root.magnusActionBusy = false
      root.feedbackText = root.preferenceRecentLinks ? "Opened in Rock and added to Recent Links" : "Opened in Rock"
      if (root.preferenceCloseAfterOpen) Qt.callLater(function() { root.close() })
    }
    else if (response.previewAction) {
      root.knowledgeBusy = false
      root.magnusActionBusy = false
      root.feedbackText = String(response.previewAction)
    }
    else if (response.source === "unavailable" && !frame.staleSearch)
      root.feedbackText = "Live Rock search needs a saved Rock login"
    else if (response.source === "knowledge_unavailable" && !frame.staleSearch)
      root.feedbackText = "Rock Knowledge isn't available right now. Try again when you're online."
    else if (response.source === "not_authorized" && !frame.staleSearch)
      root.feedbackText = "This Rock account can't search " + (root.scopeLabel || "that category") + "."
    else if (response.source === "access_check_failed" && !frame.staleSearch)
      root.feedbackText = "Rock Arch couldn't check what this account can search."
    else if (response.source && !frame.staleSearch)
      root.feedbackText = ""
}
