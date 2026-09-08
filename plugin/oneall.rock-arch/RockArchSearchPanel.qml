pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: searchPanel

  readonly property Item listFocus: controller.showRecentLinks ? recentListFocus : resultListFocus
  required property var controller
  required property var searchField
  property alias resultRepeater: resultRepeater
  property alias quickReturnRepeater: quickReturnRepeater
  property alias clearCancelButton: cancelClearButton
  property alias clearButton: clearRecentButton
  property alias buildConfirmButton: recentBuildConfirmButton
  property alias jobSurface: jobPanel
  property alias buildCancelButton: recentBuildCancelButton
  property alias buildControls: buildRecentConfirm
  property alias clearControls: clearControls
  property alias jobCancelButton: jobPanel.cancelButton
  readonly property color dim: Qt.darker(Color.foreground, 1.4)

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.rowGap

  RockArchListFocus {
    id: resultListFocus
    controller: searchPanel.controller
    visible: !searchPanel.controller.showRecentLinks && searchPanel.controller.activeSearchCount > 0 && !searchPanel.controller.job.editing && !searchPanel.controller.pendingClearRecent && searchPanel.controller.pendingMagnusBuildId === ""
    Accessible.name: "Search results"
  }

  RockArchJobPanel {
    id: jobPanel
    model: searchPanel.controller.job
    visible: model.editing
    width: searchPanel.width
    height: visible ? implicitHeight : 0
  }

  Column {
    visible: !searchPanel.controller.showRecentLinks && !searchPanel.controller.job.editing
    width: searchPanel.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.rowGap

    Repeater {
      id: resultRepeater
      model: searchPanel.controller.results

      delegate: Item {
        id: resultRow

        required property var modelData
        required property int index
        readonly property bool rowSelected: resultRow.index === searchPanel.controller.resultCursor ||
          (searchPanel.controller.resultCursor < 0 && resultRow.index === 0 &&
            searchPanel.searchField.activeFocus && searchPanel.controller.resultsAreCurrent &&
            searchPanel.controller.results.length > 0)

        width: searchPanel.width
        height: Style.space(54)
        clip: true
        opacity: searchPanel.controller.resultsAreCurrent ? 1 : 0.45

        RockArchSelectionChrome {
          keyboardFocused: searchPanel.listFocus.activeFocus
          anchors.fill: parent
          selected: resultRow.rowSelected
        }

        Column {
          anchors.left: parent.left
          anchors.right: runButton.visible ? runButton.left : (bookmarkButton.visible ? bookmarkButton.left : (openButton.visible ? openButton.left : parent.right))
          anchors.verticalCenter: parent.verticalCenter
          anchors.leftMargin: Style.spacing.rowPaddingX
          anchors.rightMargin: Style.spacing.rowPaddingX
          spacing: Style.spacing.xxs

          Text {
            width: parent.width
            text: resultRow.modelData.title
            textFormat: Text.PlainText
            color: Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            font.weight: Font.DemiBold
            elide: Text.ElideRight
          }

          Text {
            width: parent.width
            text: searchPanel.controller.displayCategory(resultRow.modelData.category) +
              " · " + resultRow.modelData.subtitle + " · " + resultRow.modelData.status
            textFormat: Text.PlainText
            color: searchPanel.dim
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        MouseArea {
          anchors.fill: parent
          anchors.rightMargin: openButton.visible ? openButton.width + Style.spacing.sm : 0
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            searchPanel.controller.selectResult(resultRow.index)
            if (resultRow.modelData.category === "People")
              searchPanel.controller.request({op: "person_quick_look", safeId: resultRow.modelData.safeId})
          }
          onDoubleClicked: {
            searchPanel.controller.resultCursor = resultRow.index
            searchPanel.controller.activateResult(resultRow.index)
          }
        }

        Button {
          id: runButton
          visible: bookmarkButton.visible && resultRow.modelData.category === "Jobs" && searchPanel.controller.job.available
          anchors.right: bookmarkButton.left
          anchors.rightMargin: Style.spacing.xs
          anchors.verticalCenter: parent.verticalCenter
          text: "Run"
          tooltipText: "Run now · R"
          fontSize: Style.font.caption
          focusable: true
          z: 2
          onClicked: searchPanel.controller.beginJob(resultRow.index)
        }

        Button {
          id: bookmarkButton
          visible: openButton.visible && searchPanel.controller.resultsAreCurrent
          anchors.right: openButton.left
          anchors.rightMargin: Style.spacing.xs
          anchors.verticalCenter: parent.verticalCenter
          iconText: "\uf097" // Nerd Font: bookmark outline
          iconSize: Style.font.body
          Accessible.role: Accessible.Button
          Accessible.name: "Add bookmark"
          Accessible.description: "Add to Personal Links · Ctrl+B"
          Accessible.onPressAction: clicked()
          tooltipText: "Add to Personal Links · Ctrl+B"
          fontSize: Style.font.caption
          focusable: true
          z: 2
          onClicked: searchPanel.controller.beginPersonalLink(resultRow.modelData.safeId)
        }

        Button {
          id: openButton
          visible: resultRow.modelData.canOpen === true &&
            searchPanel.controller.contextName === "PROD" && resultRow.rowSelected
          anchors.right: parent.right
          anchors.rightMargin: Style.spacing.sm
          anchors.verticalCenter: parent.verticalCenter
          text: "Open"
          tooltipText: "Open in Rock · Enter"
          fontSize: Style.font.caption
          bordered: true
          focusable: true
          z: 2
          onClicked: {
            searchPanel.controller.resultCursor = resultRow.index
            searchPanel.controller.activateResult(resultRow.index)
          }
        }
      }
    }

    Column {
      visible: searchPanel.controller.results.length === 0
      width: parent.width
      topPadding: Style.spacing.xxxl
      bottomPadding: Style.spacing.huge
      spacing: Style.spacing.labelGap

      Text {
        width: parent.width
        text: searchPanel.controller.contextName === "PROD" && !searchPanel.controller.rockConfigured
          ? "Rock login required"
          : "No matching results"
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
      }

      Text {
        width: parent.width
        text: searchPanel.controller.contextName === "PROD" && !searchPanel.controller.rockConfigured
          ? "Open Settings to sign in."
          : "Try a name, ID, GUID, or category prefix."
        textFormat: Text.PlainText
        color: searchPanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
      }
    }

    BorderSurface {
      visible: searchPanel.controller.quickLook !== null
      width: parent.width
      implicitHeight: quickLookContent.implicitHeight + Style.spacing.rowPaddingX * 2
      color: Style.normalFillFor(Color.foreground, Color.accent)
      borderSpec: Border.controlSpec("normal", Color.foreground, Color.accent)
      radius: Style.cornerRadius

      Column {
        id: quickLookContent
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Style.spacing.rowPaddingX
        anchors.rightMargin: Style.spacing.rowPaddingX
        spacing: Style.spacing.xxs

        Text {
          width: parent.width
          text: searchPanel.controller.quickLook ? searchPanel.controller.quickLook.displayName : ""
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.weight: Font.DemiBold
          elide: Text.ElideRight
        }

        Text {
          width: parent.width
          text: searchPanel.controller.quickLook ? searchPanel.controller.quickLook.subtitle : ""
          textFormat: Text.PlainText
          color: searchPanel.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }

        Text {
          visible: text !== ""
          width: parent.width
          text: searchPanel.controller.quickLook ? searchPanel.controller.quickLook.campus : ""
          textFormat: Text.PlainText
          color: searchPanel.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }
    }
  }

  Column {
    visible: searchPanel.controller.showRecentLinks && !searchPanel.controller.job.editing
    width: searchPanel.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.rowGap

    RowLayout {
      width: parent.width

      id: clearControls
      PanelSectionHeader {
        text: "RECENT LINKS"
        Layout.fillWidth: true
      }

      Button {
        id: cancelClearButton
        visible: searchPanel.controller.pendingClearRecent
        text: "Cancel"
        focusable: true
        KeyNavigation.right: clearRecentButton
        onClicked: {
          searchPanel.controller.pendingClearRecent = false
          searchPanel.controller.focusList()
        }
      }

      Button {
        id: clearRecentButton
        visible: searchPanel.controller.contextName === "PROD"
        text: searchPanel.controller.pendingClearRecent ? "Confirm clear" : "Clear"
        tooltipText: "Clear Recent Links · X"
        foreground: searchPanel.controller.pendingClearRecent ? Color.urgent : Color.foreground
        bordered: searchPanel.controller.pendingClearRecent
        focusable: true
        KeyNavigation.left: cancelClearButton.visible ? cancelClearButton : null
        fontSize: Style.font.caption
        horizontalPadding: Style.spacing.lg
        verticalPadding: Style.spacing.xs
        enabled: searchPanel.controller.quickReturns.length > 0 && !searchPanel.controller.setupBusy
        onActiveFocusChanged: searchPanel.controller.revealFocusedControl(clearRecentButton)
        onClicked: searchPanel.controller.clearRecentLinks()
      }
    }

    Column {
      visible: searchPanel.controller.quickReturns.length === 0
      width: parent.width
      topPadding: Style.spacing.xxxl
      bottomPadding: Style.spacing.huge
      spacing: Style.spacing.labelGap

      Text {
        width: parent.width
        text: searchPanel.controller.contextName === "PROD"
          ? "No recent links yet"
          : "Recent Links are hidden in preview mode"
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
      }

      Text {
        width: parent.width
        text: searchPanel.controller.contextName === "PROD"
          ? "Search Rock and open an item to add it here."
          : "Start typing to search preview data."
        textFormat: Text.PlainText
        color: searchPanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
      }
    }

    BorderSurface {
      visible: searchPanel.controller.pendingMagnusBuildId !== "" &&
        searchPanel.controller.pendingMagnusBuildRecent
      width: parent.width
      implicitHeight: buildRecentConfirm.implicitHeight + Style.spacing.rowPaddingX * 2
      color: Style.normalFillFor(Color.urgent, Color.urgent)
      borderSpec: Border.controlSpec("normal", Color.urgent, Color.urgent)
      radius: Style.cornerRadius

      ColumnLayout {
        id: buildRecentConfirm
        anchors.fill: parent
        anchors.margins: Style.spacing.rowPaddingX
        spacing: Style.spacing.labelGap

        Text {
          Layout.fillWidth: true
          text: "Deploy " + searchPanel.controller.pendingMagnusBuildTitle + " again?"
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.weight: Font.DemiBold
          wrapMode: Text.WordWrap
        }

        Text {
          Layout.fillWidth: true
          text: searchPanel.controller.contextName === "DEV"
            ? "Preview the confirmation flow without starting a build."
            : "This starts a production mobile-app build."
          textFormat: Text.PlainText
          color: searchPanel.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        RowLayout {
          Item { Layout.fillWidth: true }

          Button {
            id: recentBuildCancelButton
            text: "Cancel"
            focusable: true
            enabled: !searchPanel.controller.magnusActionBusy
            KeyNavigation.right: recentBuildConfirmButton
            KeyNavigation.tab: recentBuildConfirmButton
            KeyNavigation.backtab: recentBuildConfirmButton
            Keys.onEscapePressed: searchPanel.controller.cancelMagnusBuild()
            onClicked: searchPanel.controller.cancelMagnusBuild()
          }

          Button {
            id: recentBuildConfirmButton
            text: searchPanel.controller.magnusActionBusy ? "Deploying…" : "Deploy again"
            foreground: Color.urgent
            bordered: true
            focusable: true
            enabled: !searchPanel.controller.magnusActionBusy
            KeyNavigation.left: recentBuildCancelButton
            KeyNavigation.tab: recentBuildCancelButton
            KeyNavigation.backtab: recentBuildCancelButton
            Keys.onEscapePressed: searchPanel.controller.cancelMagnusBuild()
            onClicked: searchPanel.controller.confirmMagnusBuild()
          }
        }
      }
    }

    RockArchListFocus {
      id: recentListFocus
      controller: searchPanel.controller
      visible: searchPanel.controller.quickReturns.length > 0 && !searchPanel.controller.pendingClearRecent && searchPanel.controller.pendingMagnusBuildId === ""
      Accessible.name: "Recent links"
    }

    Repeater {
      id: quickReturnRepeater
      model: searchPanel.controller.quickReturns

      delegate: Item {
        id: recentRow

        enabled: !searchPanel.controller.pendingClearRecent && searchPanel.controller.pendingMagnusBuildId === ""

        required property var modelData
        required property int index
        readonly property bool rowSelected: recentRow.index === searchPanel.controller.recentCursor ||
          (searchPanel.controller.recentCursor < 0 && recentRow.index === 0 &&
            searchPanel.searchField.activeFocus && searchPanel.controller.quickReturns.length > 0)

        width: searchPanel.width
        height: Style.space(54)
        clip: true

        RockArchSelectionChrome {
          keyboardFocused: searchPanel.listFocus.activeFocus
          anchors.fill: parent
          selected: recentRow.rowSelected
        }

        Column {
          anchors.left: parent.left
          anchors.right: recentActions.visible ? recentActions.left : parent.right
          anchors.verticalCenter: parent.verticalCenter
          anchors.leftMargin: Style.spacing.rowPaddingX
          anchors.rightMargin: Style.spacing.rowPaddingX
          spacing: Style.spacing.xxs

          Text {
            width: parent.width
            text: recentRow.modelData.title
            textFormat: Text.PlainText
            color: Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            font.weight: Font.DemiBold
            elide: Text.ElideRight
          }

          Text {
            width: parent.width
            text: recentRow.modelData.kind === "Magnus Build"
              ? "Last started " + searchPanel.controller.relativeTime(recentRow.modelData.lastUsedAt) +
                " · Enter to deploy again"
              : recentRow.modelData.kind
            textFormat: Text.PlainText
            color: searchPanel.dim
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        MouseArea {
          anchors.fill: parent
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            searchPanel.controller.selectRecent(recentRow.index)
          }
          onDoubleClicked: {
            searchPanel.controller.selectRecent(recentRow.index)
            searchPanel.controller.activateRecent(recentRow.index)
          }
        }

        Row {
          id: recentActions
          visible: recentRow.rowSelected && searchPanel.controller.contextName === "PROD"
          anchors.right: parent.right
          anchors.rightMargin: Style.spacing.sm
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.spacing.xs
          z: 2

          Button {
            visible: recentRow.modelData.kind === "Scheduled Job" && searchPanel.controller.job.available
            text: "Run"
            tooltipText: "Run now · R"
            fontSize: Style.font.caption
            focusable: true
            onClicked: {
              searchPanel.controller.selectRecent(recentRow.index)
              searchPanel.controller.beginJob(recentRow.index)
            }
          }
          Button {
            visible: recentRow.modelData.kind !== "Magnus Build"
            iconText: "\uf097"
            iconSize: Style.font.body
            Accessible.role: Accessible.Button
            Accessible.name: "Add bookmark"
            Accessible.description: "Add to Personal Links · Ctrl+B"
            Accessible.onPressAction: clicked()
            tooltipText: "Add to Personal Links · Ctrl+B"
            fontSize: Style.font.caption
            focusable: true
            onClicked: searchPanel.controller.beginPersonalLink(recentRow.modelData.safeId)
          }
          Button {
            text: recentRow.modelData.kind === "Magnus Build" ? "Deploy" : "Open"
            tooltipText: recentRow.modelData.kind === "Magnus Build" ? "Review deployment · Enter" : "Open in Rock · Enter"
            fontSize: Style.font.caption
            bordered: true
            focusable: true
            onClicked: {
              searchPanel.controller.recentCursor = recentRow.index
              searchPanel.controller.activateRecent(recentRow.index)
            }
          }
        }
      }
    }
  }
}
