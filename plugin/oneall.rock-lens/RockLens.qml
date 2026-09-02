import QtQuick
import QtQuick.Controls
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
  property string contextName: "DEV"
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
  property int resultCursor: -1
  property int linkCursor: -1
  readonly property int navigationCount: personalLinks.length + quickReturns.length
  readonly property string connectionText: contextName === "DEV" ? "Synthetic preview" :
    magnusConfigured ? "Live via Magnus · " + instanceDomain :
    magnusAvailable ? "Rock login required" : "Magnus unavailable"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function request(payload) {
    requestQueue = requestQueue.concat([JSON.stringify(payload) + "\n"])
    if (!brokerSocket.connected) brokerSocket.connected = true
    sendTimer.restart()
  }

  function accept(line) {
    var response
    try { response = JSON.parse(line) } catch (e) { return }
    if (!response || response.ok !== true) {
      setupBusy = false
      feedbackText = response && response.error ? String(response.error).split("_").join(" ") : "Request failed"
      return
    }
    if (response.context) contextName = response.context === "PROD" ? "PROD" : "DEV"
    if (response.instance)
      instanceDomain = String(response.instance.origin || "").replace("https://", "")
    if (response.magnus) {
      magnusAvailable = response.magnus.available === true
      magnusConfigured = response.magnus.configured === true
    }
    if (Array.isArray(response.results)) {
      results = response.results
      if (resultCursor >= results.length) resultCursor = results.length - 1
    }
    if (Array.isArray(response.personalLinks)) personalLinks = response.personalLinks
    if (Array.isArray(response.quickReturns)) quickReturns = response.quickReturns
    if (linkCursor >= navigationCount) linkCursor = navigationCount - 1
    if (viewMode === "links" && linkCursor < 0 && navigationCount) linkCursor = 0
    if (response.personalLinksAvailable !== undefined)
      personalLinksAvailable = response.personalLinksAvailable === true
    if (response.person) quickLook = response.person
    if (response.source) searchSource = String(response.source)
    if (response.refreshLive === true) {
      setupBusy = false
      setupPassword = ""
      feedbackText = "Magnus credentials saved securely"
      Qt.callLater(function() {
        root.refreshSearch()
        root.refreshNavigation()
        searchField.forceActiveFocus()
      })
    }
    if (Array.isArray(response.unavailable) && response.unavailable.length)
      feedbackText = "Unavailable: " + response.unavailable.join(", ")
    else if (response.opened === true)
      feedbackText = "Opened in Rock and added to Quick Returns"
    else if (response.source === "unavailable")
      feedbackText = "Live Rock search needs Magnus setup"
    else if (response.source)
      feedbackText = ""
  }

  function refreshSearch() { request({op: "search", query: query}) }
  function scheduleSearch() { searchTimer.restart() }
  function refreshNavigation() { request({op: "navigation_status"}) }
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
    linkCursor = -1
    quickLook = null
    panelFlick.contentY = 0
    Qt.callLater(function() { searchField.forceActiveFocus() })
  }
  function selectResult(index) {
    if (!results.length) {
      focusSearch()
      return
    }
    viewMode = "search"
    resultCursor = Math.max(0, Math.min(results.length - 1, index))
    linkCursor = -1
    quickLook = null
    Qt.callLater(function() {
      keyCatcher.forceActiveFocus()
      root.revealItem(resultRepeater.itemAt(root.resultCursor))
    })
  }
  function selectLink(index) {
    var changedView = viewMode !== "links"
    viewMode = "links"
    resultCursor = -1
    linkCursor = navigationCount ? Math.max(0, Math.min(navigationCount - 1, index)) : -1
    quickLook = null
    if (changedView) refreshNavigation()
    Qt.callLater(function() {
      keyCatcher.forceActiveFocus()
      var item = root.linkCursor < root.personalLinks.length ?
        personalLinkRepeater.itemAt(root.linkCursor) :
        quickReturnRepeater.itemAt(root.linkCursor - root.personalLinks.length)
      root.revealItem(item)
    })
  }
  function moveTab(direction) {
    if (direction >= 0) {
      if (viewMode === "search" && resultCursor < 0 && results.length)
        selectResult(0)
      else if (viewMode === "search")
        selectLink(0)
      else
        focusSearch()
      return
    }
    if (viewMode === "links") {
      if (results.length) selectResult(results.length - 1)
      else focusSearch()
    } else if (resultCursor >= 0) {
      focusSearch()
    } else {
      selectLink(navigationCount - 1)
    }
  }
  function moveCursor(dx, dy) {
    if (dx !== 0) {
      moveTab(dx)
      return
    }
    if (dy === 0) return
    if (viewMode === "search") {
      if (resultCursor < 0) {
        if (dy > 0 && results.length) selectResult(0)
        else if (dy < 0 && navigationCount) selectLink(navigationCount - 1)
        return
      }
      var nextResult = resultCursor + dy
      if (nextResult < 0) focusSearch()
      else if (nextResult >= results.length) selectLink(0)
      else selectResult(nextResult)
      return
    }
    if (!navigationCount) {
      focusSearch()
      return
    }
    var nextLink = linkCursor < 0 ? (dy > 0 ? 0 : navigationCount - 1) : linkCursor + dy
    if (nextLink < 0) {
      if (results.length) selectResult(results.length - 1)
      else focusSearch()
    } else if (nextLink >= navigationCount) {
      focusSearch()
    } else {
      selectLink(nextLink)
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
      activateResult(resultCursor)
      return
    }
    if (linkCursor < 0 || linkCursor >= navigationCount) return
    var item = linkCursor < personalLinks.length ?
      personalLinks[linkCursor] : quickReturns[linkCursor - personalLinks.length]
    request({op: "open_navigation", safeId: item.safeId})
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
    contextName = contextName === "DEV" ? "PROD" : "DEV"
    results = []
    personalLinks = []
    resultCursor = -1
    linkCursor = -1
    quickLook = null
    setupPassword = ""
    request({op: "set_context", context: contextName})
    request({op: "status"})
    refreshSearch()
    refreshNavigation()
  }
  function resetPanel() {
    query = ""
    focusSearch()
    quickLook = null
    feedbackText = ""
    request({op: "status"})
    refreshSearch()
    refreshNavigation()
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
      brokerSocket.write(payload)
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

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "ROCK " + root.contextName + (root.contextName === "PROD" && root.magnusConfigured ? "  ●" : "")
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
    contentWidth: panel.fittedContentWidth(Style.space(560))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(680))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: searchField.activeFocus || domainField.activeFocus || usernameField.activeFocus || passwordField.activeFocus
      onCloseRequested: root.close()
      onMoveRequested: function(dx, dy) { root.moveCursor(dx, dy) }
      onTabRequested: function(direction) { root.moveTab(direction) }
      onActivateRequested: root.activateCursor()

      Column {
        id: content
        width: parent.width
        spacing: Style.spacing.md

        Row {
          width: parent.width
          spacing: Style.spacing.md
          Text { text: "Rock Lens"; color: Color.foreground; font.pixelSize: Style.font.title; font.bold: true }
          Rectangle {
            width: contextLabel.implicitWidth + 16
            height: contextLabel.implicitHeight + 8
            radius: 6
            color: root.contextName === "PROD" ? "#7f1d1d" : "#14532d"
            Text { id: contextLabel; anchors.centerIn: parent; text: root.contextName; color: "white"; font.bold: true }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.switchContext() }
          }
        }

        Row {
          spacing: Style.spacing.sm
          Repeater {
            model: ["search", "links"]
            delegate: Rectangle {
              required property var modelData
              width: tabText.implicitWidth + 24
              height: Style.space(34)
              radius: 7
              color: root.viewMode === modelData ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
              Text {
                id: tabText
                anchors.centerIn: parent
                text: modelData === "search" ? "Search" : "Links"
                color: Color.foreground
                font.bold: root.viewMode === modelData
              }
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  if (modelData === "search") root.focusSearch()
                  else root.selectLink(0)
                }
              }
            }
          }
        }

        TextField {
          id: searchField
          visible: root.viewMode === "search"
          width: parent.width
          maximumLength: 120
          placeholderText: "Search People, Groups, Workflows, Jobs, Pages, Content…"
          selectByMouse: true
          inputMethodHints: Qt.ImhNoPredictiveText
          onTextEdited: {
            root.resultCursor = -1
            root.quickLook = null
            root.scheduleSearch()
          }
          Keys.priority: Keys.BeforeItem
          Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Escape) {
              root.close()
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
              root.activateResult(0)
              event.accepted = true
            }
          }
        }
        Text {
          visible: root.viewMode === "links"
          width: parent.width
          text: "Personal Links and launcher Quick Returns"
          color: Color.foreground
          opacity: 0.75
          elide: Text.ElideRight
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
              visible: root.viewMode === "search"
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
                  height: Style.space(54)
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
                    visible: modelData.canOpen === true && root.contextName === "PROD"
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
              visible: root.viewMode === "links"
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
                  height: Style.space(46)
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
                      root.selectLink(index)
                      root.request({op: "open_navigation", safeId: modelData.safeId})
                    }
                  }
                }
              }

              Text { text: "Quick Returns"; color: Color.foreground; font.pixelSize: Style.font.heading; font.bold: true }
              Text { visible: root.quickReturns.length === 0; width: body.width; text: "Items opened from Rock Lens will appear here (up to 20)."; color: Color.foreground; opacity: 0.6; wrapMode: Text.WordWrap }
              Repeater {
                id: quickReturnRepeater
                model: root.quickReturns
                delegate: Rectangle {
                  required property var modelData
                  required property int index
                  width: body.width
                  height: Style.space(46)
                  radius: 7
                  color: root.personalLinks.length + index === root.linkCursor ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
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
                      root.selectLink(root.personalLinks.length + index)
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
          text: root.feedbackText || "↑/↓ move · Tab next · Enter/Space open"
          color: Color.foreground
          opacity: 0.55
          wrapMode: Text.WordWrap
          textFormat: Text.PlainText
        }
      }
    }
  }
}
