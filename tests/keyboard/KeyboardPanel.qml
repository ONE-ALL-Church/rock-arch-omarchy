import QtQuick
Window {
 id: panel
 required property Item anchorItem
 required property QtObject bar
 property var owner
 property bool open: false
 property Item focusTarget
 property int contentWidth: 430
 property int contentHeight: 600
 default property alias contentItem: holder.children
 width: contentWidth
 height: contentHeight
 visible: open
 onOpenChanged: if (open) Qt.callLater(function() { panel.requestActivate(); if (focusTarget) focusTarget.forceActiveFocus() })
 function fittedContentWidth(value) { return value }
 function fittedContentHeight(value, cap) { return Math.min(value, cap) }
 Item { id: holder; anchors.fill: parent }
}
