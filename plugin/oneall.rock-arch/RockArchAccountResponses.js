.pragma library
.import "RockArchNavigation.js" as Navigation

// Explicit controller and UI dependencies keep response transitions testable.

function context(root, ui, response, frame) {
    if (response.context && !frame.staleSearch)
      root.contextName = response.context === "PROD" ? "PROD" : "DEV"
    if (response.developerMode !== undefined)
      root.developerMode = response.developerMode === true
    if (response.instance)
      root.instanceDomain = String(response.instance.origin || "").replace("https://", "")
    if (response.rock) {
      root.rockAvailable = response.rock.available === true
      root.rockConfigured = response.rock.configured === true
      if (!root.rockConfigured) root.resetSearchCapabilities()
    }
}

function update(root, ui, response, frame) {
    if (response.update) {
      root.updateManaged = response.update.managed === true
      root.updateState = String(response.update.state || "idle")
      root.currentVersion = String(response.update.currentVersion || root.currentVersion)
      root.availableVersion = String(response.update.availableVersion || "")
      root.updateLastCheckedAt = String(response.update.lastCheckedAt || "")
      root.updateLastUpdatedAt = String(response.update.lastUpdatedAt || "")
      root.updateError = String(response.update.error || "")
      root.updateAvailable = response.update.updateAvailable === true
    }
}

function profiles(root, ui, response, frame) {
    if (response.profiles) {
      var previousProfileId = root.activeProfileId
      root.profilesLoaded = true
      root.activeProfileId = String(response.profiles.activeProfileId || "")
      root.profiles = Array.isArray(response.profiles.profiles) ? response.profiles.profiles : []
      var preferences = response.profiles.preferences || {}
      var tabOrder = Navigation.normalize(preferences.tabOrder)
      if (JSON.stringify(root.tabOrder) !== JSON.stringify(tabOrder)) root.tabOrder = tabOrder
      root.preferencePersonContext = preferences.showPersonContext !== false
      root.preferenceRecentLinks = preferences.recentLinks !== false
      root.preferenceCloseAfterOpen = preferences.closeAfterOpen === true
      root.preferenceShowMenuBar = preferences.showMenuBar !== false
      root.preferenceTerminalAccess = preferences.terminalAccess !== false
      root.preferenceAutomaticUpdates = preferences.automaticUpdates === true
      root.preferenceOnboardingSetupCompleted = preferences.onboardingSetupCompleted === true
      if (Array.isArray(preferences.enabledCategories))
        root.enabledCategories = preferences.enabledCategories
      if (previousProfileId !== root.activeProfileId) root.resetSearchCapabilities()
      if (root.profiles.length === 0 && root.opened) {
        root.viewMode = "settings"
        root.addProfileMode = false
      }
      if (root.contextName === "PROD" && !root.rockConfigured && root.opened) {
        root.viewMode = "settings"
        root.addProfileMode = false
        root.editLoginMode = false
        if (root.instanceDomain && root.newProfileDomain.trim().length === 0)
          root.newProfileDomain = root.instanceDomain
        if (root.activeProfileId && root.newProfileName.trim().length === 0)
          root.newProfileName = root.activeProfileName()
        Qt.callLater(function() { ui.onboardingForm.profileNameField.forceActiveFocus() })
      } else if (root.finishSetupOnboardingRequired && root.opened) {
        root.initializeOnboardingSetup()
        Qt.callLater(function() {
          ui.finishSetupPanel.primaryButton.forceActiveFocus(Qt.TabFocusReason)
          root.revealFocusedControl(ui.finishSetupPanel.primaryButton)
        })
      }
    }
}

function capabilities(root, ui, response, frame) {
    if (response.searchCapabilities) {
      root.searchCapabilitiesInFlight = false
      root.searchCapabilitiesState = String(response.searchCapabilities.state || "error")
      root.availableSearchCategories = Array.isArray(
        response.searchCapabilities.availableCategories)
        ? response.searchCapabilities.availableCategories : []
      root.unavailableSearchCategories = Array.isArray(
        response.searchCapabilities.unavailableCategories)
        ? response.searchCapabilities.unavailableCategories : []
      root.onboardingSetupPrepared = false
      if (root.searchCapabilitiesState === "ready") {
        root.initializeOnboardingSetup()
        if (root.query.trim().length > 0 && root.resultsQuery !== root.query)
          Qt.callLater(function() { root.refreshSearch() })
      } else if (root.searchCapabilitiesState === "error") {
        root.results = []
        root.feedbackText = "Rock Arch couldn't check what this account can search."
      }
    }
}

