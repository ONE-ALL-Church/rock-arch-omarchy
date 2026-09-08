pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

ColumnLayout {
  id: help
  required property var controller
  property alias closeButton: closeButton
  spacing: Style.spacing.md
  RowLayout {
    Layout.fillWidth: true
    PanelSectionHeader { text: "KEYBOARD & SEARCH"; Layout.fillWidth: true }
    Button {
      id: closeButton
      text: "Back"
      focusable: true
      onClicked: help.controller.closeKeyboardHelp()
    }
  }
  Text {
    Layout.fillWidth: true
    text: "Ctrl+Tab / Ctrl+Shift+Tab  Switch workspaces\nCtrl+1–4  Open a workspace by position\nTab / Shift+Tab  Move between controls\nArrow keys  Move within tabs or lists\nCtrl+F  Focus search or Model Map filter\nCtrl+,  Settings    Esc  Back or close\nCtrl+B  Bookmark    Ctrl+N  Add link or section"
    textFormat: Text.PlainText
    color: Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
    wrapMode: Text.WordWrap
  }
  Text {
    Layout.fillWidth: true
    text: "Search by name or ID, or choose a prefix. Alt+0 clears the search scope."
    textFormat: Text.PlainText
    color: Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
    wrapMode: Text.WordWrap
  }
  GridLayout {
    Layout.fillWidth: true
    columns: 2
    Repeater {
      model: help.controller.searchScopeOptions
      Button {
        required property var modelData
        Layout.fillWidth: true
        text: modelData.prefix + ": " + modelData.label
        tooltipText: modelData.shortcut
        fontSize: Style.font.caption
        horizontalPadding: Style.spacing.sm
        focusable: true
        onClicked: {
          help.controller.keyboardHelpVisible = false
          help.controller.applyScope(modelData.prefix)
        }
      }
    }
  }
}
