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

  Column {
    visible: personalPanel.controller.linkView.rows.length === 0
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
          ? "Add a link here or bookmark a Search result. Bookmarks saved in Rock also appear here."
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
    model: personalPanel.controller.linkView.rows

    delegate: Item {
      id: row

      required property var modelData
      required property int index
      readonly property bool rowSelected: row.index === personalPanel.controller.linkCursor
      readonly property bool deletable: !!personalPanel.controller.linkView.deletionTarget(modelData)
      readonly property bool nested: personalPanel.controller.preferencePersonalLinksView === "sections" && !modelData.group
      readonly property real inset: nested ? Style.spacing.lg : 0

      width: personalPanel.width
      height: Style.space(modelData.group ? 44 : (nested ? 40 : 54))
      clip: true
      Accessible.role: Accessible.Button
      Accessible.name: modelData.title
      Accessible.description: modelData.group
        ? (modelData.expanded ? "Expanded" : "Collapsed") + ", " + modelData.count + " links"
          : modelData.empty ? "Add a link to this section" : "Open Personal Link"
      Accessible.onPressAction: personalPanel.controller.linkView.activate(row.index)

      Rectangle {
        visible: row.nested
        x: row.inset
        width: parent.width - row.inset
        height: parent.height
        color: Color.foreground
        opacity: 0.025
      }
      Rectangle {
        visible: row.nested
        x: row.inset
        width: 1
        height: parent.height
        color: Color.foreground
        opacity: 0.12
      }

      RockArchSelectionChrome {
        anchors.fill: parent
        anchors.leftMargin: row.inset
        selected: row.rowSelected
      }

      Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Style.spacing.rowPaddingX + row.inset
        anchors.rightMargin: Style.spacing.rowPaddingX + (row.deletable ? deleteButton.width + Style.spacing.sm : 0) + (row.modelData.group ? Style.space(row.modelData.isShared ? 98 : 52) : 0)
        spacing: Style.spacing.xxs

        Text {
          width: parent.width
          text: row.modelData.group ? (row.modelData.expanded ? "▾  " : "▸  ") + row.modelData.title : row.modelData.title
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.weight: Font.DemiBold
          elide: Text.ElideRight
        }

        Text {
          visible: !row.modelData.group && !row.nested
          width: parent.width
          text: row.modelData.section + (row.modelData.isShared ? " · Shared" : "")
          textFormat: Text.PlainText
          color: personalPanel.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }

      Text {
        visible: row.modelData.group
        anchors.right: parent.right
        anchors.rightMargin: Style.spacing.rowPaddingX + (row.deletable ? deleteButton.width + Style.spacing.sm : 0)
        anchors.verticalCenter: parent.verticalCenter
        text: String(row.modelData.count) + (row.modelData.isShared ? " · Shared" : "")
        textFormat: Text.PlainText
        color: personalPanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }

      HoverHandler { id: rowHover }
      MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: {
          personalPanel.controller.selectPersonalLink(row.index)
          personalPanel.controller.linkView.activate(row.index)
        }
      }
      Button {
        id: deleteButton
        anchors.right: parent.right
        anchors.rightMargin: Style.spacing.rowPaddingX
        anchors.verticalCenter: parent.verticalCenter
        width: Style.space(28)
        height: Style.space(28)
        visible: row.deletable && (row.rowSelected || rowHover.hovered || activeFocus)
        text: "×"
        foreground: hot || activeFocus ? Color.foreground : personalPanel.dim
        horizontalPadding: Style.spacing.xs
        verticalPadding: Style.spacing.xs
        tooltipText: row.modelData.group ? "Delete section and its links…" : "Delete link…"
        Accessible.role: Accessible.Button
        Accessible.name: (row.modelData.group ? "Delete section " : "Delete link ") + row.modelData.title
        Accessible.onPressAction: deleteButton.clicked()
        focusable: true
        onClicked: personalPanel.controller.beginPersonalDelete(row.modelData)
      }
    }
  }
}