function terminal(root, ui, response, frame) {
    if (response.terminal) {
      root.terminalInstalled = response.terminal.installed === true
      root.terminalInPath = response.terminal.inPath === true
      root.terminalError = String(response.terminal.error || "")
    }
}

function status(root, ui, response, frame) {
    if (frame.isStatusResponse) {
      root.statusLoaded = true
      if (root.contextName === "PROD" && !root.rockConfigured) {
        root.resetSearchCapabilities()
        root.searchInFlight = false
        root.searchPending = false
        root.searchInFlightQuery = ""
      } else if (root.searchCapabilitiesReady && root.query.trim().length > 0 && root.resultsQuery !== root.query) {
        Qt.callLater(function() { root.refreshSearch() })
      }
      if (root.contextName === "PROD" && root.rockConfigured &&
          !root.searchCapabilitiesReady && !root.searchCapabilitiesInFlight)
        Qt.callLater(function() { root.probeSearchCapabilities(false) })
      if (root.contextName === "PROD" && root.rockConfigured &&
          (root.magnusState === "unknown" || root.magnusState === "error"))
        ui.magnusProbeTimer.restart()
      if (root.finishSetupOnboardingRequired && root.opened) {
        root.initializeOnboardingSetup()
        Qt.callLater(function() {
          ui.finishSetupPanel.primaryButton.forceActiveFocus(Qt.TabFocusReason)
          root.revealFocusedControl(ui.finishSetupPanel.primaryButton)
        })
      }
    }
}

function refresh(root, ui, response, frame) {
    if (response.refreshLive === true) {
      root.resetSearchCapabilities()
      var completedOnboarding = root.onboardingInProgress
      root.onboardingInProgress = false
      root.finishSetup()
      root.setupPassword = ""
      root.newProfileName = ""
      root.newProfileDomain = ""
      if (root.profiles.length > 0) root.addProfileMode = false
      root.editLoginMode = false
      root.pendingRemoveProfileId = ""
      root.pendingSignOut = false
      root.feedbackText = root.pendingSuccessText || "Rock connection updated"
      root.pendingSuccessText = ""
      Qt.callLater(function() {
        if (completedOnboarding && root.finishSetupOnboardingRequired) {
          root.feedbackText = ""
          root.initializeOnboardingSetup()
          ui.finishSetupPanel.primaryButton.forceActiveFocus(Qt.TabFocusReason)
          root.revealFocusedControl(ui.finishSetupPanel.primaryButton)
        } else if (completedOnboarding) {
          root.focusSearch()
        }
        root.refreshSearch()
        root.refreshQuickReturns()
        root.refreshPersonalLinks()
        if (root.viewMode === "search" && !root.onboardingFlowActive)
          ui.searchField.forceActiveFocus()
        root.request({op: "status"})
      })
    }
}

function connection(root, ui, response, frame) {
    if (response.onboardingSetup) {
      root.onboardingSetupPending = false
      root.onboardingSetupPrepared = false
      root.feedbackText = "Setup complete"
      Qt.callLater(function() { root.focusSearch() })
    }
    if (response.connection === "connected") {
      root.finishSetup()
      root.feedbackText = "Connection successful"
      Qt.callLater(function() { root.request({op: "status"}) })
    } else if (response.connection === "signed_out") {
      root.finishSetup()
      root.onboardingInProgress = false
      root.pendingSignOut = false
      root.editLoginMode = false
      root.setupPassword = ""
      root.feedbackText = "Signed out; this profile and its local history were kept"
    }
}

function interrupted(root) {
    if (root.searchCapabilitiesInFlight) {
        root.searchCapabilitiesInFlight = false
        root.searchCapabilitiesState = "unknown"
        root.probeSearchCapabilities(false)
    }
}
