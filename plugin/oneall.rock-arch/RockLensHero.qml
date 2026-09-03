import QtQuick
import qs.Commons
import qs.Ui

PanelHero {
  id: hero

  required property var controller

  title: "Rock Arch"
  meta: controller.onboardingRequired
    ? "Bridging Rock RMS and Omarchy"
    : controller.activeProfileName()
  detail: controller.updateAvailable ? "Update" : ""
  foreground: Color.foreground
  fontFamily: Style.font.family
  iconComponent: Component {
    RockArchIcon {
      iconSize: Style.font.display
      color: Color.foreground
    }
  }
}
