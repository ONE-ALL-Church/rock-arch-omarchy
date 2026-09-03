pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons

Column {
  id: searchPanel
  required property var controller
  required property var searchField
  property alias resultRepeater: resultRepeater
  property alias quickReturnRepeater: quickReturnRepeater
  property alias clearButton: clearRecentButton
  property alias buildConfirmButton: recentBuildConfirmButton

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.sm

  Column {
    visible: !searchPanel.controller.showRecentLinks
    width: searchPanel.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.sm

    Repeater {
      id: resultRepeater
      model: searchPanel.controller.results
      delegate: Rectangle {
        id: resultRow
        required property var modelData
        required property int index
        readonly property bool rowSelected: resultRow.index === searchPanel.controller.resultCursor ||
          (searchPanel.controller.resultCursor < 0 && resultRow.index === 0 && searchPanel.searchField.activeFocus && searchPanel.controller.results.length > 0)
        width: searchPanel.width
        height: Style.space(52)
        radius: 7
        color: "transparent"
        clip: true
        RockLensSelectionChrome { anchors.fill: parent; selected: parent.rowSelected }
        Column {
          anchors.left: parent.left
          anchors.right: openButton.visible ? openButton.left : parent.right
          anchors.verticalCenter: parent.verticalCenter
          anchors.leftMargin: 16
          anchors.rightMargin: 10
          Text { width: parent.width; text: resultRow.modelData.title; color: Color.foreground; font.bold: true; textFormat: Text.PlainText; elide: Text.ElideRight }
          Text { width: parent.width; text: searchPanel.controller.displayCategory(resultRow.modelData.category) + " · " + resultRow.modelData.subtitle + " · " + resultRow.modelData.status; color: Color.foreground; opacity: 0.65; textFormat: Text.PlainText; elide: Text.ElideRight }
        }
        MouseArea {
          anchors.fill: parent
          onClicked: {
            searchPanel.controller.selectResult(resultRow.index)
            if (resultRow.modelData.category === "People")
              searchPanel.controller.request({op: "person_quick_look", safeId: resultRow.modelData.safeId})
          }
        }
        Rectangle {
          id: openButton
          visible: resultRow.modelData.canOpen === true && searchPanel.controller.contextName === "PROD" && resultRow.index === searchPanel.controller.resultCursor
          width: visible ? Style.space(54) : 0
          height: Style.space(32)
          anchors.right: parent.right
          anchors.rightMargin: 7
          anchors.verticalCenter: parent.verticalCenter
          radius: 6
          color: "#14532d"
          z: 2
          Text { anchors.centerIn: parent; text: "Open"; color: "white"; font.bold: true }
          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: {
              searchPanel.controller.resultCursor = resultRow.index
              searchPanel.controller.request({op: "open_navigation", safeId: resultRow.modelData.safeId})
            }
          }
        }
      }
    }

    Text {
      visible: searchPanel.controller.results.length === 0
      width: searchPanel.width
      text: searchPanel.controller.contextName === "PROD" && !searchPanel.controller.rockConfigured ? "Live results stay empty until a Rock login is saved." : "No matching results."
      color: Color.foreground
      opacity: 0.6
      wrapMode: Text.WordWrap
    }

    Rectangle {
      visible: searchPanel.controller.quickLook !== null
      width: searchPanel.width
      height: visible ? Style.space(100) : 0
      radius: 9
      color: Style.selectedFillFor(Color.foreground, Color.accent)
      Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 4
        Text { text: searchPanel.controller.quickLook ? searchPanel.controller.quickLook.displayName : ""; color: Color.foreground; font.pixelSize: Style.font.heading; font.bold: true; textFormat: Text.PlainText }
        Text { text: searchPanel.controller.quickLook ? searchPanel.controller.quickLook.subtitle : ""; color: Color.foreground; textFormat: Text.PlainText }
        Text { text: searchPanel.controller.quickLook ? searchPanel.controller.quickLook.campus : ""; color: Color.foreground; opacity: 0.65; textFormat: Text.PlainText }
      }
    }
  }

  Column {
    visible: searchPanel.controller.showRecentLinks
    width: searchPanel.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.sm

    RowLayout {
      width: parent.width
      Text {
        text: "Recent Links"
        color: Color.foreground
        font.pixelSize: Style.font.heading
        font.bold: true
      }
      Item { Layout.fillWidth: true }
      Button {
        id: clearRecentButton
        Layout.preferredHeight: Style.space(30)
        visible: searchPanel.controller.contextName === "PROD"
        text: searchPanel.controller.pendingClearRecent ? "Confirm clear" : "X · Clear"
        focusable: enabled
        enabled: searchPanel.controller.quickReturns.length > 0 && !searchPanel.controller.setupBusy
        background: searchPanel.controller.pendingClearRecent ? "#7f1d1d" : Style.selectedFillFor(Color.foreground, Color.accent)
        KeyNavigation.tab: clearRecentButton
        KeyNavigation.backtab: clearRecentButton
        onActiveFocusChanged: searchPanel.controller.revealFocusedControl(clearRecentButton)
        onClicked: searchPanel.controller.clearRecentLinks()
      }
    }
    Text {
      visible: searchPanel.controller.quickReturns.length === 0
      width: searchPanel.width
      text: searchPanel.controller.contextName === "PROD" ?
        "Items opened from Rock Arch will appear here (up to 20)." :
        "Recent Links are available in PROD. Start typing to search preview data."
      color: Color.foreground
      opacity: 0.6
      wrapMode: Text.WordWrap
    }
    Rectangle {
      visible: searchPanel.controller.pendingMagnusBuildId !== "" && searchPanel.controller.pendingMagnusBuildRecent
      width: searchPanel.width
      height: visible ? buildRecentConfirm.implicitHeight + 24 : 0
      radius: 9
      color: Qt.rgba(0.45, 0.2, 0.05, 0.35)
      border.width: 1
      border.color: "#f59e0b"
      ColumnLayout {
        id: buildRecentConfirm
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8
        Text { Layout.fillWidth: true; text: "Deploy " + searchPanel.controller.pendingMagnusBuildTitle + " again?"; color: Color.foreground; font.bold: true; wrapMode: Text.WordWrap; textFormat: Text.PlainText }
        Text { Layout.fillWidth: true; text: "Press Enter to start the production build, or Esc to cancel. You can deploy it again later from Recent Links."; color: Color.foreground; opacity: 0.68; wrapMode: Text.WordWrap; textFormat: Text.PlainText }
        RowLayout {
          Button {
            id: recentBuildCancelButton
            text: "Cancel"
            activeFocusOnTab: true
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
            activeFocusOnTab: true
            enabled: !searchPanel.controller.magnusActionBusy
            KeyNavigation.left: recentBuildCancelButton
            KeyNavigation.tab: recentBuildCancelButton
            KeyNavigation.backtab: recentBuildCancelButton
            Keys.onEscapePressed: searchPanel.controller.cancelMagnusBuild()
            onClicked: searchPanel.controller.confirmMagnusBuild()
          }
          Item { Layout.fillWidth: true }
        }
      }
    }
    Repeater {
      id: quickReturnRepeater
      model: searchPanel.controller.quickReturns
      delegate: Rectangle {
        id: recentRow
        required property var modelData
        required property int index
        readonly property bool rowSelected: recentRow.index === searchPanel.controller.recentCursor ||
          (searchPanel.controller.recentCursor < 0 && recentRow.index === 0 && searchPanel.searchField.activeFocus && searchPanel.controller.quickReturns.length > 0)
        width: searchPanel.width
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
          Text { width: parent.width; text: recentRow.modelData.title; color: Color.foreground; font.bold: true; textFormat: Text.PlainText; elide: Text.ElideRight }
          Text {
            width: parent.width
            text: recentRow.modelData.kind === "Magnus Build" ?
              "Last deployed " + searchPanel.controller.relativeTime(recentRow.modelData.lastUsedAt) + " · Enter to deploy again" :
              recentRow.modelData.kind
            color: Color.foreground
            opacity: 0.65
            textFormat: Text.PlainText
            elide: Text.ElideRight
          }
        }
        MouseArea {
          anchors.fill: parent
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            searchPanel.controller.selectRecent(recentRow.index)
            searchPanel.controller.activateRecent(recentRow.index)
          }
        }
      }
    }
  }
}
