import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: updateOnboarding

  required property var controller
  property alias primaryButton: enableUpdatesButton
  property alias secondaryButton: notNowButton
  readonly property color dim: Qt.darker(Color.foreground, 1.4)
  readonly property bool inputActive: enableUpdatesButton.activeFocus ||
    notNowButton.activeFocus

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.panelGap

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap

    Text {
      width: parent.width
      text: "Keep Rock Arch up to date?"
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.heading
      font.bold: true
      wrapMode: Text.WordWrap
    }

    Text {
      width: parent.width
      text: "Rock Arch can check daily and install validated updates automatically."
      textFormat: Text.PlainText
      color: updateOnboarding.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      wrapMode: Text.WordWrap
    }
  }

  Text {
    width: parent.width
    text: "You can change this later in Settings."
    textFormat: Text.PlainText
    color: updateOnboarding.dim
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }

  RowLayout {
    width: parent.width
    spacing: Style.spacing.sm

    Item { Layout.fillWidth: true }

    Button {
      id: notNowButton
      text: "Not now"
      focusable: true
      enabled: !updateOnboarding.controller.automaticUpdatesChoicePending
      KeyNavigation.tab: enableUpdatesButton
      KeyNavigation.backtab: enableUpdatesButton
      Keys.onEscapePressed: updateOnboarding.controller.completeAutomaticUpdatesOnboarding(false)
      onClicked: updateOnboarding.controller.completeAutomaticUpdatesOnboarding(false)
    }

    Button {
      id: enableUpdatesButton
      text: updateOnboarding.controller.automaticUpdatesChoicePending
        ? "Saving…"
        : "Enable automatic updates"
      bordered: true
      focusable: true
      enabled: !updateOnboarding.controller.automaticUpdatesChoicePending
      KeyNavigation.tab: notNowButton
      KeyNavigation.backtab: notNowButton
      Keys.onEscapePressed: updateOnboarding.controller.completeAutomaticUpdatesOnboarding(false)
      onClicked: updateOnboarding.controller.completeAutomaticUpdatesOnboarding(true)
    }
  }
}
