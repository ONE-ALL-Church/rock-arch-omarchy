pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons

Column {
  id: magnusPanel
  required property var controller
  property alias repeater: magnusRepeater
  property alias buildConfirmButton: magnusBuildConfirmButton
  property alias previewPrimaryButton: magnusDownloadButton
  readonly property bool inputActive: magnusTextArea.activeFocus

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.sm

  RowLayout {
    width: parent.width
    Button {
      id: magnusBackButton
      visible: magnusPanel.controller.magnusPreview !== null || magnusPanel.controller.magnusHistory.length > 0
      text: "Back"
      focusable: true
      enabled: !magnusPanel.controller.magnusBusy
      onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusBackButton)
      onClicked: magnusPanel.controller.magnusBack()
    }
    Text {
      Layout.fillWidth: true
      text: magnusPanel.controller.magnusPreview ? magnusPanel.controller.magnusPreview.title : magnusPanel.controller.magnusFolderTitle
      color: Color.foreground
      font.pixelSize: Style.font.heading
      font.bold: true
      textFormat: Text.PlainText
      elide: Text.ElideMiddle
    }
    Text {
      text: "Files and mobile apps"
      color: "#86efac"
      font.pixelSize: Style.font.bodySmall
      font.bold: true
    }
    Button {
      id: magnusRefreshButton
      text: "R · Refresh"
      focusable: true
      enabled: !magnusPanel.controller.magnusBusy && !magnusPanel.controller.magnusActionBusy
      onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusRefreshButton)
      onClicked: magnusPanel.controller.refreshMagnus()
    }
  }

  Rectangle {
    visible: magnusPanel.controller.pendingMagnusBuildId !== "" && !magnusPanel.controller.pendingMagnusBuildRecent
    width: magnusPanel.width
    height: visible ? buildMagnusConfirm.implicitHeight + 24 : 0
    radius: 9
    color: Qt.rgba(0.45, 0.2, 0.05, 0.35)
    border.width: 1
    border.color: "#f59e0b"
    ColumnLayout {
      id: buildMagnusConfirm
      anchors.fill: parent
      anchors.margins: 12
      spacing: 8
      Text { Layout.fillWidth: true; text: "Deploy " + magnusPanel.controller.pendingMagnusBuildTitle + "?"; color: Color.foreground; font.bold: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText }
      Text { Layout.fillWidth: true; text: magnusPanel.controller.deploymentSummary(magnusPanel.controller.pendingMagnusBuildTitle) + ". Press Enter to start the production build, or Esc to cancel."; color: Color.foreground; opacity: 0.68; wrapMode: Text.WordWrap; textFormat: Text.PlainText }
      RowLayout {
        Button {
          id: magnusBuildCancelButton
          text: "Cancel"
          focusable: true
          enabled: !magnusPanel.controller.magnusActionBusy
          KeyNavigation.right: magnusBuildConfirmButton
          KeyNavigation.tab: magnusBuildConfirmButton
          KeyNavigation.backtab: magnusBuildConfirmButton
          Keys.onEscapePressed: magnusPanel.controller.cancelMagnusBuild()
          onClicked: magnusPanel.controller.cancelMagnusBuild()
        }
        Button {
          id: magnusBuildConfirmButton
          text: magnusPanel.controller.magnusActionBusy ? "Deploying…" : "Deploy now"
          focusable: true
          enabled: !magnusPanel.controller.magnusActionBusy
          KeyNavigation.left: magnusBuildCancelButton
          KeyNavigation.tab: magnusBuildCancelButton
          KeyNavigation.backtab: magnusBuildCancelButton
          Keys.onEscapePressed: magnusPanel.controller.cancelMagnusBuild()
          onClicked: magnusPanel.controller.confirmMagnusBuild()
        }
        Item { Layout.fillWidth: true }
      }
    }
  }

  Text {
    visible: magnusPanel.controller.magnusBusy
    width: parent.width
    text: "Opening Magnus…"
    color: Color.foreground
    opacity: 0.6
  }

  Column {
    visible: magnusPanel.controller.magnusPreview !== null && !magnusPanel.controller.magnusBusy
    width: parent.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.sm
    Text {
      width: parent.width
      text: magnusPanel.controller.magnusPreview ? "SHA-256 · " + magnusPanel.controller.magnusPreview.sha256 : ""
      color: Color.foreground
      opacity: 0.55
      font.pixelSize: Style.font.bodySmall
      textFormat: Text.PlainText
      elide: Text.ElideMiddle
    }
    RowLayout {
      width: parent.width
      spacing: 6
      Button {
        id: magnusDownloadButton
        text: magnusPanel.controller.magnusActionBusy ? "Working…" : "D · Download"
        focusable: true
        enabled: !magnusPanel.controller.magnusActionBusy
        onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusDownloadButton)
        onClicked: magnusPanel.controller.runMagnusAction("magnus_download", "")
      }
      Button {
        id: magnusCopyButton
        visible: magnusPanel.controller.hasMagnusAction("copy")
        text: "C · Copy"
        focusable: true
        enabled: !magnusPanel.controller.magnusActionBusy
        onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusCopyButton)
        onClicked: magnusPanel.controller.runMagnusAction("magnus_copy", "content")
      }
      Button {
        id: magnusHashButton
        text: "H · Copy hash"
        focusable: true
        enabled: !magnusPanel.controller.magnusActionBusy
        onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusHashButton)
        onClicked: magnusPanel.controller.runMagnusAction("magnus_copy", "hash")
      }
      Button {
        id: magnusOpenButton
        visible: magnusPanel.controller.hasMagnusAction("view")
        text: "O · Open in Rock"
        focusable: true
        enabled: !magnusPanel.controller.magnusActionBusy
        onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusOpenButton)
        onClicked: magnusPanel.controller.runMagnusAction("magnus_open", "")
      }
      Item { Layout.fillWidth: true }
    }
    Text {
      visible: magnusPanel.controller.magnusPreview && magnusPanel.controller.magnusPreview.previewAvailable !== true
      width: parent.width
      text: "Preview is unavailable for this binary or large file. You can still download it or copy its hash."
      color: Color.foreground
      opacity: 0.68
      wrapMode: Text.WordWrap
    }
    ScrollView {
      visible: magnusPanel.controller.magnusPreview && magnusPanel.controller.magnusPreview.previewAvailable === true
      width: parent.width
      height: visible ? Style.space(320) : 0
      clip: true
      TextArea {
        id: magnusTextArea
        text: magnusPanel.controller.magnusPreview ? magnusPanel.controller.magnusPreview.content : ""
        readOnly: true
        selectByMouse: true
        wrapMode: TextEdit.NoWrap
        font.family: "monospace"
        color: Color.foreground
        background: Rectangle {
          radius: 7
          color: Qt.rgba(1, 1, 1, 0.05)
          border.width: 1
          border.color: Qt.rgba(1, 1, 1, 0.10)
        }
        Keys.onEscapePressed: magnusPanel.controller.magnusBack()
      }
    }
  }

  Text {
    visible: magnusPanel.controller.magnusPreview === null && !magnusPanel.controller.magnusBusy && magnusPanel.controller.magnusItems.length === 0
    width: parent.width
    text: "This Magnus folder is empty."
    color: Color.foreground
    opacity: 0.6
    wrapMode: Text.WordWrap
  }

  Repeater {
    id: magnusRepeater
    model: magnusPanel.controller.magnusPreview === null ? magnusPanel.controller.magnusItems : []
    delegate: Rectangle {
      id: itemRow
      required property var modelData
      required property int index
      readonly property bool rowSelected: itemRow.index === magnusPanel.controller.magnusCursor
      width: magnusPanel.width
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
        anchors.rightMargin: itemRow.modelData.actions && itemRow.modelData.actions.indexOf("build") >= 0 ? 108 : 10
        Text {
          width: parent.width
          text: (itemRow.modelData.kind === "folder" ? "▸ " : "") + itemRow.modelData.title
          color: Color.foreground
          font.bold: true
          textFormat: Text.PlainText
          elide: Text.ElideRight
        }
        Text {
          width: parent.width
          text: itemRow.modelData.kind === "folder" ?
            (itemRow.modelData.actions && itemRow.modelData.actions.indexOf("build") >= 0 ? "Mobile app · " + magnusPanel.controller.deploymentSummary(itemRow.modelData.title) : "Folder · Enter to open") :
            "File · preview and download"
          color: Color.foreground
          opacity: 0.55
          font.pixelSize: Style.font.bodySmall
          textFormat: Text.PlainText
          elide: Text.ElideRight
        }
      }
      MouseArea {
        anchors.fill: parent
        anchors.rightMargin: itemRow.modelData.actions && itemRow.modelData.actions.indexOf("build") >= 0 ? 102 : 0
        cursorShape: Qt.PointingHandCursor
        onClicked: {
          magnusPanel.controller.selectMagnus(itemRow.index)
          magnusPanel.controller.activateMagnus(itemRow.index)
        }
      }
      Button {
        visible: itemRow.modelData.actions && itemRow.modelData.actions.indexOf("build") >= 0
        width: 92
        height: 32
        anchors.right: parent.right
        anchors.rightMargin: 7
        anchors.verticalCenter: parent.verticalCenter
        text: "B · Deploy"
        enabled: !magnusPanel.controller.magnusBusy && !magnusPanel.controller.magnusActionBusy
        z: 2
        onClicked: {
          magnusPanel.controller.selectMagnus(itemRow.index)
          magnusPanel.controller.prepareMagnusBuild(itemRow.modelData.safeId, itemRow.modelData.title, false)
        }
      }
    }
  }
}
