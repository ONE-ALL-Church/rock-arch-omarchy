import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "oneall.rock-arch"
  ipcTarget: "oneall.rock-arch"
  manageIpc: false

  readonly property string runtimeDir: (Quickshell.env("XDG_RUNTIME_DIR") || ("/run/user/" + Quickshell.env("UID"))) + "/rock-arch"
  readonly property string socketPath: runtimeDir + "/broker.sock"
  readonly property string packageRoot: Quickshell.env("ROCK_ARCH_HOME") ||
    decodeURIComponent(Qt.resolvedUrl("../../").toString().replace(/^file:\/\//, "")).replace(/\/$/, "")
  property string contextName: "PROD"
  property bool developerMode: false
  property string viewMode: "search"
  property alias query: searchField.text
  property var results: []
  property var personalLinks: []
  property var quickReturns: []
  property var profiles: []
  property bool profilesLoaded: false
  property bool statusLoaded: false
  property string activeProfileId: ""
  property bool preferencePersonContext: true
  property bool preferenceRecentLinks: true
  property bool preferenceCloseAfterOpen: true
  property bool preferenceAutomaticUpdates: false
  property bool updateManaged: false
  property string updateState: "idle"
  property string currentVersion: "0.15.0"
  property string availableVersion: ""
  property string updateLastCheckedAt: ""
  property string updateLastUpdatedAt: ""
  property string updateError: ""
  property bool updateAvailable: false
  property var enabledCategories: ["People", "Groups", "Workflows", "Jobs", "Pages", "Content Channel Items"]
  property var quickLook: null
  property var requestQueue: []
  property string searchSource: "synthetic"
  property string feedbackText: ""
  property string instanceDomain: ""
  property string setupUsername: ""
  property string setupPassword: ""
  property string newProfileName: ""
  property string newProfileDomain: ""
  property bool addProfileMode: false
  property string pendingRemoveProfileId: ""
  property bool pendingSignOut: false
  property bool pendingClearRecent: false
  property bool editLoginMode: false
  property string pendingSuccessText: ""
  property bool rockAvailable: false
  property bool rockConfigured: false
  property bool magnusAvailable: false
  property string magnusState: "unknown"
  property bool magnusProbeInFlight: false
  property var magnusItems: []
  property var magnusPreview: null
  property var magnusHistory: []
  property string magnusFolderId: ""
  property string magnusFolderTitle: "Magnus"
  property int magnusCursor: -1
  property bool magnusBusy: false
  property bool magnusActionBusy: false
  property string pendingMagnusBuildId: ""
  property string pendingMagnusBuildTitle: ""
  property bool pendingMagnusBuildRecent: false
  property bool personalLinksAvailable: false
  property bool setupBusy: false
  property bool setupSlow: false
  property bool onboardingInProgress: false
  property string setupBusyText: "Working…"
  property bool searchInFlight: false
  property bool searchPending: false
  property string searchInFlightQuery: ""
  property int resultCursor: -1
  property int recentCursor: -1
  property int linkCursor: -1
  property int relativeTimeTick: 0
  readonly property int navigationCount: personalLinks.length
  readonly property int magnusCount: magnusItems.length
  readonly property bool showMagnus: contextName === "PROD" && magnusAvailable
  readonly property bool updateBusy: updateState === "checking" || updateState === "updating"
  readonly property bool magnusPreviewCommandsEnabled: opened && viewMode === "magnus" &&
    magnusPreview !== null && !magnusBusy && !magnusActionBusy && pendingMagnusBuildId === ""
  readonly property bool onboardingRequired: contextName === "PROD" &&
    statusLoaded && profilesLoaded && !rockConfigured
  readonly property bool queryIsEmpty: query.trim().length === 0
  readonly property bool showRecentLinks: viewMode === "search" && queryIsEmpty
  readonly property int activeSearchCount: queryIsEmpty ? quickReturns.length : results.length
  readonly property string scopeKey: scopeKeyForQuery(query)
  readonly property string scopeLabel: scopeLabelForKey(scopeKey)
  readonly property bool scopeShortcutsEnabled: opened && viewMode === "search" &&
    !onboardingForm.inputActive && !settingsPanel.inputActive
  readonly property string connectionText: contextName === "DEV" ? "Preview data" :
    rockConfigured ? (activeProfileName() === instanceDomain ? "Connected · " + instanceDomain : activeProfileName() + " · " + instanceDomain) :
    rockAvailable ? (activeProfileId ? activeProfileName() + " · login required" : "Rock profile required") : "Secure password storage unavailable"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function request(payload) {
    var next = []
    var coalesce = payload.op === "search" || payload.op === "status" || payload.op === "navigation_status"
    for (var index = 0; index < requestQueue.length; index++) {
      var queued = requestQueue[index]
      var sameNavigationSection = payload.op !== "navigation_status" || queued.section === payload.section
      if (!coalesce || queued.op !== payload.op || !sameNavigationSection) next.push(queued)
    }
    requestQueue = next.concat([payload])
    if (brokerSocket.connected) flushRequests()
    else brokerReconnectTimer.restart()
  }

  function isCredentialRequest(payload) {
    return payload && (payload.op === "rock_configure" ||
      payload.op === "profile_add" ||
      payload.op === "profile_credentials_update")
  }

  function dropQueuedCredentialRequests() {
    var retained = []
    for (var index = 0; index < requestQueue.length; index++)
      if (!isCredentialRequest(requestQueue[index])) retained.push(requestQueue[index])
    requestQueue = retained
    setupPassword = ""
  }

  function flushRequests() {
    if (!brokerSocket.connected || !requestQueue.length) return
    while (brokerSocket.connected && requestQueue.length) {
      var payload = requestQueue[0]
      requestQueue = requestQueue.slice(1)
      brokerSocket.write(JSON.stringify(payload) + "\n")
    }
    brokerSocket.flush()
  }

  function scopeKeyForQuery(value) {
    var text = String(value || "")
    var colon = text.indexOf(":")
    if (colon < 1) return ""
    var prefix = text.substring(0, colon).trim().toLowerCase()
    if (prefix === "p" || prefix === "person" || prefix === "people") return "p"
    if (prefix === "g" || prefix === "group" || prefix === "groups") return "g"
    if (prefix === "w" || prefix === "wt" || prefix === "workflow" ||
        prefix === "workflows" || prefix === "workflowtype" ||
        prefix === "workflowtypes") return "w"
    if (prefix === "j" || prefix === "job" || prefix === "jobs") return "j"
    if (prefix === "pg" || prefix === "page" || prefix === "pages") return "page"
    if (prefix === "c" || prefix === "content" || prefix === "contents" ||
        prefix === "item" || prefix === "items") return "c"
    return ""
  }

  function activeProfileName() {
    for (var index = 0; index < profiles.length; index++)
      if (profiles[index].id === activeProfileId) return String(profiles[index].name || "Rock")
    return "Rock"
  }

  function normalizedBuildTitle(value) {
    return String(value || "").replace(/^Deploy /, "").trim().toLowerCase()
  }

  function lastDeployedAt(title) {
    var expected = normalizedBuildTitle(title)
    for (var index = 0; index < quickReturns.length; index++) {
      var item = quickReturns[index]
      if (item.kind === "Magnus Build" && normalizedBuildTitle(item.title) === expected)
        return String(item.lastUsedAt || "")
    }
    return ""
  }

  function relativeTime(value) {
    var tick = relativeTimeTick
    var timestamp = Date.parse(String(value || ""))
    if (isNaN(timestamp)) return ""
    var seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000))
    if (seconds < 45) return "just now"
    if (seconds < 90) return "1 minute ago"
    if (seconds < 3600) return Math.floor(seconds / 60) + " minutes ago"
    if (seconds < 7200) return "1 hour ago"
    if (seconds < 86400) return Math.floor(seconds / 3600) + " hours ago"
    if (seconds < 172800) return "yesterday"
    if (seconds < 604800) return Math.floor(seconds / 86400) + " days ago"
    var deployed = new Date(timestamp)
    return deployed.getFullYear() === new Date().getFullYear() ?
      Qt.formatDateTime(deployed, "MMM d, h:mm AP") :
      Qt.formatDateTime(deployed, "MMM d, yyyy, h:mm AP")
  }

  function deploymentSummary(title) {
    var deployedAt = lastDeployedAt(title)
    return deployedAt ? "Last deployed " + relativeTime(deployedAt) : "No Rock Arch deployment recorded"
  }

  function friendlyError(value) {
    var code = String(value || "")
    if (code === "rock_login_failed" || code === "rock_login_required")
      return "Rock couldn't sign in. Check the saved login and try again."
    if (code === "magnus_unavailable_for_user")
      return "Magnus isn't available for this Rock account."
    if (code === "magnus_request_failed")
      return "Magnus couldn't complete that request. Try again."
    if (code === "build_confirmation_required")
      return "Confirm the deployment before it starts."
    if (code === "magnus_build_failed")
      return "Magnus couldn't start the deployment. Try again."
    if (code === "clipboard_unavailable")
      return "The clipboard isn't available right now."
    if (code === "recent_links_clear_failed")
      return "Recent Links couldn't be cleared from this computer. Try again."
    if (code === "no_update_available")
      return "Rock Arch is already up to date."
    if (code === "local_changes_prevent_update")
      return "Local plugin changes must be committed or removed before updating."
    if (code === "update_history_diverged")
      return "This installation has a different Git history and must be updated manually."
    if (code === "update_managed_manually")
      return "Updates for this installation are managed manually."
    if (code === "update_launch_failed" || code === "update_failed")
      return "Rock Arch couldn't install the update. Try again from Settings."
    if (code === "update_check_failed" || code === "update_interrupted")
      return "Rock Arch couldn't check for updates. Try again when you're online."
    if (code === "not_found" || code === "magnus_item_not_found")
      return "That item is no longer available. Refresh and try again."
    if (!code) return "That action didn't finish. Try again."
    var message = code.split("_").join(" ")
    return message.charAt(0).toUpperCase() + message.slice(1) + "."
  }

  function guidanceText() {
    if (setupBusy)
      return setupSlow ? setupBusyText + " Rock is taking longer than usual." : setupBusyText
    if (pendingClearRecent)
      return "Press Enter to clear Recent Links, or Esc to cancel."
    if ((contextName === "DEV" || rockConfigured) && searchInFlight)
      return "Looking for matches…"
    if (!statusLoaded) return "Getting your Rock workspace ready…"
    if (contextName === "PROD" && !rockConfigured)
      return "Sign in from Settings to search Rock."
    if (viewMode === "settings")
      return updateState === "updating" ?
        "The update is running through Omarchy. Rock Arch will restart when it finishes." :
        "Changes save automatically. Press Esc to return to Search."
    if (viewMode === "personal")
      return personalLinks.length ?
        "Use Up/Down to choose a Personal Link. Enter opens it in Rock." :
        (showMagnus ?
          "Press Tab for Magnus; Shift+Tab returns to Search." :
          "Press Tab for Settings; Shift+Tab returns to Search.")
    if (viewMode === "magnus") {
      if (pendingMagnusBuildId !== "")
        return "Press Enter to deploy, or Esc to cancel."
      if (magnusPreview)
        return "D downloads · C copies · H copies the hash · O opens in Rock · R refreshes"
      if (magnusCursor >= 0 && magnusCursor < magnusItems.length) {
        var item = magnusItems[magnusCursor]
        if (item.actions && item.actions.indexOf("build") >= 0)
          return "Press B to prepare this deployment, then Enter to confirm."
      }
      return "Use Up/Down to choose an item. Enter opens it; R refreshes."
    }
    if (scopeKey)
      return "Showing " + scopeLabel + " only. Esc returns to all categories."
    if (showRecentLinks)
      return quickReturns.length ?
        "Start typing to search, or use Up/Down and Enter to open a recent item. X or Delete clears the list." :
        (contextName === "PROD" ?
          "Start typing to search Rock. Opened items will appear here." :
          "Start typing to search preview data.")
    return "Narrow results with p:, g:, w:, j:, pg:, or c:. Any ID or GUID checks every category."
  }

  function categoryEnabled(category) {
    return enabledCategories.indexOf(category) >= 0
  }

  function displayCategory(category) {
    return category === "Workflows" ? "Workflow Types" : category
  }

  function toggleCategory(category) {
    var next = []
    for (var index = 0; index < enabledCategories.length; index++)
      if (enabledCategories[index] !== category) next.push(enabledCategories[index])
    if (!categoryEnabled(category)) next.push(category)
    enabledCategories = next
    request({op: "preferences_update", preferences: {enabledCategories: next}})
    if (viewMode === "search") scheduleSearch()
  }

  function scopeLabelForKey(key) {
    if (key === "p") return "People"
    if (key === "g") return "Groups"
    if (key === "w") return "Workflow Types"
    if (key === "j") return "Jobs"
    if (key === "page") return "Pages"
    if (key === "c") return "Content"
    return ""
  }

  function queryWithoutScope(value) {
    var text = String(value || "")
    if (!scopeKeyForQuery(text)) return text.trim()
    return text.substring(text.indexOf(":") + 1).trim()
  }

  function applyScope(key) {
    var term = scopeKey ? queryWithoutScope(query) : query.trim()
    viewMode = "search"
    query = key + ":" + (term ? " " + term : "")
    resultCursor = -1
    recentCursor = -1
    linkCursor = -1
    quickLook = null
    feedbackText = ""
    panelFlick.contentY = 0
    scheduleSearch()
    Qt.callLater(function() {
      searchField.cursorPosition = searchField.text.length
      searchField.forceActiveFocus()
    })
  }

  function clearScope() {
    if (!scopeKey) return false
    query = queryWithoutScope(query)
    resultCursor = -1
    recentCursor = -1
    quickLook = null
    feedbackText = ""
    scheduleSearch()
    if (query.trim().length === 0) refreshQuickReturns()
    Qt.callLater(function() {
      searchField.cursorPosition = searchField.text.length
      searchField.forceActiveFocus()
    })
    return true
  }

  function escapePanel() {
    if (onboardingRequired) {
      close()
      return
    }
    if (pendingMagnusBuildId !== "" && !magnusActionBusy) {
      cancelMagnusBuild()
      return
    }
    if (pendingClearRecent) {
      pendingClearRecent = false
      feedbackText = "Clear cancelled"
      focusSearch()
      return
    }
    if (viewMode === "settings") {
      focusSearch()
      return
    }
    if (viewMode === "magnus" && (magnusPreview !== null || magnusHistory.length > 0)) {
      magnusBack()
      return
    }
    if (!clearScope()) close()
  }

  function accept(line) {
    var response
    try { response = JSON.parse(line) } catch (e) {
      finishSetup()
      onboardingInProgress = false
      searchInFlight = false
      searchPending = false
      searchInFlightQuery = ""
      magnusActionBusy = false
      feedbackText = "Rock Arch couldn't read Rock's response. Try again."
      return
    }
    if (!response || response.ok !== true) {
      finishSetup()
      onboardingInProgress = false
      searchInFlight = false
      searchPending = false
      searchInFlightQuery = ""
      magnusBusy = false
      magnusActionBusy = false
      magnusProbeInFlight = false
      if (magnusState === "checking") magnusState = "error"
      pendingSuccessText = ""
      feedbackText = friendlyError(response && response.error ? response.error : "")
      return
    }
    var isStatusResponse = response.categories !== undefined && response.rock !== undefined
    var isSearchResponse = Array.isArray(response.results)
    var staleSearch = isSearchResponse && searchInFlight &&
      (searchPending || query !== searchInFlightQuery)
    if (isSearchResponse) {
      searchInFlight = false
      searchPending = false
      searchInFlightQuery = ""
    }
    if (response.context && !staleSearch)
      contextName = response.context === "PROD" ? "PROD" : "DEV"
    if (response.developerMode !== undefined)
      developerMode = response.developerMode === true
    if (response.instance)
      instanceDomain = String(response.instance.origin || "").replace("https://", "")
    if (response.rock) {
      rockAvailable = response.rock.available === true
      rockConfigured = response.rock.configured === true
    }
    if (response.magnus) {
      magnusAvailable = response.magnus.available === true
      magnusState = String(response.magnus.state || "unknown")
      magnusProbeInFlight = false
      if (!showMagnus && viewMode === "magnus") focusSearch()
    }
    if (response.update) {
      updateManaged = response.update.managed === true
      updateState = String(response.update.state || "idle")
      currentVersion = String(response.update.currentVersion || currentVersion)
      availableVersion = String(response.update.availableVersion || "")
      updateLastCheckedAt = String(response.update.lastCheckedAt || "")
      updateLastUpdatedAt = String(response.update.lastUpdatedAt || "")
      updateError = String(response.update.error || "")
      updateAvailable = response.update.updateAvailable === true
      if (updateState === "updated")
        feedbackText = "Rock Arch was updated successfully"
      else if (updateState === "updating")
        feedbackText = "Updating Rock Arch through Omarchy…"
    }
    if (response.magnusBrowser) {
      magnusBusy = false
      magnusPreview = null
      magnusFolderId = String(response.magnusBrowser.folderId || "")
      magnusFolderTitle = String(response.magnusBrowser.title || "Magnus")
      magnusItems = Array.isArray(response.magnusBrowser.items) ? response.magnusBrowser.items : []
      magnusCursor = magnusItems.length ? 0 : -1
      panelFlick.contentY = 0
      Qt.callLater(function() {
        if (root.viewMode !== "magnus") return
        keyCatcher.forceActiveFocus()
        if (root.magnusCursor >= 0)
          root.revealItem(magnusPanel.repeater.itemAt(root.magnusCursor))
      })
    }
    if (response.magnusPreview) {
      magnusBusy = false
      magnusPreview = response.magnusPreview
      panelFlick.contentY = 0
      Qt.callLater(function() {
        if (root.viewMode !== "magnus" || root.magnusPreview === null) return
        magnusPanel.previewPrimaryButton.forceActiveFocus(Qt.TabFocusReason)
        root.revealFocusedControl(magnusPanel.previewPrimaryButton)
      })
    }
    if (response.magnusDownload) {
      magnusActionBusy = false
      feedbackText = "Saved " + response.magnusDownload.savedAs + " to Downloads"
    }
    if (response.magnusCopied) {
      magnusActionBusy = false
      feedbackText = response.magnusCopied.value === "hash" ? "SHA-256 copied" : "File contents copied"
    }
    if (response.magnusBuild) {
      magnusActionBusy = false
      pendingMagnusBuildId = ""
      pendingMagnusBuildTitle = ""
      pendingMagnusBuildRecent = false
      feedbackText = String(response.magnusBuild.message || "Build started successfully") +
        (preferenceRecentLinks ? " · Added to Recent Links" : "")
      Qt.callLater(function() { keyCatcher.forceActiveFocus() })
    }
    if (response.profiles) {
      profilesLoaded = true
      activeProfileId = String(response.profiles.activeProfileId || "")
      profiles = Array.isArray(response.profiles.profiles) ? response.profiles.profiles : []
      var preferences = response.profiles.preferences || {}
      preferencePersonContext = preferences.showPersonContext !== false
      preferenceRecentLinks = preferences.recentLinks !== false
      preferenceCloseAfterOpen = preferences.closeAfterOpen === true
      preferenceAutomaticUpdates = preferences.automaticUpdates === true
      if (Array.isArray(preferences.enabledCategories))
        enabledCategories = preferences.enabledCategories
      if (profiles.length === 0 && opened) {
        viewMode = "settings"
        addProfileMode = false
      }
      if (contextName === "PROD" && !rockConfigured && opened) {
        viewMode = "settings"
        addProfileMode = false
        editLoginMode = false
        if (instanceDomain && newProfileDomain.trim().length === 0)
          newProfileDomain = instanceDomain
        Qt.callLater(function() { onboardingForm.domainField.forceActiveFocus() })
      }
    }
    if (isStatusResponse) {
      statusLoaded = true
      if (contextName === "PROD" && !rockConfigured) {
        searchInFlight = false
        searchPending = false
        searchInFlightQuery = ""
      } else if (query.trim().length > 0) {
        Qt.callLater(function() { root.refreshSearch() })
      }
      if (contextName === "PROD" && rockConfigured &&
          (magnusState === "unknown" || magnusState === "error"))
        Qt.callLater(function() { root.probeMagnus() })
    }
    if (isSearchResponse && !staleSearch) {
      results = response.results
      resultCursor = results.length ? 0 : -1
      recentCursor = -1
      panelFlick.contentY = 0
      Qt.callLater(function() {
        if (root.viewMode === "search" && root.resultCursor >= 0)
          root.revealItem(searchPanel.resultRepeater.itemAt(root.resultCursor))
      })
    }
    if (Array.isArray(response.personalLinks)) personalLinks = response.personalLinks
    if (Array.isArray(response.quickReturns)) {
      quickReturns = response.quickReturns
      if (showRecentLinks) {
        recentCursor = quickReturns.length ? 0 : -1
        resultCursor = -1
      } else if (recentCursor >= quickReturns.length) {
        recentCursor = quickReturns.length - 1
      }
    }
    if (linkCursor >= navigationCount) linkCursor = navigationCount - 1
    if (viewMode === "personal" && linkCursor < 0 && navigationCount) linkCursor = 0
    if (viewMode === "personal" && linkCursor >= 0)
      Qt.callLater(function() { root.revealItem(personalPanel.repeater.itemAt(root.linkCursor)) })
    if (response.personalLinksAvailable !== undefined)
      personalLinksAvailable = response.personalLinksAvailable === true
    if (response.person) quickLook = response.person
    if (response.source && !staleSearch) searchSource = String(response.source)
    if (response.refreshLive === true) {
      var completedOnboarding = onboardingInProgress
      onboardingInProgress = false
      finishSetup()
      setupPassword = ""
      newProfileName = ""
      newProfileDomain = ""
      if (profiles.length > 0) addProfileMode = false
      editLoginMode = false
      pendingRemoveProfileId = ""
      pendingSignOut = false
      feedbackText = pendingSuccessText || "Rock connection updated"
      pendingSuccessText = ""
      Qt.callLater(function() {
        if (completedOnboarding) root.focusSearch()
        root.refreshSearch()
        root.refreshQuickReturns()
        root.refreshPersonalLinks()
        if (root.viewMode === "search") searchField.forceActiveFocus()
        root.request({op: "status", probeMagnus: true})
      })
    }
    if (response.connection === "connected") {
      finishSetup()
      feedbackText = "Connection successful"
      Qt.callLater(function() { root.request({op: "status", probeMagnus: true}) })
    } else if (response.connection === "signed_out") {
      finishSetup()
      onboardingInProgress = false
      pendingSignOut = false
      editLoginMode = false
      setupPassword = ""
      feedbackText = "Signed out; this profile and its local history were kept"
    }
    if (!staleSearch && Array.isArray(response.unavailable) && response.unavailable.length)
      feedbackText = "Couldn't search " + response.unavailable.join(", ") + "."
    else if (response.opened === true) {
      magnusActionBusy = false
      feedbackText = preferenceRecentLinks ? "Opened in Rock and added to Recent Links" : "Opened in Rock"
      if (preferenceCloseAfterOpen) Qt.callLater(function() { root.close() })
    }
    else if (response.source === "unavailable" && !staleSearch)
      feedbackText = "Live Rock search needs a saved Rock login"
    else if (response.source && !staleSearch)
      feedbackText = ""
    if (staleSearch) Qt.callLater(function() { root.refreshSearch() })
  }

  function refreshSearch() {
    if (contextName === "PROD" && (!statusLoaded || !rockConfigured)) {
      searchInFlight = false
      searchPending = false
      searchInFlightQuery = ""
      results = []
      return
    }
    if (searchInFlight) {
      searchPending = true
      return
    }
    searchInFlight = true
    searchPending = false
    searchInFlightQuery = query
    request({op: "search", query: query})
  }
  function scheduleSearch() { searchTimer.restart() }
  function probeMagnus() {
    if (contextName !== "PROD" || !statusLoaded || !rockConfigured || magnusProbeInFlight)
      return
    if (setupBusy || searchInFlight) {
      magnusProbeTimer.restart()
      return
    }
    magnusProbeInFlight = true
    magnusState = "checking"
    request({op: "magnus_status"})
  }
  function refreshQuickReturns() { request({op: "navigation_status", section: "quick_returns"}) }
  function refreshPersonalLinks() { request({op: "navigation_status", section: "personal"}) }
  function revealItem(item) {
    if (!item) return
    var point = item.mapToItem(body, 0, 0)
    var top = point.y
    var bottom = top + item.height
    var visibleTop = panelFlick.contentY
    var visibleBottom = visibleTop + panelFlick.height
    var maximum = Math.max(0, panelFlick.contentHeight - panelFlick.height)
    if (top < visibleTop)
      panelFlick.contentY = Math.max(0, top)
    else if (bottom > visibleBottom)
      panelFlick.contentY = Math.min(maximum, bottom - panelFlick.height)
  }
  function focusSearch() {
    viewMode = "search"
    resultCursor = -1
    recentCursor = -1
    linkCursor = -1
    quickLook = null
    pendingClearRecent = false
    panelFlick.contentY = 0
    Qt.callLater(function() { searchField.forceActiveFocus() })
  }

  function openSettings(showAdd) {
    viewMode = "settings"
    addProfileMode = showAdd === true || (profilesLoaded && profiles.length === 0)
    resultCursor = -1
    recentCursor = -1
    linkCursor = -1
    quickLook = null
    pendingRemoveProfileId = ""
    pendingSignOut = false
    pendingClearRecent = false
    editLoginMode = false
    feedbackText = ""
    panelFlick.contentY = 0
    request({op: "profiles_status"})
    request({op: "update_status"})
    Qt.callLater(function() {
      settingsPanel.primaryButton.forceActiveFocus(Qt.TabFocusReason)
      root.revealItem(settingsPanel.primaryButton)
    })
  }
  function revealFocusedControl(control) {
    if (!control || !control.activeFocus) return
    Qt.callLater(function() { root.revealItem(control) })
  }
  function togglePersonContextPreference() {
    preferencePersonContext = !preferencePersonContext
    updatePreference("showPersonContext", preferencePersonContext)
  }
  function toggleRecentLinksPreference() {
    preferenceRecentLinks = !preferenceRecentLinks
    updatePreference("recentLinks", preferenceRecentLinks)
    if (!preferenceRecentLinks) quickReturns = []
    else refreshQuickReturns()
  }
  function toggleCloseAfterOpenPreference() {
    preferenceCloseAfterOpen = !preferenceCloseAfterOpen
    updatePreference("closeAfterOpen", preferenceCloseAfterOpen)
  }
  function toggleAutomaticUpdatesPreference() {
    preferenceAutomaticUpdates = !preferenceAutomaticUpdates
    updatePreference("automaticUpdates", preferenceAutomaticUpdates)
  }
  function checkForUpdates() {
    if (!updateManaged || updateBusy) return
    updateState = "checking"
    feedbackText = "Checking for a Rock Arch update…"
    request({op: "update_check"})
  }
  function startPluginUpdate() {
    if (!updateManaged || !updateAvailable || updateBusy) return
    updateState = "updating"
    feedbackText = "Updating Rock Arch through Omarchy…"
    request({op: "update_start"})
  }
  function updateStatusText() {
    if (!updateManaged || updateState === "manual")
      return "Updates are managed manually for this installation"
    if (updateState === "checking") return "Checking for updates…"
    if (updateState === "updating") return "Installing the update through Omarchy…"
    if (updateState === "available")
      return availableVersion && availableVersion !== currentVersion ?
        availableVersion + " available" : "A new revision is available"
    if (updateState === "updated")
      return "Updated " + (updateLastUpdatedAt ? relativeTime(updateLastUpdatedAt) : "successfully")
    if (updateState === "modified")
      return "Local changes prevent automatic updates"
    if (updateState === "diverged")
      return "This Git checkout must be updated manually"
    if (updateState === "error")
      return updateError === "update_failed" ? "The last update failed" : "Couldn't check for updates"
    if (updateState === "current")
      return "Up to date" + (updateLastCheckedAt ? " · checked " + relativeTime(updateLastCheckedAt) : "")
    return "Ready to check for updates"
  }
  function backspaceToSearch() {
    var selectionStart = searchField.selectionStart
    var selectionEnd = searchField.selectionEnd
    var cursor = searchField.cursorPosition
    var changed = false

    if (selectionStart !== selectionEnd) {
      searchField.remove(selectionStart, selectionEnd)
      searchField.cursorPosition = selectionStart
      changed = true
    } else if (cursor > 0) {
      searchField.remove(cursor - 1, cursor)
      searchField.cursorPosition = cursor - 1
      changed = true
    }

    feedbackText = ""
    focusSearch()
    if (changed) {
      scheduleSearch()
      if (searchField.text.trim().length === 0) refreshQuickReturns()
    }
  }
  function selectResult(index) {
    if (!results.length) {
      focusSearch()
      return
    }
    viewMode = "search"
    resultCursor = Math.max(0, Math.min(results.length - 1, index))
    recentCursor = -1
    linkCursor = -1
    quickLook = null
    Qt.callLater(function() {
      keyCatcher.forceActiveFocus()
      root.revealItem(searchPanel.resultRepeater.itemAt(root.resultCursor))
    })
  }
  function selectRecent(index) {
    if (!quickReturns.length) {
      focusSearch()
      return
    }
    viewMode = "search"
    resultCursor = -1
    recentCursor = Math.max(0, Math.min(quickReturns.length - 1, index))
    linkCursor = -1
    quickLook = null
    Qt.callLater(function() {
      keyCatcher.forceActiveFocus()
      root.revealItem(searchPanel.quickReturnRepeater.itemAt(root.recentCursor))
    })
  }
  function selectPersonalLink(index) {
    var changedView = viewMode !== "personal"
    viewMode = "personal"
    resultCursor = -1
    recentCursor = -1
    linkCursor = navigationCount ? Math.max(0, Math.min(navigationCount - 1, index)) : -1
    quickLook = null
    if (changedView) panelFlick.contentY = 0
    if (changedView) refreshPersonalLinks()
    Qt.callLater(function() {
      keyCatcher.forceActiveFocus()
      root.revealItem(personalPanel.repeater.itemAt(root.linkCursor))
    })
  }
  function openMagnus() {
    if (!showMagnus) return
    viewMode = "magnus"
    resultCursor = -1
    recentCursor = -1
    linkCursor = -1
    quickLook = null
    feedbackText = ""
    panelFlick.contentY = 0
    if (!magnusItems.length && !magnusBusy) {
      magnusHistory = []
      magnusFolderId = ""
      magnusFolderTitle = "Magnus"
      magnusBusy = true
      request({op: "magnus_browse"})
    } else if (magnusItems.length) {
      magnusCursor = Math.max(0, magnusCursor)
      Qt.callLater(function() { keyCatcher.forceActiveFocus() })
    }
  }
  function selectMagnus(index) {
    if (!magnusItems.length) return
    magnusCursor = Math.max(0, Math.min(magnusItems.length - 1, index))
    Qt.callLater(function() {
      keyCatcher.forceActiveFocus()
      root.revealItem(magnusPanel.repeater.itemAt(root.magnusCursor))
    })
  }
  function activateMagnus(index) {
    if (index < 0 || index >= magnusItems.length || magnusBusy) return
    var item = magnusItems[index]
    magnusBusy = true
    if (item.kind === "folder") {
      magnusHistory = magnusHistory.concat([{id: magnusFolderId, title: magnusFolderTitle}])
      request({op: "magnus_browse", safeId: item.safeId})
    } else {
      request({op: "magnus_preview", safeId: item.safeId})
    }
  }
  function hasMagnusAction(action) {
    return magnusPreview && Array.isArray(magnusPreview.actions) && magnusPreview.actions.indexOf(action) >= 0
  }
  function refreshMagnus() {
    if (magnusBusy || magnusActionBusy) return
    magnusBusy = true
    if (magnusPreview)
      request({op: "magnus_preview", safeId: magnusPreview.safeId})
    else
      request({op: "magnus_browse", safeId: magnusFolderId})
  }
  function runMagnusAction(op, value) {
    if (!magnusPreview || magnusBusy || magnusActionBusy) return
    magnusActionBusy = true
    var payload = {op: op, safeId: magnusPreview.safeId}
    if (value) payload.value = value
    request(payload)
  }
  function prepareMagnusBuild(safeId, title, recent) {
    if (!safeId || magnusBusy || magnusActionBusy) return
    pendingMagnusBuildId = String(safeId)
    pendingMagnusBuildTitle = String(title || "mobile app").replace(/^Deploy /, "")
    pendingMagnusBuildRecent = recent === true
    feedbackText = "Press Enter to deploy, or Esc to cancel"
    Qt.callLater(function() {
      if (root.pendingMagnusBuildRecent)
        searchPanel.buildConfirmButton.forceActiveFocus(Qt.TabFocusReason)
      else
        magnusPanel.buildConfirmButton.forceActiveFocus(Qt.TabFocusReason)
    })
  }
  function cancelMagnusBuild() {
    if (magnusActionBusy) return
    pendingMagnusBuildId = ""
    pendingMagnusBuildTitle = ""
    pendingMagnusBuildRecent = false
    feedbackText = "Build cancelled"
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }
  function confirmMagnusBuild() {
    if (!pendingMagnusBuildId || magnusActionBusy) return
    magnusActionBusy = true
    request({
      op: pendingMagnusBuildRecent ? "activate_recent" : "magnus_build",
      safeId: pendingMagnusBuildId,
      confirmed: true
    })
  }
  function handleMagnusKey(value) {
    var key = String(value || "").toLowerCase()
    if (viewMode !== "magnus" || magnusBusy || magnusActionBusy) return
    if (magnusPreview) {
      if (key === "d") runMagnusAction("magnus_download", "")
      else if (key === "c" && hasMagnusAction("copy")) runMagnusAction("magnus_copy", "content")
      else if (key === "h") runMagnusAction("magnus_copy", "hash")
      else if (key === "o" && hasMagnusAction("view")) runMagnusAction("magnus_open", "")
      else if (key === "r") refreshMagnus()
      return
    }
    if (key === "r") {
      refreshMagnus()
      return
    }
    if (key === "b" && magnusCursor >= 0 && magnusCursor < magnusItems.length) {
      var item = magnusItems[magnusCursor]
      if (item.actions && item.actions.indexOf("build") >= 0)
        prepareMagnusBuild(item.safeId, item.title, false)
    }
  }
  function magnusBack() {
    if (magnusBusy) return
    if (magnusPreview !== null) {
      magnusPreview = null
      Qt.callLater(function() { keyCatcher.forceActiveFocus() })
      return
    }
    if (!magnusHistory.length) return
    var previous = magnusHistory[magnusHistory.length - 1]
    magnusHistory = magnusHistory.slice(0, magnusHistory.length - 1)
    magnusBusy = true
    request({op: "magnus_browse", safeId: previous.id})
  }
  function selectSearchItem(index) {
    if (queryIsEmpty) selectRecent(index)
    else selectResult(index)
  }
  function moveTab(direction) {
    if (direction >= 0) {
      if (viewMode === "settings")
        focusSearch()
      else if (viewMode === "search" && searchField.activeFocus && activeSearchCount)
        selectSearchItem(0)
      else if (viewMode === "search")
        selectPersonalLink(0)
      else if (viewMode === "personal" && showMagnus)
        openMagnus()
      else if (viewMode === "personal" || viewMode === "magnus")
        openSettings(false)
      else
        focusSearch()
      return
    }
    if (viewMode === "settings") {
      if (showMagnus) openMagnus()
      else selectPersonalLink(Math.max(0, navigationCount - 1))
    } else if (viewMode === "magnus") {
      selectPersonalLink(Math.max(0, navigationCount - 1))
    } else if (viewMode === "personal") {
      if (activeSearchCount) selectSearchItem(activeSearchCount - 1)
      else focusSearch()
    } else if (viewMode === "search" && searchField.activeFocus) {
      openSettings(false)
    } else if (resultCursor >= 0 || recentCursor >= 0) {
      focusSearch()
    } else {
      openSettings(false)
    }
  }
  function moveCursor(dx, dy) {
    if (dx !== 0) {
      moveTab(dx)
      return
    }
    if (dy === 0) return
    if (viewMode === "magnus") {
      if (magnusPreview !== null) return
      if (!magnusCount) return
      var nextMagnus = magnusCursor < 0 ? (dy > 0 ? 0 : magnusCount - 1) : magnusCursor + dy
      if (nextMagnus < 0) selectPersonalLink(Math.max(0, navigationCount - 1))
      else if (nextMagnus >= magnusCount) focusSearch()
      else selectMagnus(nextMagnus)
      return
    }
    if (viewMode === "search") {
      if (searchField.activeFocus) {
        if (dy > 0 && activeSearchCount) selectSearchItem(0)
        else if (dy < 0) selectPersonalLink(navigationCount - 1)
        return
      }
      var searchCursor = showRecentLinks ? recentCursor : resultCursor
      if (searchCursor < 0) {
        if (dy > 0 && activeSearchCount) selectSearchItem(0)
        else if (dy < 0) selectPersonalLink(navigationCount - 1)
        return
      }
      var nextSearchItem = searchCursor + dy
      if (nextSearchItem < 0) focusSearch()
      else if (nextSearchItem >= activeSearchCount) selectPersonalLink(0)
      else selectSearchItem(nextSearchItem)
      return
    }
    if (!navigationCount) {
      focusSearch()
      return
    }
    var nextLink = linkCursor < 0 ? (dy > 0 ? 0 : navigationCount - 1) : linkCursor + dy
    if (nextLink < 0) {
      if (activeSearchCount) selectSearchItem(activeSearchCount - 1)
      else focusSearch()
    } else if (nextLink >= navigationCount) {
      focusSearch()
    } else {
      selectPersonalLink(nextLink)
    }
  }
  function activateResult(index) {
    if (index < 0 || index >= results.length) return
    var item = results[index]
    if (item.canOpen === true)
      request({op: "open_navigation", safeId: item.safeId})
    else if (item.category === "People")
      request({op: "person_quick_look", safeId: item.safeId})
  }
  function activateRecent(index) {
    if (index < 0 || index >= quickReturns.length) return
    var item = quickReturns[index]
    if (item.kind === "Magnus Build")
      prepareMagnusBuild(item.safeId, item.title, true)
    else
      request({op: "activate_recent", safeId: item.safeId})
  }
  function activateCursor() {
    if (pendingMagnusBuildId !== "") {
      confirmMagnusBuild()
      return
    }
    if (viewMode === "search") {
      if (showRecentLinks) {
        if (recentCursor >= 0 && recentCursor < quickReturns.length)
          activateRecent(recentCursor)
      } else {
        activateResult(resultCursor)
      }
      return
    }
    if (viewMode === "magnus") {
      if (magnusPreview === null) activateMagnus(magnusCursor)
      return
    }
    if (linkCursor < 0 || linkCursor >= navigationCount) return
    request({op: "open_navigation", safeId: personalLinks[linkCursor].safeId})
  }
  function activateFirstSearchItem() {
    if (showRecentLinks) {
      if (quickReturns.length) activateRecent(0)
    } else {
      activateResult(0)
    }
  }
  function onboardingDomainKey(value) {
    return String(value || "").trim().toLowerCase()
      .replace(/^https:\/\//, "").replace(/\/+$/, "")
  }
  function completeOnboarding() {
    var domain = newProfileDomain.trim()
    var username = setupUsername.trim()
    if (!domain || !username || !setupPassword || setupBusy) return
    beginSetup("Connecting to Rock…")
    onboardingInProgress = true
    var password = setupPassword
    var operation = activeProfileId &&
      onboardingDomainKey(domain) !== onboardingDomainKey(instanceDomain) ?
      "profile_add" : "rock_configure"
    pendingSuccessText = "Rock Arch is ready"
    request({op: operation, name: "", domain: domain, username: username, password: password})
    setupPassword = ""
  }
  function saveRockCredentials() {
    var username = setupUsername.trim()
    if (!username || !setupPassword || setupBusy || !activeProfileId) return
    beginSetup("Signing in…")
    var password = setupPassword
    pendingSuccessText = "Login updated securely"
    request({op: "profile_credentials_update", username: username, password: password})
    setupPassword = ""
  }
  function addProfile() {
    var username = setupUsername.trim()
    var domain = newProfileDomain.trim()
    if (!domain || !username || !setupPassword || setupBusy) return
    beginSetup("Signing in…")
    var password = setupPassword
    pendingSuccessText = "Profile added"
    request({op: "profile_add", name: newProfileName.trim(), domain: domain, username: username, password: password})
    setupPassword = ""
  }
  function switchProfile(profileId) {
    if (!profileId || profileId === activeProfileId || setupBusy) return
    beginSetup("Switching profile…")
    editLoginMode = false
    magnusItems = []
    magnusPreview = null
    magnusHistory = []
    pendingMagnusBuildId = ""
    pendingMagnusBuildTitle = ""
    pendingMagnusBuildRecent = false
    pendingSuccessText = "Profile switched"
    request({op: "profile_switch", profileId: profileId})
  }
  function removeProfile(profileId) {
    if (pendingRemoveProfileId !== profileId) {
      pendingRemoveProfileId = profileId
      feedbackText = "Press Remove again to confirm"
      return
    }
    beginSetup("Removing profile…")
    pendingSuccessText = "Profile removed from this computer"
    request({op: "profile_remove", profileId: profileId})
  }
  function signOut() {
    if (!pendingSignOut) {
      pendingSignOut = true
      feedbackText = "Press Sign out again to clear the saved login"
      return
    }
    beginSetup("Signing out…")
    request({op: "profile_sign_out"})
  }
  function beginSetup(label) {
    setupBusyText = label || "Working…"
    setupSlow = false
    setupBusy = true
    setupSlowTimer.restart()
    setupTimeoutTimer.restart()
  }
  function finishSetup() {
    setupBusy = false
    setupSlow = false
    setupSlowTimer.stop()
    setupTimeoutTimer.stop()
  }
  function updatePreference(name, value) {
    var values = {}
    values[name] = value
    request({op: "preferences_update", preferences: values})
  }
  function clearRecentLinks() {
    if (!quickReturns.length || setupBusy) return
    if (!pendingClearRecent) {
      pendingClearRecent = true
      feedbackText = "Press Enter to clear Recent Links, or Esc to cancel"
      Qt.callLater(function() { searchPanel.clearButton.forceActiveFocus(Qt.TabFocusReason) })
      return
    }
    pendingClearRecent = false
    request({op: "recent_links_clear"})
    quickReturns = []
    feedbackText = "Recent Links cleared"
    focusSearch()
  }
  function deleteCurrentItem() {
    if (viewMode === "search" && showRecentLinks && quickReturns.length)
      clearRecentLinks()
  }
  function switchContext() {
    if (!developerMode) return
    contextName = contextName === "DEV" ? "PROD" : "DEV"
    results = []
    personalLinks = []
    quickReturns = []
    resultCursor = -1
    recentCursor = -1
    linkCursor = -1
    quickLook = null
    magnusItems = []
    magnusPreview = null
    magnusHistory = []
    pendingMagnusBuildId = ""
    pendingMagnusBuildTitle = ""
    pendingMagnusBuildRecent = false
    setupPassword = ""
    request({op: "set_context", context: contextName})
    request({op: "status", probeMagnus: true})
    refreshSearch()
    refreshQuickReturns()
    if (viewMode === "personal") refreshPersonalLinks()
  }
  function resetPanel() {
    query = ""
    focusSearch()
    recentCursor = quickReturns.length ? 0 : -1
    quickLook = null
    feedbackText = ""
    statusLoaded = false
    searchInFlight = false
    searchPending = false
    searchInFlightQuery = ""
    request({op: "status"})
    refreshQuickReturns()
    refreshPersonalLinks()
  }

  onOpenedChanged: {
    if (opened) resetPanel()
    else dropQueuedCredentialRequests()
  }

  Process {
    id: brokerProcess
    command: ["/usr/bin/python3", "-m", "rock_lens_broker"]
    workingDirectory: root.packageRoot
    running: true
    onStarted: if (root.requestQueue.length) brokerReconnectTimer.restart()
  }

  Timer {
    id: brokerReconnectTimer
    interval: 150
    onTriggered: {
      if (!root.requestQueue.length) return
      if (brokerSocket.connected) {
        root.flushRequests()
        return
      }
      brokerSocket.connected = false
      brokerSocket.connected = true
    }
  }
  Timer { id: searchTimer; interval: 250; onTriggered: root.refreshSearch() }
  Timer {
    interval: 60000
    repeat: true
    running: root.opened
    onTriggered: root.relativeTimeTick += 1
  }
  Timer {
    id: startupStatusTimer
    interval: 300
    running: true
    onTriggered: root.request({op: "status", probeMagnus: true})
  }
  Timer { id: magnusProbeTimer; interval: 800; onTriggered: root.probeMagnus() }
  Timer {
    id: updatePollTimer
    interval: 1000
    repeat: true
    running: root.updateBusy
    onTriggered: root.request({op: "update_status"})
  }
  Timer { interval: 86400000; repeat: true; running: true; onTriggered: root.request({op: "update_status"}) }
  Timer {
    id: setupSlowTimer
    interval: 3000
    onTriggered: if (root.setupBusy) root.setupSlow = true
  }
  Timer {
    id: setupTimeoutTimer
    interval: 18000
    onTriggered: if (root.setupBusy) {
      root.dropQueuedCredentialRequests()
      root.finishSetup()
      root.pendingSuccessText = ""
      root.feedbackText = "Rock did not respond. Check the connection and try again."
    }
  }

  Socket {
    id: brokerSocket
    path: root.socketPath
    connected: false
    onConnectedChanged: {
      if (connected && root.requestQueue.length) root.flushRequests()
      else if (!connected && root.requestQueue.length) brokerReconnectTimer.restart()
    }
    onError: function(error) {
      connected = false
      if (root.requestQueue.length) brokerReconnectTimer.restart()
    }
    parser: SplitParser { onRead: function(line) { root.accept(line) } }
  }

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function settings(): void {
      root.open()
      root.openSettings(false)
    }
  }

  Shortcut { sequence: "Alt+P"; context: Qt.ApplicationShortcut; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("p") }
  Shortcut { sequence: "Alt+G"; context: Qt.ApplicationShortcut; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("g") }
  Shortcut { sequence: "Alt+W"; context: Qt.ApplicationShortcut; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("w") }
  Shortcut { sequence: "Alt+J"; context: Qt.ApplicationShortcut; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("j") }
  Shortcut { sequence: "Alt+Shift+P"; context: Qt.ApplicationShortcut; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("page") }
  Shortcut { sequence: "Alt+C"; context: Qt.ApplicationShortcut; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("c") }
  Shortcut { sequence: "Alt+0"; context: Qt.ApplicationShortcut; enabled: root.scopeShortcutsEnabled; onActivated: root.clearScope() }
  Shortcut { sequence: "Ctrl+,"; context: Qt.ApplicationShortcut; enabled: root.opened; onActivated: root.openSettings(false) }
  Shortcut { sequence: "Ctrl+1"; context: Qt.ApplicationShortcut; enabled: root.opened && !root.onboardingRequired; onActivated: root.focusSearch() }
  Shortcut { sequence: "Ctrl+2"; context: Qt.ApplicationShortcut; enabled: root.opened && !root.onboardingRequired; onActivated: root.selectPersonalLink(0) }
  Shortcut { sequence: "Ctrl+3"; context: Qt.ApplicationShortcut; enabled: root.opened && !root.onboardingRequired && root.showMagnus; onActivated: root.openMagnus() }
  Shortcut { sequence: "Ctrl+4"; context: Qt.ApplicationShortcut; enabled: root.opened && !root.onboardingRequired; onActivated: root.openSettings(false) }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "ROCK" + (root.developerMode ? " " + root.contextName : "") +
      (root.contextName === "PROD" && root.rockConfigured ? "  ●" : "")
    fontFamily: root.bar ? root.bar.fontFamily : Style.font.family
    horizontalMargin: 8
    onPressed: root.toggle()
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: root.onboardingRequired ? onboardingForm.domainField : searchField
    contentWidth: panel.fittedContentWidth(Style.space(520))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(680))

    RockLensKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      formMode: root.onboardingRequired || root.viewMode === "settings" ||
        root.pendingClearRecent || root.pendingMagnusBuildId !== "" || root.magnusPreview !== null
      commandMode: root.magnusPreviewCommandsEnabled
      blocked: searchField.activeFocus || onboardingForm.inputActive || settingsPanel.inputActive || magnusPanel.inputActive
      backspaceEnabled: root.resultCursor >= 0 || root.recentCursor >= 0 || root.linkCursor >= 0 || (root.viewMode === "magnus" && (root.magnusPreview !== null || root.magnusHistory.length > 0))
      onCloseRequested: root.escapePanel()
      onMoveRequested: function(dx, dy) { root.moveCursor(dx, dy) }
      onTabRequested: function(direction) { root.moveTab(direction) }
      onActivateRequested: root.activateCursor()
      onDeleteRequested: root.deleteCurrentItem()
      onTextKey: function(value) { root.handleMagnusKey(value) }
      onBackspaceRequested: {
        if (root.viewMode === "magnus") root.magnusBack()
        else root.backspaceToSearch()
      }

      Column {
        id: content
        width: parent.width
        spacing: Style.spacing.sm

        RockLensNavigationTabs {
          width: parent.width
          controller: root
        }

        RowLayout {
          visible: root.viewMode === "search" && !root.onboardingRequired
          width: parent.width
          spacing: Style.spacing.sm

          TextField {
            id: searchField
            Layout.fillWidth: true
            enabled: root.contextName === "DEV" || (root.statusLoaded && root.rockConfigured)
            maximumLength: 120
            placeholderText: root.contextName === "PROD" && root.statusLoaded && !root.rockConfigured ? "Save a Rock login to search" : "Search Rock… (try g: name or ID)"
            selectByMouse: true
            inputMethodHints: Qt.ImhNoPredictiveText
            onTextEdited: {
              root.resultCursor = -1
              root.recentCursor = -1
              root.pendingClearRecent = false
              root.results = []
              root.quickLook = null
              root.feedbackText = ""
              root.scheduleSearch()
              if (text.trim().length === 0) root.refreshQuickReturns()
            }
            Keys.priority: Keys.BeforeItem
            Keys.onPressed: function(event) {
              if (event.key === Qt.Key_Escape) {
                root.escapePanel()
                event.accepted = true
              } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
                root.moveCursor(0, event.key === Qt.Key_Down ? 1 : -1)
                event.accepted = true
              } else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
                if (root.contextName === "PROD" && !root.rockConfigured) return
                var backwards = event.key === Qt.Key_Backtab || (event.modifiers & Qt.ShiftModifier)
                root.moveTab(backwards ? -1 : 1)
                event.accepted = true
              } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                root.activateFirstSearchItem()
                event.accepted = true
              }
            }
          }

          Rectangle {
            visible: root.scopeKey !== ""
            Layout.preferredWidth: scopeBadgeLabel.implicitWidth + 20
            Layout.preferredHeight: searchField.implicitHeight
            radius: 7
            color: Style.selectedFillFor(Color.foreground, Color.accent)
            Text {
              id: scopeBadgeLabel
              anchors.centerIn: parent
              text: root.scopeLabel
              color: Color.foreground
              font.bold: true
            }
            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.clearScope()
            }
          }
        }
        Text {
          visible: !root.onboardingRequired
          width: parent.width
          text: root.connectionText
          color: Color.foreground
          opacity: 0.58
          font.pixelSize: Style.font.bodySmall
          textFormat: Text.PlainText
          elide: Text.ElideRight
        }

        Column {
          visible: !root.onboardingRequired && root.viewMode !== "settings" && root.contextName === "PROD" && !root.rockConfigured
          width: content.width
          height: visible ? implicitHeight : 0
          spacing: Style.spacing.sm
          Text {
            width: parent.width
            text: root.profiles.length ? "This profile is signed out. Update its login in Settings." : "Add a Rock profile to begin live search."
            color: Color.foreground
            opacity: 0.65
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
          }
          Button {
            text: root.profiles.length ? "Open Settings" : "Add Rock profile"
            onClicked: root.openSettings(root.profiles.length === 0)
          }
        }

        Flickable {
          id: panelFlick
          readonly property real maximumHeight: Style.space(root.onboardingRequired ? 280 : (root.viewMode === "settings" ? 520 : (root.contextName === "PROD" && !root.rockConfigured ? 180 : 420)))
          width: content.width
          height: Math.min(maximumHeight, Math.max(Style.space(72), body.implicitHeight))
          contentWidth: width
          contentHeight: body.implicitHeight
          clip: true
          boundsBehavior: Flickable.StopAtBounds
          interactive: contentHeight > height
          ScrollBar.vertical: ScrollBar {}

          Column {
            id: body
            width: parent.width
            spacing: Style.spacing.sm

            RockLensLoginPanel {
              id: onboardingForm
              visible: root.onboardingRequired
              width: body.width
              controller: root
            }

            RockLensSearchPanel {
              id: searchPanel
              visible: !root.onboardingRequired && root.viewMode === "search"
              width: body.width
              controller: root
              searchField: searchField
            }

            RockLensPersonalPanel {
              id: personalPanel
              visible: !root.onboardingRequired && root.viewMode === "personal"
              width: body.width
              controller: root
            }

            RockLensMagnusPanel {
              id: magnusPanel
              visible: !root.onboardingRequired && root.viewMode === "magnus"
              width: body.width
              controller: root
            }

            RockLensSettingsPanel {
              id: settingsPanel
              visible: !root.onboardingRequired && root.viewMode === "settings"
              width: body.width
              controller: root
            }
          }
        }

        Text {
          visible: text.length > 0
          width: parent.width
          text: root.feedbackText || (root.onboardingRequired ? "" : root.guidanceText())
          color: Color.foreground
          opacity: 0.55
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
        }
      }
    }
  }
}
