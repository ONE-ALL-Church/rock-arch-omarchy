import QtQuick
import QtQuick.Shapes
import qs.Commons

Item {
  id: root

  property color color: Color.foreground
  property real iconSize: Style.font.display

  implicitWidth: iconSize
  implicitHeight: iconSize

  Shape {
    anchors.centerIn: parent
    width: 24
    height: 24
    scale: root.iconSize / width
    antialiasing: true

    ShapePath {
      fillRule: ShapePath.OddEvenFill
      fillColor: root.color
      strokeWidth: 0
      PathSvg { path: "m1.1 21.5 2.2-6.6.9-5.6 3.2-4.2 2.7-1.5 4.9.5 3.2 3.4 2 4.7 2.7 9.3h-6.2l-.9-7.8c-.4-3-1.6-4.5-3.5-4.6-2.2-.1-3.5 1.7-3.9 4.9l-.7 7.5Zm9 0 .7-7.3c.2-1.7.6-2.4 1.4-2.4s1.2.7 1.4 2.5l.5 7.2Z" }
    }
  }
}

