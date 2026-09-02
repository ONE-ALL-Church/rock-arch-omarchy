import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "oneall.rock-lens"
  ipcTarget: "oneall.rock-lens"
  manageIpc: false

  readonly property string projectPath: "/home/bscottdavis/Documents/Codex/2026-09-01/rock-lens-omarchy"
  readonly property string runtimeDir: (Quickshell.env("XDG_RUNTIME_DIR") || ("/run/user/" + Quickshell.env("UID"))) + "/rock-lens"
  readonly property string socketPath: runtimeDir + "/broker.sock"
  property string contextName: "PROD"
  property bool developerMode: false
  property string viewMode: "search"
  property alias query: searchField.text
  property var results: []
  property var personalLinks: []
  property var quickReturns: []
  property var quickLook: null
  property var requestQueue: []
  property string searchSource: "synthetic"
  property string feedbackText: ""
  property string instanceDomain: ""
  property string setupUsername: ""
  property string setupPassword: ""
  property bool magnusAvailable: false
  property bool magnusConfigured: false
  property bool personalLinksAvailable: false
  property bool setupBusy: false
  property bool searchInFlight: false
  property bool searchPending: false
  property string searchInFlightQuery: ""
  property int resultCursor: -1
  property int recentCursor: -1
  property int linkCursor: -1
  readonly property int navigationCount: personalLinks.length
  readonly property bool queryIsEmpty: query.trim().length === 0
  readonly property bool showRecentLinks: viewMode === "search" && queryIsEmpty
  readonly property int activeSearchCount: queryIsEmpty ? quickReturns.length : results.length
  readonly property string scopeKey: scopeKeyForQuery(query)
  readonly property string scopeLabel: scopeLabelForKey(scopeKey)
  readonly property bool scopeShortcutsEnabled: opened && viewMode === "search" &&
    !domainField.activeFocus && !usernameField.activeFocus && !passwordField.activeFocus
  readonly property string connectionText: contextName === "DEV" ? "Preview data" :
    magnusConfigured ? "Magnus · " + instanceDomain :
    magnusAvailable ? "Rock login required" : "Magnus unavailable"

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
    if (!brokerSocket.connected) brokerSocket.connected = true
    sendTimer.restart()
  }

  function scopeKeyForQuery(value) {
    var text = String(value || "")
    var colon = text.indexOf(":")
    if (colon < 1) return ""
    var prefix = text.substring(0, colon).trim().toLowerCase()
    if (prefix === "p" || prefix === "person" || prefix === "people") return "p"
    if (prefix === "g" || prefix === "group" || prefix === "groups") return "g"
    if (prefix === "w" || prefix === "workflow" || prefix === "workflows") return "w"
    if (prefix === "j" || prefix === "job" || prefix === "jobs") return "j"
    if (prefix === "pg" || prefix === "page" || prefix === "pages") return "page"
    if (prefix === "c" || prefix === "content" || prefix === "contents" ||
        prefix === "item" || prefix === "items") return "c"
    return ""
  }

  function scopeLabelForKey(key) {
    if (key === "p") return "People"
    if (key === "g") return "Groups"
    if (key === "w") return "Workflows"
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
    if (!clearScope()) close()
  }

  function accept(line) {
    var response
    try { response = JSON.parse(line) } catch (e) { return }
    if (!response || response.ok !== true) {
      setupBusy = false
      feedbackText = response && response.error ? String(response.error).split("_").join(" ") : "Request failed"
      return
    }
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
    if (response.magnus) {
      magnusAvailable = response.magnus.available === true
      magnusConfigured = response.magnus.configured === true
    }
    if (isSearchResponse && !staleSearch) {
      results = response.results
      if (resultCursor >= results.length) resultCursor = results.length - 1
    }
    if (Array.isArray(response.personalLinks)) personalLinks = response.personalLinks
    if (Array.isArray(response.quickReturns)) {
      quickReturns = response.quickReturns
      if (recentCursor >= quickReturns.length) recentCursor = quickReturns.length - 1
    }
    if (linkCursor >= navigationCount) linkCursor = navigationCount - 1
    if (viewMode === "personal" && linkCursor < 0 && navigationCount) linkCursor = 0
    if (response.personalLinksAvailable !== undefined)
      personalLinksAvailable = response.personalLinksAvailable === true
    if (response.person) quickLook = response.person
    if (response.source && !staleSearch) searchSource = String(response.source)
    if (response.refreshLive === true) {
      setupBusy = false
      setupPassword = ""
      feedbackText = "Magnus credentials saved securely"
      Qt.callLater(function() {
        root.refreshSearch()
        root.refreshQuickReturns()
        if (root.viewMode === "personal") root.refreshPersonalLinks()
        searchField.forceActiveFocus()
      })
    }
    if (!staleSearch && Array.isArray(response.unavailable) && response.unavailable.length)
      feedbackText = "Unavailable: " + response.unavailable.join(", ")
    else if (response.opened === true)
      feedbackText = "Opened in Rock and added to Recent Links"
    else if (response.source === "unavailable" && !staleSearch)
      feedbackText = "Live Rock search needs Magnus setup"
    else if (response.source && !staleSearch)
      feedbackText = ""
    if (staleSearch) Qt.callLater(function() { root.refreshSearch() })
  }

  function refreshSearch() {
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
    panelFlick.contentY = 0
    Qt.callLater(function() { searchField.forceActiveFocus() })
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
      root.revealItem(resultRepeater.itemAt(root.resultCursor))
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
      root.revealItem(quickReturnRepeater.itemAt(root.recentCursor))
    })
  }
  function selectPersonalLink(index) {
    var changedView = viewMode !== "personal"
    viewMode = "personal"
    resultCursor = -1
    recentCursor = -1
    linkCursor = navigationCount ? Math.max(0, Math.min(navigationCount - 1, index)) : -1
    quickLook = null
    if (changedView) refreshPersonalLinks()
    Qt.callLater(function() {
      keyCatcher.forceActiveFocus()
      root.revealItem(personalLinkRepeater.itemAt(root.linkCursor))
    })
  }
  function selectSearchItem(index) {
    if (queryIsEmpty) selectRecent(index)
    else selectResult(index)
  }
  function moveTab(direction) {
    if (direction >= 0) {
      if (viewMode === "search" && resultCursor < 0 && recentCursor < 0 && activeSearchCount)
        selectSearchItem(0)
      else if (viewMode === "search")
        selectPersonalLink(0)
      else
        focusSearch()
      return
    }
    if (viewMode === "personal") {
      if (activeSearchCount) selectSearchItem(activeSearchCount - 1)
      else focusSearch()
    } else if (resultCursor >= 0 || recentCursor >= 0) {
      focusSearch()
    } else {
      selectPersonalLink(navigationCount - 1)
    }
  }
  function moveCursor(dx, dy) {
    if (dx !== 0) {
      moveTab(dx)
      return
    }
    if (dy === 0) return
    if (viewMode === "search") {
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
  function activateCursor() {
    if (viewMode === "search") {
      if (showRecentLinks) {
        if (recentCursor >= 0 && recentCursor < quickReturns.length)
          request({op: "open_navigation", safeId: quickReturns[recentCursor].safeId})
      } else {
        activateResult(resultCursor)
      }
      return
    }
    if (linkCursor < 0 || linkCursor >= navigationCount) return
    request({op: "open_navigation", safeId: personalLinks[linkCursor].safeId})
  }
  function activateFirstSearchItem() {
    if (showRecentLinks) {
      if (quickReturns.length) request({op: "open_navigation", safeId: quickReturns[0].safeId})
    } else {
      activateResult(0)
    }
  }
  function saveMagnusCredentials() {
    var username = setupUsername.trim()
    var domain = instanceDomain.trim()
    if (!domain || !username || !setupPassword || setupBusy) return
    setupBusy = true
    var password = setupPassword
    request({op: "magnus_configure", domain: domain, username: username, password: password})
    setupPassword = ""
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
    setupPassword = ""
    request({op: "set_context", context: contextName})
    request({op: "status"})
    refreshSearch()
    refreshQuickReturns()
    if (viewMode === "personal") refreshPersonalLinks()
  }
  function resetPanel() {
    query = ""
    focusSearch()
    quickLook = null
    feedbackText = ""
    request({op: "status"})
    refreshSearch()
    refreshQuickReturns()
  }

  onOpenedChanged: if (opened) resetPanel()

  Process {
    id: brokerProcess
    command: ["python3", "-m", "rock_lens_broker"]
    workingDirectory: root.projectPath
    running: true
  }

  Timer {
    id: sendTimer
    interval: 40
    onTriggered: {
      if (!brokerSocket.connected) {
        brokerSocket.connected = true
        retryTimer.restart()
        return
      }
      if (!root.requestQueue.length) return
      var payload = root.requestQueue[0]
      root.requestQueue = root.requestQueue.slice(1)
      brokerSocket.write(JSON.stringify(payload) + "\n")
      brokerSocket.flush()
      if (root.requestQueue.length) sendTimer.restart()
    }
  }
  Timer { id: retryTimer; interval: 120; onTriggered: sendTimer.restart() }
  Timer { id: searchTimer; interval: 250; onTriggered: root.refreshSearch() }

  Socket {
    id: brokerSocket
    path: root.socketPath
    connected: false
    onConnectedChanged: if (connected && root.requestQueue.length) sendTimer.restart()
    parser: SplitParser { onRead: function(line) { root.accept(line) } }
  }

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
  }

  Shortcut { sequence: "Alt+P"; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("p") }
  Shortcut { sequence: "Alt+G"; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("g") }
  Shortcut { sequence: "Alt+W"; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("w") }
  Shortcut { sequence: "Alt+J"; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("j") }
  Shortcut { sequence: "Alt+Shift+P"; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("page") }
  Shortcut { sequence: "Alt+C"; enabled: root.scopeShortcutsEnabled; onActivated: root.applyScope("c") }
  Shortcut { sequence: "Alt+0"; enabled: root.scopeShortcutsEnabled; onActivated: root.clearScope() }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "ROCK" + (root.developerMode ? " " + root.contextName : "") +
      (root.contextName === "PROD" && root.magnusConfigured ? "  ●" : "")
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
    focusTarget: searchField
    contentWidth: panel.fittedContentWidth(Style.space(520))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(680))

    RockLensKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: searchField.activeFocus || domainField.activeFocus || usernameField.activeFocus || passwordField.activeFocus
      backspaceEnabled: root.resultCursor >= 0 || root.recentCursor >= 0 || root.linkCursor >= 0
      onCloseRequested: root.escapePanel()
      onMoveRequested: function(dx, dy) { root.moveCursor(dx, dy) }
      onTabRequested: function(direction) { root.moveTab(direction) }
      onActivateRequested: root.activateCursor()
      onBackspaceRequested: root.backspaceToSearch()

      Column {
        id: content
        width: parent.width
        spacing: Style.spacing.sm

        RowLayout {
          width: parent.width
          spacing: Style.spacing.sm
          Text { text: "Rock Lens"; color: Color.foreground; font.pixelSize: Style.font.title; font.bold: true }
          Rectangle {
            visible: root.developerMode
            Layout.preferredWidth: contextLabel.implicitWidth + 16
            Layout.preferredHeight: contextLabel.implicitHeight + 8
            radius: 6
            color: root.contextName === "PROD" ? "#7f1d1d" : "#14532d"
            Text { id: contextLabel; anchors.centerIn: parent; text: root.contextName; color: "white"; font.bold: true }
            MouseArea { anchors.fill: parent; enabled: root.developerMode; cursorShape: Qt.PointingHandCursor; onClicked: root.switchContext() }
          }
          Item { Layout.fillWidth: true }
          Repeater {
            model: ["search", "personal"]
            delegate: Rectangle {
              required property var modelData
              Layout.preferredWidth: tabText.implicitWidth + 20
              Layout.preferredHeight: Style.space(32)
              radius: 7
              color: root.viewMode === modelData ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
              Text {
                id: tabText
                anchors.centerIn: parent
                text: modelData === "search" ? "Search" : "Personal Links"
                color: Color.foreground
                font.bold: root.viewMode === modelData
              }
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  if (modelData === "search") root.focusSearch()
                  else root.selectPersonalLink(0)
                }
              }
            }
          }
        }

        RowLayout {
          visible: root.viewMode === "search"
          width: parent.width
          spacing: Style.spacing.sm

          TextField {
            id: searchField
            Layout.fillWidth: true
            maximumLength: 120
            placeholderText: "Search Rock… (try g:)"
            selectByMouse: true
            inputMethodHints: Qt.ImhNoPredictiveText
            onTextEdited: {
              root.resultCursor = -1
              root.recentCursor = -1
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
                if (root.contextName === "PROD" && !root.magnusConfigured) return
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
          width: parent.width
          text: root.connectionText
          color: Color.foreground
          opacity: 0.58
          font.pixelSize: Style.font.bodySmall
          textFormat: Text.PlainText
          elide: Text.ElideRight
        }

        Column {
          visible: root.contextName === "PROD" && !root.magnusConfigured
          width: content.width
          height: visible ? implicitHeight : 0
          spacing: Style.spacing.sm
          Text { width: parent.width; text: "Connect this Rock instance. Credentials stay in Secret Service."; color: Color.foreground; opacity: 0.65; wrapMode: Text.WordWrap; textFormat: Text.PlainText }
          TextField {
            id: domainField
            width: parent.width
            placeholderText: "Rock domain (for example rock.example.org)"
            text: root.instanceDomain
            selectByMouse: true
            inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoPredictiveText
            onTextChanged: root.instanceDomain = text
          }
          TextField {
            id: usernameField
            width: parent.width
            placeholderText: "Rock username"
            text: root.setupUsername
            selectByMouse: true
            onTextChanged: root.setupUsername = text
          }
          TextField {
            id: passwordField
            width: parent.width
            placeholderText: "Rock password"
            text: root.setupPassword
            echoMode: TextInput.Password
            selectByMouse: true
            inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
            onTextChanged: root.setupPassword = text
            onAccepted: root.saveMagnusCredentials()
          }
          Rectangle {
            width: Style.space(150)
            height: Style.space(34)
            radius: 6
            opacity: root.instanceDomain.trim().length > 0 && root.setupUsername.trim().length > 0 && root.setupPassword.length > 0 && !root.setupBusy ? 1 : 0.45
            color: "#14532d"
            Text { anchors.centerIn: parent; text: root.setupBusy ? "Saving…" : "Save securely"; color: "white"; font.bold: true }
            MouseArea {
              anchors.fill: parent
              enabled: root.instanceDomain.trim().length > 0 && root.setupUsername.trim().length > 0 && root.setupPassword.length > 0 && !root.setupBusy
              cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
              onClicked: root.saveMagnusCredentials()
            }
          }
        }

        Flickable {
          id: panelFlick
          readonly property real maximumHeight: Style.space(root.contextName === "PROD" && !root.magnusConfigured ? 180 : 420)
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

            Column {
              visible: root.viewMode === "search" && !root.showRecentLinks
              width: body.width
              height: visible ? implicitHeight : 0
              spacing: Style.spacing.sm

              Repeater {
                id: resultRepeater
                model: root.results
                delegate: Rectangle {
                  required property var modelData
                  required property int index
                  width: body.width
                  height: Style.space(50)
                  radius: 7
                  color: index === root.resultCursor ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
                  Column {
                    anchors.left: parent.left
                    anchors.right: openButton.visible ? openButton.left : parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    Text { width: parent.width; text: modelData.title; color: Color.foreground; font.bold: true; textFormat: Text.PlainText; elide: Text.ElideRight }
                    Text { width: parent.width; text: modelData.category + " · " + modelData.subtitle + " · " + modelData.status; color: Color.foreground; opacity: 0.65; textFormat: Text.PlainText; elide: Text.ElideRight }
                  }
                  MouseArea {
                    anchors.fill: parent
                    onClicked: {
                      root.selectResult(index)
                      if (modelData.category === "People")
                        root.request({op: "person_quick_look", safeId: modelData.safeId})
                    }
                  }
                  Rectangle {
                    id: openButton
                    visible: modelData.canOpen === true && root.contextName === "PROD" && index === root.resultCursor
                    width: visible ? Style.space(54) : 0
                    height: Style.space(32)
                    anchors.right: parent.right
                    anchors.rightMargin: 7
                    anchors.verticalCenter: parent.verticalCenter
                    radius: 6
                    color: "#14532d"
                    z: 2
                    Text { anchors.centerIn: parent; text: "Open"; color: "white"; font.bold: true }
                    MouseArea {
                      anchors.fill: parent
                      cursorShape: Qt.PointingHandCursor
                      onClicked: {
                        root.resultCursor = index
                        root.request({op: "open_navigation", safeId: modelData.safeId})
                      }
                    }
                  }
                }
              }

              Text {
                visible: root.results.length === 0
                width: body.width
                text: root.contextName === "PROD" && !root.magnusConfigured ? "Live results stay empty until Magnus is configured." : "No matching results."
                color: Color.foreground
                opacity: 0.6
                wrapMode: Text.WordWrap
              }

              Rectangle {
                visible: root.quickLook !== null
                width: body.width
                height: visible ? Style.space(100) : 0
                radius: 9
                color: Style.selectedFillFor(Color.foreground, Color.accent)
                Column {
                  anchors.fill: parent
                  anchors.margins: 12
                  spacing: 4
                  Text { text: root.quickLook ? root.quickLook.displayName : ""; color: Color.foreground; font.pixelSize: Style.font.heading; font.bold: true; textFormat: Text.PlainText }
                  Text { text: root.quickLook ? root.quickLook.subtitle : ""; color: Color.foreground; textFormat: Text.PlainText }
                  Text { text: root.quickLook ? root.quickLook.campus : ""; color: Color.foreground; opacity: 0.65; textFormat: Text.PlainText }
                }
              }
            }

            Column {
              visible: root.viewMode === "search" && root.showRecentLinks
              width: body.width
              height: visible ? implicitHeight : 0
              spacing: Style.spacing.sm

              Text { text: "Recent Links"; color: Color.foreground; font.pixelSize: Style.font.heading; font.bold: true }
              Text {
                visible: root.quickReturns.length === 0
                width: body.width
                text: root.contextName === "PROD" ?
                  "Items opened from Rock Lens will appear here (up to 20)." :
                  "Recent Links are available in PROD. Start typing to search preview data."
                color: Color.foreground
                opacity: 0.6
                wrapMode: Text.WordWrap
              }
              Repeater {
                id: quickReturnRepeater
                model: root.quickReturns
                delegate: Rectangle {
                  required property var modelData
                  required property int index
                  width: body.width
                  height: Style.space(42)
                  radius: 7
                  color: index === root.recentCursor ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
                  Column {
                    anchors.fill: parent
                    anchors.margins: 7
                    Text { width: parent.width; text: modelData.title; color: Color.foreground; font.bold: true; textFormat: Text.PlainText; elide: Text.ElideRight }
                    Text { width: parent.width; text: modelData.kind; color: Color.foreground; opacity: 0.65; textFormat: Text.PlainText; elide: Text.ElideRight }
                  }
                  MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                      root.selectRecent(index)
                      root.request({op: "open_navigation", safeId: modelData.safeId})
                    }
                  }
                }
              }
            }

            Column {
              visible: root.viewMode === "personal"
              width: body.width
              height: visible ? implicitHeight : 0
              spacing: Style.spacing.sm

              Text { text: "Personal Links"; color: Color.foreground; font.pixelSize: Style.font.heading; font.bold: true }
              Text {
                visible: root.personalLinks.length === 0
                width: body.width
                text: root.contextName !== "PROD" ? "Switch to PROD to load your Rock bookmarks." :
                  root.magnusConfigured ? "No same-site Personal Links were returned." : "Magnus setup is needed to load Personal Links."
                color: Color.foreground
                opacity: 0.6
                wrapMode: Text.WordWrap
              }
              Repeater {
                id: personalLinkRepeater
                model: root.personalLinks
                delegate: Rectangle {
                  required property var modelData
                  required property int index
                  width: body.width
                  height: Style.space(42)
                  radius: 7
                  color: index === root.linkCursor ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
                  Column {
                    anchors.fill: parent
                    anchors.margins: 7
                    Text { width: parent.width; text: modelData.title; color: Color.foreground; font.bold: true; textFormat: Text.PlainText; elide: Text.ElideRight }
                    Text { width: parent.width; text: modelData.section + (modelData.isShared ? " · Shared" : ""); color: Color.foreground; opacity: 0.65; textFormat: Text.PlainText; elide: Text.ElideRight }
                  }
                  MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                      root.selectPersonalLink(index)
                      root.request({op: "open_navigation", safeId: modelData.safeId})
                    }
                  }
                }
              }
            }
          }
        }

        Text {
          width: parent.width
          text: root.feedbackText || (root.searchInFlight ? "Searching…" :
            root.scopeKey ? "Esc clear · ↑↓ navigate · Tab switch · Enter open" :
            root.showRecentLinks ? "Type to search · ↑↓ select recent · Tab Personal Links" :
            "Try g: or Alt+G · ↑↓ navigate · Enter open")
          color: Color.foreground
          opacity: 0.55
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
        }
      }
    }
  }
}
