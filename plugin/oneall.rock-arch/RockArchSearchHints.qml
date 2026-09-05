pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

FocusScope {
  id: hints
  required property var options
  property bool expanded: false
  readonly property bool inputActive: activeFocus
  signal selected(string key)
  signal exitRequested(int direction)
  implicitHeight: content.implicitHeight
  onVisibleChanged: if (!visible) expanded = false

  function controls() {
    var items = []
    for (var i = 0; i < common.count; i++) items.push(common.itemAt(i))
    if (more.visible) items.push(more)
    if (expanded)
      for (var j = 0; j < remaining.count; j++) items.push(remaining.itemAt(j))
    return items
  }
  function focusFirst() {
    var items = controls()
    if (items.length) items[0].forceActiveFocus(Qt.TabFocusReason)
  }
  Keys.onPressed: function(event) {
    if (event.key === Qt.Key_Escape) {
      if (expanded) { expanded = false; more.forceActiveFocus(Qt.TabFocusReason) }
      else exitRequested(-1)
      event.accepted = true
    } else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
      var direction = event.key === Qt.Key_Backtab || (event.modifiers & Qt.ShiftModifier) ? -1 : 1
      var items = controls()
      var index = items.findIndex(function(item) { return item.activeFocus }) + direction
      if (index < 0 || index >= items.length) exitRequested(direction)
      else items[index].forceActiveFocus(Qt.TabFocusReason)
      event.accepted = true
    }
  }

  Column {
    id: content
    width: parent.width
    spacing: Style.spacing.xs

    RowLayout {
      width: parent.width
      spacing: Style.spacing.xs
      Repeater {
        id: common
        model: hints.options.slice(0, 2)
        delegate: Button {
          required property var modelData
          text: modelData.prefix + ": " + modelData.label
          tooltipText: "Search " + modelData.label + " · " + modelData.shortcut
          fontSize: Style.font.caption
          horizontalPadding: Style.spacing.sm
          verticalPadding: Style.spacing.xs
          focusable: true
          onClicked: hints.selected(modelData.prefix)
        }
      }
      Button {
        id: more
        visible: hints.options.length > 2
        text: hints.expanded ? "Less" : "More"
        tooltipText: hints.expanded ? "Hide other categories" : "Show all search categories"
        Accessible.name: tooltipText
        fontSize: Style.font.caption
        horizontalPadding: Style.spacing.sm
        verticalPadding: Style.spacing.xs
        focusable: true
        onClicked: hints.expanded = !hints.expanded
      }
      Item { Layout.fillWidth: true }
    }

    GridLayout {
      visible: hints.expanded
      width: parent.width
      columns: 2
      columnSpacing: Style.spacing.xs
      rowSpacing: Style.spacing.xs
      Repeater {
        id: remaining
        model: hints.options.slice(2)
        delegate: Button {
          required property var modelData
          Layout.fillWidth: true
          Layout.preferredWidth: 1
          Layout.minimumWidth: 0
          text: modelData.prefix + ": " + modelData.label
          tooltipText: "Search " + modelData.label + " · " + modelData.shortcut
          fontSize: Style.font.caption
          horizontalPadding: Style.spacing.sm
          verticalPadding: Style.spacing.xs
          leftAlign: true
          focusable: true
          onClicked: hints.selected(modelData.prefix)
        }
      }
    }
  }
}
