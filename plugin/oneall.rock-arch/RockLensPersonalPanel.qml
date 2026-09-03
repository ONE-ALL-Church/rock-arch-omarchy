pragma ComponentBehavior: Bound

import QtQuick
import qs.Commons

Column {
  id: personalPanel
  required property var controller
  property alias repeater: personalLinkRepeater

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.sm

  Text {
    text: "Personal Links"
    color: Color.foreground
    font.pixelSize: Style.font.heading
    font.bold: true
  }
  Text {
    visible: personalPanel.controller.personalLinks.length === 0
    width: parent.width
    text: personalPanel.controller.contextName !== "PROD" ? "Switch to PROD to load your Rock bookmarks." :
      personalPanel.controller.rockConfigured ? "No same-site Personal Links were returned." : "A Rock login is needed to load Personal Links."
    color: Color.foreground
    opacity: 0.6
    wrapMode: Text.WordWrap
  }
  Repeater {
    id: personalLinkRepeater
    model: personalPanel.controller.personalLinks
    delegate: Rectangle {
      id: row
      required property var modelData
      required property int index
      readonly property bool rowSelected: row.index === personalPanel.controller.linkCursor
      width: personalPanel.width
      height: Style.space(52)
      radius: 7
      color: "transparent"
      clip: true
      RockLensSelectionChrome { anchors.fill: parent; selected: parent.rowSelected }
      Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 16
        anchors.rightMargin: 10
        Text { width: parent.width; text: row.modelData.title; color: Color.foreground; font.bold: true; textFormat: Text.PlainText; elide: Text.ElideRight }
        Text { width: parent.width; text: row.modelData.section + (row.modelData.isShared ? " · Shared" : ""); color: Color.foreground; opacity: 0.65; textFormat: Text.PlainText; elide: Text.ElideRight }
      }
      MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: {
          personalPanel.controller.selectPersonalLink(row.index)
          personalPanel.controller.request({op: "open_navigation", safeId: row.modelData.safeId})
        }
      }
    }
  }
}
