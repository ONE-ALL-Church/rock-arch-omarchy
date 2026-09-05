pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: personalPanel

  required property var controller
  property alias repeater: personalLinkRepeater
  property alias addButton: addLinkButton
  readonly property bool inputActive: viewDropdown.popupOpen
  readonly property color dim: Qt.darker(Color.foreground, 1.4)
  function openViewMenu() { viewDropdown.open() }

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.rowGap

  RowLayout {
    width: parent.width
    PanelSectionHeader { text: "PERSONAL LINKS"; Layout.fillWidth: true }
    Dropdown {
      id: viewDropdown
      Layout.preferredWidth: Style.space(132)
      label: "Links view"
      showLabel: false
      value: personalPanel.controller.preferencePersonalLinksView
      options: [{value: "groups", label: "Groups"}, {value: "alpha", label: "Alphabetical"}]
      Accessible.name: "Links view"
      onChanged: function(value) { personalPanel.controller.setLinkView(value) }
    }
    Button {
      id: addLinkButton
      text: "Add link"
      tooltipText: "Add a Personal Link · Ctrl+N"
      focusable: true
      visible: personalPanel.controller.rockConfigured && personalPanel.controller.contextName === "PROD"
      onClicked: personalPanel.controller.beginPersonalLink("")
    }
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
          ? "Add a link here or save a Search result. Bookmarks saved in Rock also appear here."
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
      readonly property bool nested: personalPanel.controller.preferencePersonalLinksView === "groups" && !modelData.group
      readonly property real inset: nested ? Style.spacing.lg : 0

      width: personalPanel.width
      height: Style.space(modelData.group ? 44 : (nested ? 40 : 54))
      clip: true
      Accessible.role: Accessible.Button
      Accessible.name: modelData.title
      Accessible.description: modelData.group
        ? (modelData.expanded ? "Expanded" : "Collapsed") + ", " + modelData.count + " links"
        : "Open Personal Link"
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
        anchors.rightMargin: Style.spacing.rowPaddingX + (row.modelData.group ? Style.space(row.modelData.isShared ? 98 : 52) : 0)
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
        anchors.rightMargin: Style.spacing.rowPaddingX
        anchors.verticalCenter: parent.verticalCenter
        text: String(row.modelData.count) + (row.modelData.isShared ? " · Shared" : "")
        textFormat: Text.PlainText
        color: personalPanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }

      MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: {
          personalPanel.controller.selectPersonalLink(row.index)
          personalPanel.controller.linkView.activate(row.index)
        }
      }
    }
  }
}
