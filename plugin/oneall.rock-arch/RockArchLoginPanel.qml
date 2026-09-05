import QtQuick
import qs.Commons
import qs.Ui

Column {
  id: loginPanel

  required property var controller
  property alias profileNameField: onboardingProfileNameField
  property alias domainField: onboardingDomainField
  readonly property color dim: Qt.darker(Color.foreground, 1.4)
  readonly property bool inputActive: onboardingProfileNameField.activeFocus ||
    onboardingDomainField.activeFocus || onboardingUsernameField.activeFocus ||
    onboardingPasswordField.activeFocus

  function domainKey(value) {
    return String(value || "").trim().toLowerCase()
      .replace(/^https:\/\//, "").replace(/\/+$/, "")
  }

  function completeOnboarding() {
    var name = controller.newProfileName.trim()
    var domain = controller.newProfileDomain.trim()
    var username = controller.setupUsername.trim()
    if (!name || !domain || !username || !controller.setupPassword || controller.setupBusy) return
    controller.beginSetup("Connecting to Rock…")
    controller.onboardingInProgress = true
    var password = controller.setupPassword
    var operation = controller.activeProfileId &&
      domainKey(domain) !== domainKey(controller.instanceDomain) ?
      "profile_add" : "rock_configure"
    controller.pendingSuccessText = "Rock Arch is ready"
    controller.request({op: operation, name: name, domain: domain, username: username, password: password})
    controller.setupPassword = ""
  }

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.panelGap

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap

    Text {
      width: parent.width
      text: "Connect to Rock"
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.heading
      font.bold: true
    }

    Text {
      width: parent.width
      text: "Sign in with the same account used on the Rock website."
      textFormat: Text.PlainText
      color: loginPanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      wrapMode: Text.WordWrap
    }
  }

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap

    PanelSectionHeader { text: "PROFILE NAME" }
    TextField {
      id: onboardingProfileNameField
      width: parent.width
      enabled: !loginPanel.controller.setupBusy
      activeFocusOnTab: true
      maximumLength: 80
      placeholderText: "Rock Solid Church Production"
      text: loginPanel.controller.newProfileName
      selectByMouse: true
      KeyNavigation.tab: onboardingDomainField
      KeyNavigation.backtab: onboardingConnectButton
      onTextChanged: loginPanel.controller.newProfileName = text
      onAccepted: onboardingDomainField.forceActiveFocus(Qt.TabFocusReason)
    }
  }

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap

    PanelSectionHeader { text: "ROCK DOMAIN" }
    TextField {
      id: onboardingDomainField
      width: parent.width
      enabled: !loginPanel.controller.setupBusy
      activeFocusOnTab: true
      maximumLength: 250
      placeholderText: "rock.example.org"
      text: loginPanel.controller.newProfileDomain
      selectByMouse: true
      inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoPredictiveText
      KeyNavigation.tab: onboardingUsernameField
      KeyNavigation.backtab: onboardingProfileNameField
      onTextChanged: loginPanel.controller.newProfileDomain = text
      onAccepted: onboardingUsernameField.forceActiveFocus(Qt.TabFocusReason)
    }
  }

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap

    PanelSectionHeader { text: "USERNAME" }
    TextField {
      id: onboardingUsernameField
      width: parent.width
      enabled: !loginPanel.controller.setupBusy
      activeFocusOnTab: true
      maximumLength: 200
      placeholderText: "Rock username"
      text: loginPanel.controller.setupUsername
      selectByMouse: true
      KeyNavigation.tab: onboardingPasswordField
      KeyNavigation.backtab: onboardingDomainField
      onTextChanged: loginPanel.controller.setupUsername = text
      onAccepted: onboardingPasswordField.forceActiveFocus(Qt.TabFocusReason)
    }
  }

  Column {
    width: parent.width
    spacing: Style.spacing.labelGap

    PanelSectionHeader { text: "PASSWORD" }
    TextField {
      id: onboardingPasswordField
      width: parent.width
      enabled: !loginPanel.controller.setupBusy
      activeFocusOnTab: true
      placeholderText: "Rock password"
      text: loginPanel.controller.setupPassword
      password: true
      selectByMouse: true
      inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
      KeyNavigation.tab: onboardingConnectButton
      KeyNavigation.backtab: onboardingUsernameField
      onTextChanged: loginPanel.controller.setupPassword = text
      onAccepted: loginPanel.completeOnboarding()
    }
  }

  Button {
    id: onboardingConnectButton
    anchors.right: parent.right
    text: loginPanel.controller.setupBusy
      ? (loginPanel.controller.setupSlow ? "Still connecting…" : "Connecting…")
      : "Connect"
    focusable: true
    bordered: true
    enabled: loginPanel.controller.newProfileDomain.trim().length > 0 &&
      loginPanel.controller.newProfileName.trim().length > 0 &&
      loginPanel.controller.setupUsername.trim().length > 0 &&
      loginPanel.controller.setupPassword.length > 0 && !loginPanel.controller.setupBusy
    KeyNavigation.tab: onboardingProfileNameField
    KeyNavigation.backtab: onboardingPasswordField
    onClicked: loginPanel.completeOnboarding()
  }
}
