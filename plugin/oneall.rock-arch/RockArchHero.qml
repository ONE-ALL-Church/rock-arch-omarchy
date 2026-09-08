import QtQuick
import qs.Commons
import qs.Ui

PanelHero {
  id: hero

  required property var controller

  property Item settingsButton: null
  function focusSettings() { if (settingsButton) settingsButton.forceActiveFocus(Qt.TabFocusReason) }

  title: "Rock Arch"
  meta: controller.onboardingRequired
    ? "Bridging Rock RMS and Omarchy"
    : controller.activeProfileName()
  foreground: Color.foreground
  fontFamily: Style.font.family
  trailingControl: Component {
    Button {
      id: settingsButton
      Component.onCompleted: hero.settingsButton = settingsButton
      visible: !hero.controller.onboardingFlowActive
      text: hero.controller.updateAvailable ? "Settings · Update" : "Settings"
      tooltipText: "Settings · Ctrl+,"
      selected: hero.controller.viewMode === "settings"
      fontSize: Style.font.caption
      horizontalPadding: Style.spacing.md
      focusable: true
      enabled: !hero.controller.navigationModal
      onClicked: hero.controller.openSettings(false)
    }
  }
  iconComponent: Component {
    RockArchIcon {
      iconSize: Style.font.display
      color: Color.foreground
    }
  }
}
