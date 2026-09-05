.pragma library

// Explicit controller and UI dependencies keep response transitions testable.

function knowledgeDetail(root, ui, response, frame) {
    if (response.knowledgeDetail) {
      root.knowledgeBusy = false
      root.pendingKnowledgeNavigation = false
      root.knowledgeDetail = response.knowledgeDetail
      root.knowledgeLinkCursor = -1
      root.feedbackText = ""
      ui.panelFlick.contentY = 0
      Qt.callLater(function() {
        if (root.viewMode !== "knowledge" || root.knowledgeDetail === null) return
        ui.knowledgePanel.backButton.forceActiveFocus(Qt.TabFocusReason)
        root.revealFocusedControl(ui.knowledgePanel.backButton)
      })
    }
}

function results(root, ui, response, frame) {
    if (frame.isSearchResponse && !frame.staleSearch) {
      var selectedSafeId = frame.completedSearchQuery === root.resultsQuery && root.resultCursor >= 0 &&
        root.resultCursor < root.results.length ? String(root.results[root.resultCursor].safeId || "") : ""
      root.results = response.results
      var preservedCursor = selectedSafeId ? root.results.findIndex(function(item) {
        return String(item.safeId || "") === selectedSafeId
      }) : -1
      root.resultCursor = preservedCursor >= 0 ? preservedCursor : (root.results.length ? 0 : -1)
      root.resultsQuery = frame.completedSearchQuery
      root.recentCursor = -1
      if (preservedCursor < 0) ui.panelFlick.contentY = 0
      Qt.callLater(function() {
        if (root.viewMode === "search" && root.resultCursor >= 0)
          root.revealItem(ui.searchPanel.resultRepeater.itemAt(root.resultCursor))
      })
    }
}

function knowledgeResults(root, ui, response, frame) {
    if (frame.isKnowledgeSearchResponse && !frame.staleKnowledgeSearch) {
      root.knowledgeResults = response.knowledgeResults
      root.knowledgeCursor = root.knowledgeResults.length ? 0 : -1
      root.knowledgeLinkCursor = -1
      ui.panelFlick.contentY = 0
      Qt.callLater(function() {
        if (root.viewMode === "knowledge" && root.knowledgeCursor >= 0)
          root.revealItem(ui.knowledgePanel.resultRepeater.itemAt(root.knowledgeCursor))
      })
    }
}

function links(root, ui, response, frame) {
    if (Array.isArray(response.personalLinks)) root.personalLinks = response.personalLinks
    if (Array.isArray(response.quickReturns)) {
      root.quickReturns = response.quickReturns
      if (root.showRecentLinks) {
        root.recentCursor = root.quickReturns.length ? 0 : -1
        root.resultCursor = -1
      } else if (root.recentCursor >= root.quickReturns.length) {
        root.recentCursor = root.quickReturns.length - 1
      }
    }
    if (root.linkCursor >= root.navigationCount) root.linkCursor = root.navigationCount - 1
    if (root.viewMode === "personal" && root.linkCursor < 0 && root.navigationCount) root.linkCursor = 0
    if (root.viewMode === "personal" && root.linkCursor >= 0)
      Qt.callLater(function() { root.revealItem(ui.personalPanel.repeater.itemAt(root.linkCursor)) })
    if (response.personalLinksAvailable !== undefined)
      root.personalLinksAvailable = response.personalLinksAvailable === true
    if (response.person) root.quickLook = response.person
    if (response.source && !frame.staleSearch) root.searchSource = String(response.source)
}

function knowledgeFeedback(root, ui, response, frame) {
    if (response.knowledgeOpened === true) {
      root.knowledgeBusy = false
      root.feedbackText = "Opened the knowledge source"
    }
    if (response.knowledgeSource === "unavailable" && !frame.staleKnowledgeSearch)
      root.feedbackText = "Rock Knowledge isn't available right now. Try again when you're online."
    else if ((response.knowledgeSource === "public" ||
             response.knowledgeSource === "preview") && !frame.staleKnowledgeSearch)
      root.feedbackText = ""
}

function begin(root, response) {
    var isStatusResponse = response.categories !== undefined && response.rock !== undefined
    var isSearchResponse = Array.isArray(response.results)
    var isKnowledgeSearchResponse = Array.isArray(response.knowledgeResults)
    var completedSearchQuery = isSearchResponse ? root.searchInFlightQuery : ""
    var staleSearch = isSearchResponse && root.searchInFlight &&
      (root.searchPending || root.query !== root.searchInFlightQuery)
    var staleKnowledgeSearch = isKnowledgeSearchResponse && root.knowledgeSearchInFlight &&
      (root.knowledgeSearchPending || root.knowledgeQuery !== root.knowledgeSearchInFlightQuery)
    if (isSearchResponse) {
      root.searchInFlight = false
      root.searchPending = false
      root.searchInFlightQuery = ""
    }
    if (isKnowledgeSearchResponse) {
      root.knowledgeSearchInFlight = false
      root.knowledgeSearchPending = false
      root.knowledgeSearchInFlightQuery = ""
    }
    return {
        completedSearchQuery: completedSearchQuery,
        isKnowledgeSearchResponse: isKnowledgeSearchResponse,
        isSearchResponse: isSearchResponse,
        isStatusResponse: isStatusResponse,
        staleKnowledgeSearch: staleKnowledgeSearch,
        staleSearch: staleSearch
    }
}
