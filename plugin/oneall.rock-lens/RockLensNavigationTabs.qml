pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons

RowLayout {
  id: navigation
  required property var controller

  spacing: Style.spacing.sm

  Text {
    text: "Rock Lens"
    color: Color.foreground
    font.pixelSize: Style.font.title
    font.bold: true
  }
  Rectangle {
    visible: navigation.controller.developerMode
    Layout.preferredWidth: contextLabel.implicitWidth + 16
    Layout.preferredHeight: contextLabel.implicitHeight + 8
    radius: 6
    color: navigation.controller.contextName === "PROD" ? "#7f1d1d" : "#14532d"
    Text {
      id: contextLabel
      anchors.centerIn: parent
      text: navigation.controller.contextName
      color: "white"
      font.bold: true
    }
    MouseArea {
      anchors.fill: parent
      enabled: navigation.controller.developerMode
      cursorShape: Qt.PointingHandCursor
      onClicked: navigation.controller.switchContext()
    }
  }
  Item { Layout.fillWidth: true }
  Repeater {
    model: navigation.controller.onboardingRequired ? [] :
      (navigation.controller.showMagnus ? ["search", "personal", "magnus"] : ["search", "personal"])
    delegate: Rectangle {
      id: tab
      required property var modelData
      Layout.preferredWidth: tabText.implicitWidth + 20
      Layout.preferredHeight: Style.space(32)
      radius: 7
      color: navigation.controller.viewMode === tab.modelData ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
      Text {
        id: tabText
        anchors.centerIn: parent
        text: tab.modelData === "search" ? "Search" : (tab.modelData === "personal" ? "Personal Links" : "Magnus")
        color: Color.foreground
        font.bold: navigation.controller.viewMode === tab.modelData
      }
      MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: {
          if (tab.modelData === "search") navigation.controller.focusSearch()
          else if (tab.modelData === "personal") navigation.controller.selectPersonalLink(0)
          else navigation.controller.openMagnus()
        }
      }
    }
  }
  Rectangle {
    visible: !navigation.controller.onboardingRequired
    Layout.preferredWidth: settingsLabel.implicitWidth + 20
    Layout.preferredHeight: Style.space(32)
    radius: 7
    color: navigation.controller.viewMode === "settings" ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
    Text {
      id: settingsLabel
      anchors.centerIn: parent
      text: "Settings"
      color: Color.foreground
      font.bold: navigation.controller.viewMode === "settings"
    }
    MouseArea {
      anchors.fill: parent
      cursorShape: Qt.PointingHandCursor
      onClicked: navigation.controller.openSettings(false)
    }
  }
}
