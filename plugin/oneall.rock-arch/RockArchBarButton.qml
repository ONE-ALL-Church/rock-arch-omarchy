import QtQuick
import qs.Commons
import qs.Ui

WidgetButton {
  id: button
  required property var controller

  visible: controller.preferenceShowMenuBar
  text: ""
  keepSpace: true
  hasVisualContent: true
  labelVisible: false
  active: controller.opened
  fixedWidth: button.barSize
  tooltipText: "Rock Arch" + (controller.contextName === "PROD" && controller.rockConfigured ? " · Connected" : "")
  onPressed: controller.toggle()

  Item {
    anchors.centerIn: parent
    width: Style.bar.iconCanvas
    height: width

    RockArchIcon {
      anchors.centerIn: parent
      iconSize: parent.width
      color: button.active ? button.activeColor : button.foreground
    }
  }
}
