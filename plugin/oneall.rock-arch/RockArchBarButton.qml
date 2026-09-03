import QtQuick
import QtQuick.Effects
import qs.Commons
import qs.Ui

WidgetButton {
  id: button
  required property var controller

  visible: controller.preferenceShowMenuBar
  text: ""
  keepSpace: true
  labelVisible: false
  active: controller.opened
  fixedWidth: button.barSize
  tooltipText: "Rock Arch" + (controller.contextName === "PROD" && controller.rockConfigured ? " · Connected" : "")
  onPressed: controller.toggle()

  Item {
    anchors.centerIn: parent
    width: Style.bar.iconCanvas
    height: width
    Image {
      id: iconSource
      anchors.fill: parent
      source: Qt.resolvedUrl("assets/rock-arch.svg")
      fillMode: Image.PreserveAspectFit
      visible: false
      layer.enabled: true
    }
    MultiEffect {
      anchors.fill: iconSource
      source: iconSource
      colorization: 1.0
      colorizationColor: button.active ? button.activeColor : button.foreground
    }
  }
}
