pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui
import "RockArchNavigation.js" as Navigation

Column {
  id: orderSettings
  required property var controller
  property bool editing: false
  property string focusKey: ""
  property int focusDirection: 0
  readonly property var entries: controller.tabOrder
  spacing: Style.spacing.rowGap
  onVisibleChanged: if (!visible) editing = false
  onEntriesChanged: Qt.callLater(function() {
    if (!focusKey) return
    var index = entries.indexOf(focusKey)
    var row = rows.itemAt(index)
    if (row) {
      var button = focusDirection < 0 ? row.upButton : row.downButton
      if (!button.enabled) button = focusDirection < 0 ? row.downButton : row.upButton
      button.forceActiveFocus(Qt.TabFocusReason)
    }
    focusKey = ""
  })

  RowLayout {
    width: parent.width
    PanelSectionHeader { text: "TAB ORDER"; Layout.fillWidth: true }
    Button {
      id: editButton
      text: orderSettings.editing ? "Done" : "Edit"
      fontSize: Style.font.caption
      horizontalPadding: Style.spacing.sm
      verticalPadding: Style.spacing.xs
      focusable: true
      onActiveFocusChanged: orderSettings.controller.revealFocusedControl(editButton)
      onClicked: orderSettings.editing = !orderSettings.editing
    }
  }

  Text {
    width: parent.width
    text: orderSettings.editing ? "Ctrl+number follows the visible tab order."
      : orderSettings.controller.navigationTabs.map(function(tab) { return tab.label }).join(" · ")
    textFormat: Text.PlainText
    color: Qt.darker(Color.foreground, 1.4)
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }

  Column {
    visible: orderSettings.editing
    width: parent.width
    spacing: Style.spacing.xs
    Repeater {
      id: rows
      model: orderSettings.entries
      delegate: RowLayout {
        id: row
        required property string modelData
        required property int index
        property alias upButton: upButton
        property alias downButton: downButton
        width: parent.width
        spacing: Style.spacing.xs
        Text {
          Layout.fillWidth: true
          text: Navigation.label(row.modelData) +
            (row.modelData === "magnus" && !orderSettings.controller.showMagnus ? " (unavailable)" : "")
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
          elide: Text.ElideRight
        }
        Button {
          id: upButton
          text: "↑"
          tooltipText: "Move " + Navigation.label(row.modelData) + " earlier"
          Accessible.name: tooltipText
          enabled: row.index > 0
          focusable: true
          fontSize: Style.font.body
          verticalPadding: Style.spacing.xs
          onActiveFocusChanged: orderSettings.controller.revealFocusedControl(upButton)
          onClicked: {
            orderSettings.focusKey = row.modelData
            orderSettings.focusDirection = -1
            orderSettings.controller.moveTabOrder(row.modelData, -1)
          }
        }
        Button {
          id: downButton
          text: "↓"
          tooltipText: "Move " + Navigation.label(row.modelData) + " later"
          Accessible.name: tooltipText
          enabled: row.index < orderSettings.entries.length - 1
          focusable: true
          fontSize: Style.font.body
          verticalPadding: Style.spacing.xs
          onActiveFocusChanged: orderSettings.controller.revealFocusedControl(downButton)
          onClicked: {
            orderSettings.focusKey = row.modelData
            orderSettings.focusDirection = 1
            orderSettings.controller.moveTabOrder(row.modelData, 1)
          }
        }
      }
    }
    Button {
      id: resetButton
      text: "Reset order"
      fontSize: Style.font.caption
      horizontalPadding: Style.spacing.sm
      verticalPadding: Style.spacing.xs
      focusable: true
      onActiveFocusChanged: orderSettings.controller.revealFocusedControl(resetButton)
      onClicked: { orderSettings.controller.resetTabOrder(); editButton.forceActiveFocus(Qt.TabFocusReason) }
    }
  }
}
