.pragma library

// Explicit controller and UI dependencies keep response transitions testable.

function status(root, ui, response, frame) {
    if (response.magnus) {
      root.magnusAvailable = response.magnus.available === true
      root.magnusState = String(response.magnus.state || "unknown")
      root.magnusProbeInFlight = false
      if (!root.showMagnus && root.viewMode === "magnus") root.focusSearch()
      if (root.pendingUiHandoff && String(root.pendingUiHandoff.view || "") === "magnus") Qt.callLater(function() { root.applyUiHandoff(root.pendingUiHandoff) })
    }
    if (Array.isArray(response.magnusBuilds)) root.magnusBuilds = response.magnusBuilds
}

function content(root, ui, response, frame) {
    if (response.magnusBrowser) {
      var returning = root.pendingMagnusReturn || null
      root.pendingMagnusReturn = null
      var previousItem = root.magnusItems[root.magnusCursor]
      var sameFolder = root.magnusFolderId === String(response.magnusBrowser.folderId || "")
      root.magnusBusy = false
      root.magnusPreview = null
      root.magnusFolderId = String(response.magnusBrowser.folderId || "")
      root.magnusFolderTitle = String(response.magnusBrowser.title || "Magnus")
      root.magnusItems = Array.isArray(response.magnusBrowser.items) ? response.magnusBrowser.items : []
      var retained = sameFolder && previousItem ? root.magnusItems.findIndex(function(item) { return item.safeId === previousItem.safeId }) : -1
      root.magnusCursor = root.magnusItems.length ? Math.max(0, Math.min(root.magnusItems.length - 1, returning ? returning.cursor : retained)) : -1
      if (root.viewMode === "magnus") ui.panelFlick.contentY = returning ? returning.scroll : 0
      Qt.callLater(function() {
        if (root.viewMode !== "magnus") return
        if (!root.tabBarFocused) ui.keyCatcher.forceActiveFocus()
        if (root.magnusCursor >= 0)
          root.revealItem(ui.magnusPanel.repeater.itemAt(root.magnusCursor))
      })
    }
    if (response.magnusPreview) {
      root.magnusBusy = false
      root.magnusPreview = response.magnusPreview
      ui.panelFlick.contentY = 0
      Qt.callLater(function() {
        if (root.viewMode !== "magnus" || root.magnusPreview === null) return
        ui.magnusPanel.previewPrimaryButton.forceActiveFocus(Qt.TabFocusReason)
        root.revealFocusedControl(ui.magnusPanel.previewPrimaryButton)
      })
    }
    if (response.magnusDownload) {
      root.magnusActionBusy = false
      root.feedbackText = response.magnusDownload.previewOnly === true
        ? "Preview only · no file was downloaded"
        : "Saved " + response.magnusDownload.savedAs + " to Downloads"
    }
    if (response.magnusCopied) {
      root.magnusActionBusy = false
      root.feedbackText = response.magnusCopied.previewOnly === true
        ? "Preview only · clipboard unchanged"
        : response.magnusCopied.value === "hash" ? "SHA-256 copied" : "File contents copied"
    }
    if (response.magnusBuild) {
      root.magnusActionBusy = false
      root.pendingMagnusBuildId = ""
      root.pendingMagnusBuildTitle = ""
      root.pendingMagnusBuildRecent = false
      root.feedbackText = String(response.magnusBuild.message || "Build request accepted") +
        (response.magnusBuild.previewOnly === true || !root.preferenceRecentLinks
          ? "" : " · Added to Recent Links")
      Qt.callLater(function() { ui.keyCatcher.forceActiveFocus() })
    }
}
