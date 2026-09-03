import QtQuick
import qs.Commons

Item {
  id: root

  property bool selected: false
  property real cornerRadius: 7

  visible: selected

  Rectangle {
    anchors.fill: parent
    radius: root.cornerRadius
    color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.18)
    border.width: 2
    border.color: Color.accent
  }

  Rectangle {
    width: 4
    height: Math.max(0, parent.height - 12)
    anchors.left: parent.left
    anchors.leftMargin: 5
    anchors.verticalCenter: parent.verticalCenter
    radius: 2
    color: Color.accent
  }
}
