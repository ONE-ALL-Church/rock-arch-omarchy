pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

RowLayout {
  id: navigation

  required property var controller

  spacing: Style.spacing.xs

  Repeater {
    model: navigation.controller.onboardingFlowActive ? [] :
      (navigation.controller.showMagnus
        ? [
            { key: "search", label: "Search", shortcut: "Ctrl+1" },
            { key: "personal", label: "Links", shortcut: "Ctrl+2" },
            { key: "knowledge", label: "Knowledge", shortcut: "Alt+K" },
            { key: "magnus", label: "Magnus", shortcut: "Ctrl+3" }
          ]
        : [
            { key: "search", label: "Search", shortcut: "Ctrl+1" },
            { key: "personal", label: "Links", shortcut: "Ctrl+2" },
            { key: "knowledge", label: "Knowledge", shortcut: "Alt+K" }
          ])

    delegate: Button {
      id: tab

      required property var modelData

      text: tab.modelData.label
      tooltipText: tab.modelData.label + " · " + tab.modelData.shortcut
      selected: navigation.controller.viewMode === tab.modelData.key
      fontSize: Style.font.caption
      horizontalPadding: Style.spacing.lg
      verticalPadding: Style.spacing.xs
      focusable: false

      onClicked: {
        if (tab.modelData.key === "search") navigation.controller.focusSearch()
        else if (tab.modelData.key === "personal") navigation.controller.selectPersonalLink(0)
        else if (tab.modelData.key === "knowledge") navigation.controller.openKnowledge()
        else navigation.controller.openMagnus()
      }
    }
  }

  Item { Layout.fillWidth: true }

  Button {
    visible: !navigation.controller.onboardingFlowActive
    text: "Settings" + (navigation.controller.updateAvailable ? "  •" : "")
    tooltipText: "Settings · Ctrl+4"
    selected: navigation.controller.viewMode === "settings"
    fontSize: Style.font.caption
    horizontalPadding: Style.spacing.lg
    verticalPadding: Style.spacing.xs
    focusable: false
    onClicked: navigation.controller.openSettings(false)
  }

}
