pragma ComponentBehavior: Bound

import QtQuick
import qs.Commons
import qs.Ui

Column {
  id: personalPanel

  required property var controller
  property alias repeater: personalLinkRepeater
  readonly property color dim: Qt.darker(Color.foreground, 1.4)

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.rowGap

  PanelSectionHeader {
    text: "PERSONAL LINKS"
  }

  Column {
    visible: personalPanel.controller.personalLinks.length === 0
    width: parent.width
    topPadding: Style.spacing.xxxl
    bottomPadding: Style.spacing.huge
    spacing: Style.spacing.labelGap

    Text {
      width: parent.width
      text: personalPanel.controller.contextName !== "PROD"
        ? "Personal Links are hidden in preview mode"
        : personalPanel.controller.rockConfigured
          ? "No Personal Links found"
          : "Rock login required"
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.body
      font.weight: Font.DemiBold
      horizontalAlignment: Text.AlignHCenter
    }

    Text {
      width: parent.width
      text: personalPanel.controller.contextName !== "PROD"
        ? "Return to Search to browse preview data."
        : personalPanel.controller.rockConfigured
          ? "Bookmarks saved in Rock will appear here."
          : "Open Settings to sign in."
      textFormat: Text.PlainText
      color: personalPanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
  }

  Repeater {
    id: personalLinkRepeater
    model: personalPanel.controller.personalLinks

    delegate: Item {
      id: row

      required property var modelData
      required property int index
      readonly property bool rowSelected: row.index === personalPanel.controller.linkCursor

      width: personalPanel.width
      height: Style.space(54)
      clip: true

      RockArchSelectionChrome {
        anchors.fill: parent
        selected: row.rowSelected
      }

      Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Style.spacing.rowPaddingX
        anchors.rightMargin: Style.spacing.rowPaddingX
        spacing: Style.spacing.xxs

        Text {
          width: parent.width
          text: row.modelData.title
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.weight: Font.DemiBold
          elide: Text.ElideRight
        }

        Text {
          width: parent.width
          text: row.modelData.section + (row.modelData.isShared ? " · Shared" : "")
          textFormat: Text.PlainText
          color: personalPanel.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
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
