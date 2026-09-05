pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: magnusPanel

  required property var controller
  property alias repeater: magnusRepeater
  property alias buildConfirmButton: magnusBuildConfirmButton
  property alias previewPrimaryButton: magnusDownloadButton
  readonly property bool inputActive: magnusTextArea.activeFocus
  readonly property color dim: Qt.darker(Color.foreground, 1.4)

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.rowGap

  RowLayout {
    width: parent.width
    spacing: Style.spacing.sm

    Button {
      id: magnusBackButton
      visible: magnusPanel.controller.magnusPreview !== null ||
        magnusPanel.controller.magnusHistory.length > 0
      text: "Back"
      tooltipText: "Back · Esc"
      fontSize: Style.font.caption
      horizontalPadding: Style.spacing.lg
      verticalPadding: Style.spacing.xs
      focusable: true
      enabled: !magnusPanel.controller.magnusBusy
      onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusBackButton)
      onClicked: magnusPanel.controller.magnusBack()
    }

    PanelSectionHeader {
      Layout.fillWidth: true
      text: (magnusPanel.controller.magnusPreview
        ? magnusPanel.controller.magnusPreview.title
        : magnusPanel.controller.magnusFolderTitle).toUpperCase()
      elide: Text.ElideMiddle
    }

    Button {
      id: magnusRefreshButton
      text: magnusPanel.controller.magnusBusy ? "Refreshing…" : "Refresh"
      tooltipText: "Refresh Magnus · R"
      fontSize: Style.font.caption
      horizontalPadding: Style.spacing.lg
      verticalPadding: Style.spacing.xs
      focusable: true
      enabled: !magnusPanel.controller.magnusBusy && !magnusPanel.controller.magnusActionBusy
      onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusRefreshButton)
      onClicked: magnusPanel.controller.refreshMagnus()
    }
  }

  BorderSurface {
    visible: magnusPanel.controller.pendingMagnusBuildId !== "" &&
      !magnusPanel.controller.pendingMagnusBuildRecent
    width: parent.width
    implicitHeight: buildMagnusConfirm.implicitHeight + Style.spacing.rowPaddingX * 2
    color: Style.normalFillFor(Color.urgent, Color.urgent)
    borderSpec: Border.controlSpec("normal", Color.urgent, Color.urgent)
    radius: Style.cornerRadius

    ColumnLayout {
      id: buildMagnusConfirm
      anchors.fill: parent
      anchors.margins: Style.spacing.rowPaddingX
      spacing: Style.spacing.labelGap

      Text {
        Layout.fillWidth: true
        text: "Deploy " + magnusPanel.controller.pendingMagnusBuildTitle + "?"
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
      }

      Text {
        Layout.fillWidth: true
        text: magnusPanel.controller.deploymentSummary(
          magnusPanel.controller.pendingMagnusBuildTitle) +
          (magnusPanel.controller.contextName === "DEV"
            ? ". Preview the confirmation flow without starting a build."
            : ". This starts a production mobile-app build.")
        textFormat: Text.PlainText
        color: magnusPanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      RowLayout {
        Item { Layout.fillWidth: true }

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
          foreground: Color.urgent
          bordered: true
          focusable: true
          enabled: !magnusPanel.controller.magnusActionBusy
          KeyNavigation.left: magnusBuildCancelButton
          KeyNavigation.tab: magnusBuildCancelButton
          KeyNavigation.backtab: magnusBuildCancelButton
          Keys.onEscapePressed: magnusPanel.controller.cancelMagnusBuild()
          onClicked: magnusPanel.controller.confirmMagnusBuild()
        }
      }
    }
  }

  Column {
    visible: magnusPanel.controller.magnusBusy
    width: parent.width
    topPadding: Style.spacing.xxxl
    bottomPadding: Style.spacing.huge
    spacing: Style.spacing.labelGap

    Text {
      width: parent.width
      text: "Opening Magnus…"
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.body
      font.weight: Font.DemiBold
      horizontalAlignment: Text.AlignHCenter
    }

    Text {
      width: parent.width
      text: "Loading files and mobile apps."
      textFormat: Text.PlainText
      color: magnusPanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      horizontalAlignment: Text.AlignHCenter
    }
  }

  Column {
    visible: magnusPanel.controller.magnusPreview !== null &&
      !magnusPanel.controller.magnusBusy
    width: parent.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.rowGap

    Text {
      width: parent.width
      text: magnusPanel.controller.magnusPreview
        ? "SHA-256 · " + magnusPanel.controller.magnusPreview.sha256
        : ""
      textFormat: Text.PlainText
      color: magnusPanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      elide: Text.ElideMiddle
    }

    RowLayout {
      width: parent.width
      spacing: Style.spacing.sm

      Button {
        id: magnusDownloadButton
        text: magnusPanel.controller.magnusActionBusy ? "Working…" : "D · Download"
        bordered: true
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
        text: "H · Hash"
        tooltipText: "Copy SHA-256 hash · H"
        focusable: true
        enabled: !magnusPanel.controller.magnusActionBusy
        onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusHashButton)
        onClicked: magnusPanel.controller.runMagnusAction("magnus_copy", "hash")
      }

      Button {
        id: magnusOpenButton
        visible: magnusPanel.controller.hasMagnusAction("view")
        text: "O · Open"
        tooltipText: "Open in Rock · O"
        focusable: true
        enabled: !magnusPanel.controller.magnusActionBusy
        onActiveFocusChanged: magnusPanel.controller.revealFocusedControl(magnusOpenButton)
        onClicked: magnusPanel.controller.runMagnusAction("magnus_open", "")
      }

      Item { Layout.fillWidth: true }
    }

    Column {
      visible: magnusPanel.controller.magnusPreview &&
        magnusPanel.controller.magnusPreview.previewAvailable !== true
      width: parent.width
      topPadding: Style.spacing.xxxl
      bottomPadding: Style.spacing.huge
      spacing: Style.spacing.labelGap

      Text {
        width: parent.width
        text: "Preview unavailable"
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
      }

      Text {
        width: parent.width
        text: "This file can still be downloaded or its hash copied."
        textFormat: Text.PlainText
        color: magnusPanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
      }
    }

    QQC.ScrollView {
      visible: magnusPanel.controller.magnusPreview &&
        magnusPanel.controller.magnusPreview.previewAvailable === true
      width: parent.width
      height: visible ? Style.space(300) : 0
      clip: true

      QQC.TextArea {
        id: magnusTextArea
        text: magnusPanel.controller.magnusPreview
          ? magnusPanel.controller.magnusPreview.content
          : ""
        readOnly: true
        selectByMouse: true
        wrapMode: TextEdit.NoWrap
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        color: Color.foreground
        selectionColor: Style.selectionFillFor(Color.foreground, Color.accent)
        selectedTextColor: Color.foreground
        leftPadding: Style.spacing.controlPaddingX
        rightPadding: Style.spacing.controlPaddingX
        topPadding: Style.spacing.inputPaddingY
        bottomPadding: Style.spacing.inputPaddingY
        background: BorderSurface {
          color: Style.normalFillFor(Color.foreground, Color.accent)
          borderSpec: Border.controlSpec(
            magnusTextArea.activeFocus ? "focus" : "normal",
            Color.foreground, Color.accent)
          radius: Style.cornerRadius
        }
        Keys.onEscapePressed: magnusPanel.controller.magnusBack()
      }
    }
  }

  Column {
    visible: magnusPanel.controller.magnusPreview === null &&
      !magnusPanel.controller.magnusBusy && magnusPanel.controller.magnusItems.length === 0
    width: parent.width
    topPadding: Style.spacing.xxxl
    bottomPadding: Style.spacing.huge
    spacing: Style.spacing.labelGap

    Text {
      width: parent.width
      text: "This folder is empty"
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.body
      font.weight: Font.DemiBold
      horizontalAlignment: Text.AlignHCenter
    }

    Text {
      width: parent.width
      text: "Choose Back to return to the previous folder."
      textFormat: Text.PlainText
      color: magnusPanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.WordWrap
    }
  }

  Repeater {
    id: magnusRepeater
    model: magnusPanel.controller.magnusPreview === null
      ? magnusPanel.controller.magnusItems
      : []

    delegate: Item {
      id: itemRow

      required property var modelData
      required property int index
      readonly property bool buildAvailable: itemRow.modelData.actions &&
        itemRow.modelData.actions.indexOf("build") >= 0
      readonly property bool rowSelected: itemRow.index === magnusPanel.controller.magnusCursor

      width: magnusPanel.width
      height: Style.space(54)
      clip: true

      RockArchSelectionChrome {
        anchors.fill: parent
        selected: itemRow.rowSelected
      }

      Column {
        anchors.left: parent.left
        anchors.right: itemRow.buildAvailable ? deployButton.left : parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Style.spacing.rowPaddingX
        anchors.rightMargin: Style.spacing.rowPaddingX
        spacing: Style.spacing.xxs

        Text {
          width: parent.width
          text: (itemRow.modelData.kind === "folder" ? "› " : "") +
            itemRow.modelData.title
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.weight: Font.DemiBold
          elide: Text.ElideRight
        }

        Text {
          width: parent.width
          text: itemRow.modelData.kind === "folder"
            ? (itemRow.buildAvailable
              ? "Mobile app · " + magnusPanel.controller.deploymentSummary(itemRow.modelData.title)
              : "Folder")
            : "File · Preview and download"
          textFormat: Text.PlainText
          color: magnusPanel.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }

      MouseArea {
        anchors.fill: parent
        anchors.rightMargin: itemRow.buildAvailable
          ? deployButton.width + Style.spacing.sm
          : 0
        cursorShape: Qt.PointingHandCursor
        onClicked: {
          magnusPanel.controller.selectMagnus(itemRow.index)
          magnusPanel.controller.activateMagnus(itemRow.index)
        }
      }

      Button {
        id: deployButton
        visible: itemRow.buildAvailable
        anchors.right: parent.right
        anchors.rightMargin: Style.spacing.sm
        anchors.verticalCenter: parent.verticalCenter
        text: "B · Deploy"
        tooltipText: "Deploy mobile app · B"
        fontSize: Style.font.caption
        bordered: itemRow.rowSelected
        focusable: false
        enabled: !magnusPanel.controller.magnusBusy &&
          !magnusPanel.controller.magnusActionBusy
        z: 2
        onClicked: {
          magnusPanel.controller.selectMagnus(itemRow.index)
          magnusPanel.controller.prepareMagnusBuild(
            itemRow.modelData.safeId, itemRow.modelData.title, false)
        }
      }
    }
  }
}
