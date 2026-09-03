pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Commons

Column {
  id: settingsPanel
  required property var controller
  property alias primaryButton: settingsAddProfileButton
  readonly property bool inputActive: profileNameField.activeFocus ||
    domainField.activeFocus || usernameField.activeFocus || passwordField.activeFocus ||
    activeUsernameField.activeFocus || activePasswordField.activeFocus

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.md

  RowLayout {
    width: parent.width
    Text {
      text: "Rock profiles"
      color: Color.foreground
      font.pixelSize: Style.font.heading
      font.bold: true
    }
    Item { Layout.fillWidth: true }
    Button {
      id: settingsAddProfileButton
      text: settingsPanel.controller.addProfileMode ? "Cancel" : "Add profile"
      focusable: true
      enabled: !settingsPanel.controller.setupBusy
      onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(settingsAddProfileButton)
      onClicked: {
        settingsPanel.controller.addProfileMode = !settingsPanel.controller.addProfileMode
        settingsPanel.controller.setupUsername = ""
        settingsPanel.controller.setupPassword = ""
        settingsPanel.controller.feedbackText = ""
        if (settingsPanel.controller.addProfileMode)
          Qt.callLater(function() { profileNameField.forceActiveFocus() })
      }
    }
  }
  Text {
    width: parent.width
    text: "Each Rock site or account keeps its own login and Recent Links."
    color: Color.foreground
    opacity: 0.62
    wrapMode: Text.WordWrap
    textFormat: Text.PlainText
  }

  Repeater {
    model: settingsPanel.controller.profiles
    delegate: Rectangle {
      id: profileRow
      required property var modelData
      width: settingsPanel.width
      height: Style.space(profileRow.modelData.isActive ? 94 : 58)
      radius: 8
      color: profileRow.modelData.isActive ? Style.selectedFillFor(Color.foreground, Color.accent) : "transparent"
      border.width: 1
      border.color: profileRow.modelData.isActive ? Color.accent : Qt.rgba(1, 1, 1, 0.12)
      ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4
        RowLayout {
          Layout.fillWidth: true
          Column {
            Layout.fillWidth: true
            Text { width: parent.width; text: profileRow.modelData.name; color: Color.foreground; font.bold: true; textFormat: Text.PlainText; elide: Text.ElideRight }
            Text { width: parent.width; text: String(profileRow.modelData.origin).replace("https://", ""); color: Color.foreground; opacity: 0.58; textFormat: Text.PlainText; elide: Text.ElideRight }
          }
          Text {
            visible: profileRow.modelData.isActive
            text: "Active"
            color: Color.accent
            font.bold: true
            font.pixelSize: Style.font.bodySmall
          }
          Button {
            id: useProfileButton
            visible: !profileRow.modelData.isActive
            text: "Use"
            focusable: true
            enabled: !settingsPanel.controller.setupBusy
            onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(useProfileButton)
            onClicked: settingsPanel.controller.switchProfile(profileRow.modelData.id)
          }
          Button {
            id: removeProfileButton
            text: settingsPanel.controller.pendingRemoveProfileId === profileRow.modelData.id ? "Confirm remove" : "Remove"
            focusable: true
            enabled: !settingsPanel.controller.setupBusy
            onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(removeProfileButton)
            onClicked: settingsPanel.controller.removeProfile(profileRow.modelData.id)
          }
        }
        RowLayout {
          visible: profileRow.modelData.isActive
          Layout.fillWidth: true
          Layout.preferredHeight: visible ? Style.space(32) : 0
          spacing: Style.spacing.sm
          Rectangle {
            Layout.preferredWidth: 8
            Layout.preferredHeight: 8
            radius: 4
            color: settingsPanel.controller.rockConfigured ? "#86efac" : "#fbbf24"
          }
          Text {
            Layout.fillWidth: true
            text: !settingsPanel.controller.rockConfigured ? "Login required" :
              settingsPanel.controller.magnusState === "available" ? "Login saved · Magnus available" :
              settingsPanel.controller.magnusState === "unavailable" ? "Login saved · No Magnus access" :
              settingsPanel.controller.magnusState === "error" ? "Login saved · Magnus check failed" :
              "Login saved · Checking Magnus…"
            color: Color.foreground
            opacity: 0.72
            font.pixelSize: Style.font.bodySmall
            textFormat: Text.PlainText
            elide: Text.ElideRight
          }
          Button {
            id: changeLoginButton
            visible: settingsPanel.controller.rockConfigured
            text: settingsPanel.controller.editLoginMode ? "Cancel" : "Change login"
            focusable: true
            enabled: !settingsPanel.controller.setupBusy
            onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(changeLoginButton)
            onClicked: {
              settingsPanel.controller.editLoginMode = !settingsPanel.controller.editLoginMode
              settingsPanel.controller.setupUsername = ""
              settingsPanel.controller.setupPassword = ""
              if (settingsPanel.controller.editLoginMode)
                Qt.callLater(function() { activeUsernameField.forceActiveFocus() })
            }
          }
          Button {
            id: testProfileButton
            visible: settingsPanel.controller.rockConfigured
            text: "Test"
            focusable: true
            enabled: !settingsPanel.controller.setupBusy
            onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(testProfileButton)
            onClicked: {
              settingsPanel.controller.beginSetup("Testing connection…")
              settingsPanel.controller.feedbackText = "Testing connection…"
              settingsPanel.controller.request({op: "profile_test"})
            }
          }
          Button {
            id: signOutButton
            visible: settingsPanel.controller.rockConfigured
            text: settingsPanel.controller.pendingSignOut ? "Confirm sign out" : "Sign out"
            focusable: true
            enabled: !settingsPanel.controller.setupBusy
            onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(signOutButton)
            onClicked: settingsPanel.controller.signOut()
          }
        }
      }
    }
  }

  Rectangle {
    visible: settingsPanel.controller.addProfileMode
    width: parent.width
    height: visible ? addProfileForm.implicitHeight + 24 : 0
    radius: 8
    color: Style.selectedFillFor(Color.foreground, Color.accent)
    Column {
      id: addProfileForm
      anchors.fill: parent
      anchors.margins: 12
      spacing: Style.spacing.sm
      Text { text: "Add a Rock profile"; color: Color.foreground; font.bold: true }
      TextField {
        id: profileNameField
        width: parent.width
        activeFocusOnTab: true
        maximumLength: 80
        placeholderText: "Profile name (for example Main Campus)"
        text: settingsPanel.controller.newProfileName
        selectByMouse: true
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(profileNameField)
        onTextChanged: settingsPanel.controller.newProfileName = text
      }
      TextField {
        id: domainField
        width: parent.width
        activeFocusOnTab: true
        maximumLength: 250
        placeholderText: "Rock domain (for example rock.example.org)"
        text: settingsPanel.controller.newProfileDomain
        selectByMouse: true
        inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoPredictiveText
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(domainField)
        onTextChanged: settingsPanel.controller.newProfileDomain = text
      }
      TextField {
        id: usernameField
        width: parent.width
        activeFocusOnTab: true
        maximumLength: 200
        placeholderText: "Rock username"
        text: settingsPanel.controller.setupUsername
        selectByMouse: true
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(usernameField)
        onTextChanged: settingsPanel.controller.setupUsername = text
      }
      TextField {
        id: passwordField
        width: parent.width
        activeFocusOnTab: true
        placeholderText: "Rock password"
        text: settingsPanel.controller.setupPassword
        echoMode: TextInput.Password
        selectByMouse: true
        inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(passwordField)
        onTextChanged: settingsPanel.controller.setupPassword = text
        onAccepted: settingsPanel.controller.addProfile()
      }
      Button {
        id: addProfileButton
        text: settingsPanel.controller.setupBusy ? (settingsPanel.controller.setupSlow ? "Still signing in…" : "Signing in…") : "Add and connect"
        focusable: true
        enabled: settingsPanel.controller.newProfileDomain.trim().length > 0 && settingsPanel.controller.setupUsername.trim().length > 0 && settingsPanel.controller.setupPassword.length > 0 && !settingsPanel.controller.setupBusy
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(addProfileButton)
        onClicked: settingsPanel.controller.addProfile()
      }
    }
  }

  Rectangle {
    visible: settingsPanel.controller.activeProfileId !== "" && !settingsPanel.controller.addProfileMode && (settingsPanel.controller.editLoginMode || !settingsPanel.controller.rockConfigured)
    width: parent.width
    height: visible ? activeLoginForm.implicitHeight + 24 : 0
    radius: 8
    color: Style.selectedFillFor(Color.foreground, Color.accent)
    Column {
      id: activeLoginForm
      anchors.fill: parent
      anchors.margins: 12
      spacing: Style.spacing.sm
      Text {
        text: "Sign in to " + settingsPanel.controller.activeProfileName()
        color: Color.foreground
        font.bold: true
        textFormat: Text.PlainText
      }
      TextField {
        id: activeUsernameField
        width: parent.width
        activeFocusOnTab: true
        maximumLength: 200
        placeholderText: "Rock username"
        text: settingsPanel.controller.setupUsername
        selectByMouse: true
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(activeUsernameField)
        onTextChanged: settingsPanel.controller.setupUsername = text
      }
      TextField {
        id: activePasswordField
        width: parent.width
        activeFocusOnTab: true
        placeholderText: "Rock password"
        text: settingsPanel.controller.setupPassword
        echoMode: TextInput.Password
        selectByMouse: true
        inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(activePasswordField)
        onTextChanged: settingsPanel.controller.setupPassword = text
        onAccepted: settingsPanel.controller.saveRockCredentials()
      }
      Button {
        id: saveLoginButton
        text: settingsPanel.controller.setupBusy ? (settingsPanel.controller.setupSlow ? "Still signing in…" : "Signing in…") : "Save login"
        focusable: true
        enabled: settingsPanel.controller.setupUsername.trim().length > 0 && settingsPanel.controller.setupPassword.length > 0 && !settingsPanel.controller.setupBusy
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(saveLoginButton)
        onClicked: settingsPanel.controller.saveRockCredentials()
      }
    }
  }

  Rectangle { width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.12) }
  Text { text: "Search and behavior"; color: Color.foreground; font.pixelSize: Style.font.heading; font.bold: true }
  CheckBox {
    id: personContextCheckBox
    text: "Person context · age, spouse, campus, and status"
    activeFocusOnTab: true
    checked: settingsPanel.controller.preferencePersonContext
    onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(personContextCheckBox)
    Keys.onReturnPressed: settingsPanel.controller.togglePersonContextPreference()
    Keys.onEnterPressed: settingsPanel.controller.togglePersonContextPreference()
    onClicked: {
      settingsPanel.controller.preferencePersonContext = checked
      settingsPanel.controller.updatePreference("showPersonContext", checked)
    }
  }
  CheckBox {
    id: recentLinksCheckBox
    text: "Remember Recent Links"
    activeFocusOnTab: true
    checked: settingsPanel.controller.preferenceRecentLinks
    onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(recentLinksCheckBox)
    Keys.onReturnPressed: settingsPanel.controller.toggleRecentLinksPreference()
    Keys.onEnterPressed: settingsPanel.controller.toggleRecentLinksPreference()
    onClicked: {
      settingsPanel.controller.preferenceRecentLinks = checked
      settingsPanel.controller.updatePreference("recentLinks", checked)
      if (!checked) settingsPanel.controller.quickReturns = []
      else settingsPanel.controller.refreshQuickReturns()
    }
  }
  CheckBox {
    id: closeAfterOpenCheckBox
    text: "Close Rock Lens after opening an item"
    activeFocusOnTab: true
    checked: settingsPanel.controller.preferenceCloseAfterOpen
    onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(closeAfterOpenCheckBox)
    Keys.onReturnPressed: settingsPanel.controller.toggleCloseAfterOpenPreference()
    Keys.onEnterPressed: settingsPanel.controller.toggleCloseAfterOpenPreference()
    onClicked: {
      settingsPanel.controller.preferenceCloseAfterOpen = checked
      settingsPanel.controller.updatePreference("closeAfterOpen", checked)
    }
  }
  Text { text: "Search categories"; color: Color.foreground; font.bold: true }
  Flow {
    width: parent.width
    spacing: Style.spacing.sm
    Repeater {
      model: [
        {key: "People", label: "People"},
        {key: "Groups", label: "Groups"},
        {key: "Workflows", label: "Workflow Types"},
        {key: "Jobs", label: "Jobs"},
        {key: "Pages", label: "Pages"},
        {key: "Content Channel Items", label: "Content Items"}
      ]
      delegate: CheckBox {
        id: categoryCheckBox
        required property var modelData
        text: modelData.label
        activeFocusOnTab: true
        checked: settingsPanel.controller.categoryEnabled(modelData.key)
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(categoryCheckBox)
        Keys.onReturnPressed: settingsPanel.controller.toggleCategory(modelData.key)
        Keys.onEnterPressed: settingsPanel.controller.toggleCategory(modelData.key)
        onClicked: settingsPanel.controller.toggleCategory(modelData.key)
      }
    }
  }
  Text {
    width: parent.width
    text: "Rock Lens 0.14.0 · Credentials stay in your desktop password manager"
    color: Color.foreground
    opacity: 0.48
    font.pixelSize: Style.font.bodySmall
    textFormat: Text.PlainText
  }
}
