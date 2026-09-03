import QtQuick
import QtQuick.Controls
import qs.Commons

Column {
  id: loginPanel
  required property var controller
  property alias domainField: onboardingDomainField
  readonly property bool inputActive: onboardingDomainField.activeFocus ||
    onboardingUsernameField.activeFocus || onboardingPasswordField.activeFocus

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.sm

  Text {
    text: "Connect to Rock"
    color: Color.foreground
    font.pixelSize: Style.font.heading
    font.bold: true
  }
  TextField {
    id: onboardingDomainField
    width: parent.width
    enabled: !loginPanel.controller.setupBusy
    maximumLength: 250
    placeholderText: "Rock domain (rock.example.org)"
    text: loginPanel.controller.newProfileDomain
    selectByMouse: true
    inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoPredictiveText
    KeyNavigation.tab: onboardingUsernameField
    KeyNavigation.backtab: onboardingConnectButton
    onTextChanged: loginPanel.controller.newProfileDomain = text
    onAccepted: onboardingUsernameField.forceActiveFocus(Qt.TabFocusReason)
  }
  TextField {
    id: onboardingUsernameField
    width: parent.width
    enabled: !loginPanel.controller.setupBusy
    maximumLength: 200
    placeholderText: "Rock username"
    text: loginPanel.controller.setupUsername
    selectByMouse: true
    KeyNavigation.tab: onboardingPasswordField
    KeyNavigation.backtab: onboardingDomainField
    onTextChanged: loginPanel.controller.setupUsername = text
    onAccepted: onboardingPasswordField.forceActiveFocus(Qt.TabFocusReason)
  }
  TextField {
    id: onboardingPasswordField
    width: parent.width
    enabled: !loginPanel.controller.setupBusy
    placeholderText: "Rock password"
    text: loginPanel.controller.setupPassword
    echoMode: TextInput.Password
    selectByMouse: true
    inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
    KeyNavigation.tab: onboardingConnectButton
    KeyNavigation.backtab: onboardingUsernameField
    onTextChanged: loginPanel.controller.setupPassword = text
    onAccepted: loginPanel.controller.completeOnboarding()
  }
  Button {
    id: onboardingConnectButton
    text: loginPanel.controller.setupBusy ? (loginPanel.controller.setupSlow ? "Still connecting…" : "Connecting…") : "Connect"
    activeFocusOnTab: true
    enabled: loginPanel.controller.newProfileDomain.trim().length > 0 &&
      loginPanel.controller.setupUsername.trim().length > 0 &&
      loginPanel.controller.setupPassword.length > 0 && !loginPanel.controller.setupBusy
    KeyNavigation.tab: onboardingDomainField
    KeyNavigation.backtab: onboardingPasswordField
    onClicked: loginPanel.controller.completeOnboarding()
  }
}
