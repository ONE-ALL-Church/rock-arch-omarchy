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
      PathSvg { path: "M2 21 5 9 9 3h6l4 6 3 12h-6l-1-8c-.25-2.5-1.2-4-3-4s-2.75 1.5-3 4l-1 8Z" }
    }
  }
}
