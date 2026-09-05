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
    model: navigation.controller.onboardingFlowActive ? [] : navigation.controller.navigationTabs

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

      onClicked: navigation.controller.openTab(tab.modelData.key)
    }
  }

  Item { Layout.fillWidth: true }

}
