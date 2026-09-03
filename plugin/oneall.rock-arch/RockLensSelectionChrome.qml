import QtQuick
import qs.Commons
import qs.Ui

Item {
  id: root

  property bool selected: false
  property real cornerRadius: Style.cornerRadius

  visible: selected

  BorderSurface {
    anchors.fill: parent
    radius: root.cornerRadius
    color: Style.hoverFillFor(Color.foreground, Color.accent)
    borderSpec: Border.controlSpec("hover-cursor", Color.foreground, Color.accent)
  }
}
