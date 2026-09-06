pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: panel
  required property var model
  property alias cancelButton: cancelButton
  spacing: Style.spacing.md
  Text {
    width: parent.width
    text: panel.model.title
    textFormat: Text.PlainText
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    font.weight: Font.DemiBold
    color: Color.foreground
    wrapMode: Text.WordWrap
  }
  Text {
    width: parent.width
    text: panel.model.notice
    textFormat: Text.PlainText
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
    color: Color.foreground
    wrapMode: Text.WordWrap
  }
  Text {
    width: parent.width
    visible: panel.model.lastStatus !== ""
    text: "Last recorded: " + panel.model.lastStatus + (panel.model.lastRunAt ? " · " + new Date(panel.model.lastRunAt).toLocaleString(Qt.locale(), Locale.ShortFormat) : "")
    textFormat: Text.PlainText
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
    color: Qt.darker(Color.foreground, 1.4)
    wrapMode: Text.WordWrap
  }
  RowLayout {
    width: parent.width
    spacing: Style.spacing.sm
    Button {
      id: cancelButton
      text: panel.model.phase === "confirm" || panel.model.phase === "preparing" ? "Cancel" : "Close"
      focusable: true
      bordered: true
      KeyNavigation.right: runButton.visible ? runButton : statusButton
      onClicked: panel.model.cancel()
    }
    Button {
      id: runButton
      visible: panel.model.phase === "confirm" || panel.model.phase === "sending"
      enabled: panel.model.canRun
      text: panel.model.phase === "sending" ? "Requesting…" : "Run now"
      focusable: true
      bordered: true
      KeyNavigation.left: cancelButton
      onClicked: panel.model.run()
    }
    Button {
      id: statusButton
      visible: panel.model.phase === "requested" || panel.model.phase === "uncertain"
      enabled: !panel.model.busy
      text: panel.model.busy ? "Checking…" : "Check status"
      focusable: true
      KeyNavigation.left: cancelButton
      onClicked: panel.model.checkStatus()
    }
    Item { Layout.fillWidth: true }
  }
}
