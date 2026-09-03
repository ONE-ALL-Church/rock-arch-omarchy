pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: finishSetup

  required property var controller
  property alias primaryButton: continueButton
  readonly property color dim: Qt.darker(Color.foreground, 1.4)
  readonly property bool inputActive: visible

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.panelGap

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap

    Text {
      width: parent.width
      text: "Finish setup"
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.heading
      font.bold: true
      wrapMode: Text.WordWrap
    }

    Text {
      width: parent.width
      text: "Choose what Rock Arch searches. Everything is included by default."
      textFormat: Text.PlainText
      color: finishSetup.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      wrapMode: Text.WordWrap
    }
  }

  Column {
    width: parent.width
    spacing: Style.spacing.rowGap

    PanelSectionHeader { text: "SEARCH CATEGORIES" }

    GridLayout {
      width: parent.width
      columns: 2
      columnSpacing: Style.spacing.rowGap
      rowSpacing: Style.spacing.sm

      Repeater {
        id: categoryRepeater
        model: finishSetup.controller.searchCategories

        delegate: Button {
          id: categoryButton

          required property var modelData
          required property int index

          Layout.fillWidth: true
          text: categoryButton.modelData.label
          selected: finishSetup.controller.onboardingCategoryEnabled(
            categoryButton.modelData.key)
          bordered: true
          leftAlign: true
          focusable: true
          fontSize: Style.font.bodySmall
          enabled: !finishSetup.controller.onboardingSetupPending
          KeyNavigation.tab: categoryButton.index === categoryRepeater.count - 1
            ? (finishSetup.controller.updateManaged ? automaticUpdatesButton : continueButton)
            : categoryRepeater.itemAt(categoryButton.index + 1)
          KeyNavigation.backtab: categoryButton.index === 0
            ? continueButton
            : categoryRepeater.itemAt(categoryButton.index - 1)
          Keys.onEscapePressed: finishSetup.controller.completeOnboardingSetup()
          onActiveFocusChanged: finishSetup.controller.revealFocusedControl(categoryButton)
          onClicked: finishSetup.controller.toggleOnboardingCategory(
            categoryButton.modelData.key)
        }
      }
    }

    Text {
      visible: finishSetup.controller.onboardingEnabledCategories.length === 0
      width: parent.width
      text: "Choose at least one search category."
      textFormat: Text.PlainText
      color: Color.urgent
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }
  }

  Column {
    visible: finishSetup.controller.updateManaged
    width: parent.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.rowGap

    PanelSectionHeader { text: "UPDATES" }

    Button {
      id: automaticUpdatesButton
      width: parent.width
      text: finishSetup.controller.onboardingAutomaticUpdates
        ? "Automatic updates · On"
        : "Automatic updates · Off"
      selected: finishSetup.controller.onboardingAutomaticUpdates
      bordered: true
      leftAlign: true
      focusable: true
      fontSize: Style.font.bodySmall
      enabled: !finishSetup.controller.onboardingSetupPending
      KeyNavigation.tab: continueButton
      KeyNavigation.backtab: categoryRepeater.itemAt(categoryRepeater.count - 1)
      Keys.onEscapePressed: finishSetup.controller.completeOnboardingSetup()
      onActiveFocusChanged: finishSetup.controller.revealFocusedControl(
        automaticUpdatesButton)
      onClicked: finishSetup.controller.onboardingAutomaticUpdates =
        !finishSetup.controller.onboardingAutomaticUpdates
    }

    Text {
      width: parent.width
      text: "When enabled, Rock Arch checks daily and installs validated updates."
      textFormat: Text.PlainText
      color: finishSetup.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }
  }

  RowLayout {
    width: parent.width

    Text {
      Layout.fillWidth: true
      text: "You can change these choices later in Settings."
      textFormat: Text.PlainText
      color: finishSetup.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }

    Button {
      id: continueButton
      text: finishSetup.controller.onboardingSetupPending
        ? "Saving…"
        : "Continue to Search"
      bordered: true
      focusable: true
      enabled: !finishSetup.controller.onboardingSetupPending &&
        finishSetup.controller.onboardingEnabledCategories.length > 0
      KeyNavigation.tab: categoryRepeater.itemAt(0)
      KeyNavigation.backtab: finishSetup.controller.updateManaged
        ? automaticUpdatesButton
        : categoryRepeater.itemAt(categoryRepeater.count - 1)
      Keys.onEscapePressed: finishSetup.controller.completeOnboardingSetup()
      onClicked: finishSetup.controller.completeOnboardingSetup()
    }
  }
}
