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
  property string query: ""
  property var results: []
  property var quickLook: null
  property string healthText: "mock healthy · live unknown"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function request(payload) {
    if (!brokerSocket.connected) brokerSocket.connected = true
    pending.payload = JSON.stringify(payload) + "\n"
    sendTimer.restart()
  }

  function accept(line) {
    var response
    try { response = JSON.parse(line) } catch (e) { return }
    if (!response || response.ok !== true) return
    if (response.context) contextName = response.context === "PROD" ? "PROD" : "DEV"
    if (Array.isArray(response.results)) results = response.results
    if (response.person) quickLook = response.person
    if (Array.isArray(response.capabilities)) {
      var parts = []
      for (var i = 0; i < response.capabilities.length; i++)
        parts.push(String(response.capabilities[i].name) + " " + String(response.capabilities[i].state))
      healthText = parts.join(" · ")
    }
  }

  function refreshSearch() { request({op: "search", query: query}) }
  function resetPanel() {
    query = ""
    quickLook = null
    request({op: "status"})
    refreshSearch()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  onOpenedChanged: if (opened) resetPanel()

  Process {
    id: brokerProcess
    command: ["python3", "-m", "rock_lens_broker"]
    workingDirectory: root.projectPath
    running: true
  }

  QtObject { id: pending; property string payload: "" }
  Timer {
    id: sendTimer
    interval: 40
    onTriggered: {
      if (brokerSocket.connected) { brokerSocket.write(pending.payload); brokerSocket.flush() }
      else retryTimer.restart()
    }
  }
  Timer { id: retryTimer; interval: 120; onTriggered: { brokerSocket.connected = true; sendTimer.restart() } }

  Socket {
    id: brokerSocket
    path: root.socketPath
    connected: false
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
    text: "ROCK " + root.contextName
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
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(560))
    contentHeight: panel.fittedContentHeight(content.implicitHeight, Style.space(680))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onActivateRequested: {
        if (root.results.length && root.results[0].category === "People")
          root.request({op: "person_quick_look", safeId: root.results[0].safeId})
      }
      onTextKey: function(t) { root.query = (root.query + t).slice(0, 120); root.quickLook = null; root.refreshSearch() }
      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Backspace) {
          root.query = root.query.slice(0, -1); root.quickLook = null; root.refreshSearch(); event.accepted = true
        }
      }

      Column {
        id: content
        width: parent.width
        spacing: Style.spacing.md

        Row {
          width: parent.width
          spacing: Style.spacing.md
          Text { text: "Rock Lens"; color: Color.foreground; font.pixelSize: Style.font.title; font.bold: true }
          Rectangle { width: contextLabel.implicitWidth + 16; height: contextLabel.implicitHeight + 8; radius: 6; color: root.contextName === "PROD" ? "#7f1d1d" : "#14532d"
            Text { id: contextLabel; anchors.centerIn: parent; text: root.contextName; color: "white"; font.bold: true }
            MouseArea { anchors.fill: parent; onClicked: root.request({op: "set_context", context: root.contextName === "DEV" ? "PROD" : "DEV"}) }
          }
        }

        Text { width: parent.width; text: root.query || "Search People, Groups, Workflows, Jobs, Pages, Content Channel Items…"; color: Color.foreground; opacity: root.query ? 1 : 0.55; elide: Text.ElideRight }
        Text { width: parent.width; text: root.healthText; color: Color.foreground; opacity: 0.55; font.pixelSize: Style.font.bodySmall }
        Repeater {
          model: root.results
          delegate: Rectangle {
            required property var modelData
            required property int index
            width: content.width; height: Style.space(52); radius: 7; color: index === 0 ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
            Column { anchors.fill: parent; anchors.margins: 7
              Text { text: modelData.title; color: Color.foreground; font.bold: true; textFormat: Text.PlainText }
              Text { text: modelData.category + " · " + modelData.subtitle + " · " + modelData.status; color: Color.foreground; opacity: 0.65; textFormat: Text.PlainText }
            }
          }
        }
        Rectangle {
          visible: root.quickLook !== null
          width: content.width; height: visible ? Style.space(100) : 0; radius: 9; color: Style.selectedFillFor(Color.foreground, Color.accent)
          Column { anchors.fill: parent; anchors.margins: 12; spacing: 4
            Text { text: root.quickLook ? root.quickLook.displayName : ""; color: Color.foreground; font.pixelSize: Style.font.heading; font.bold: true; textFormat: Text.PlainText }
            Text { text: root.quickLook ? root.quickLook.subtitle : ""; color: Color.foreground; textFormat: Text.PlainText }
            Text { text: root.quickLook ? root.quickLook.campus : ""; color: Color.foreground; opacity: 0.65; textFormat: Text.PlainText }
          }
        }
        Text { width: parent.width; text: "Type to filter · Enter opens privacy-safe Person Quick Look · read-only"; color: Color.foreground; opacity: 0.5; wrapMode: Text.WordWrap }
      }
    }
  }
}
