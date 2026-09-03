pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: settingsPanel

  required property var controller
  property alias primaryButton: settingsAddProfileButton
  readonly property color dim: Qt.darker(Color.foreground, 1.4)
  readonly property bool inputActive: profileNameField.activeFocus ||
    domainField.activeFocus || usernameField.activeFocus || passwordField.activeFocus ||
    activeUsernameField.activeFocus || activePasswordField.activeFocus ||
    settingsPanel.controller.profileRenameInputActive

  function beginRenameProfile(profileId, name) {
    if (!profileId || controller.setupBusy) return
    controller.editingProfileId = profileId
    controller.editingProfileName = String(name || "")
    controller.pendingRemoveProfileId = ""
    controller.feedbackText = ""
  }

  function cancelRenameProfile() {
    controller.editingProfileId = ""
    controller.editingProfileName = ""
    controller.profileRenameInputActive = false
    controller.feedbackText = "Rename cancelled"
  }

  function saveProfileName(profileId) {
    var name = controller.editingProfileName.trim()
    if (!profileId || profileId !== controller.editingProfileId || !name ||
        controller.setupBusy) return
    controller.editingProfileId = ""
    controller.editingProfileName = ""
    controller.profileRenameInputActive = false
    controller.feedbackText = "Profile name updated"
    controller.request({op: "profile_rename", profileId: profileId, name: name})
  }

  function toggleMenuBarPreference() {
    controller.preferenceShowMenuBar = !controller.preferenceShowMenuBar
    controller.updatePreference("showMenuBar", controller.preferenceShowMenuBar)
  }

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.panelGap

  Column {
    width: parent.width
    spacing: Style.spacing.rowGap

    RowLayout {
      width: parent.width

      PanelSectionHeader {
        text: "ROCK PROFILES"
        Layout.fillWidth: true
      }

      Button {
        id: settingsAddProfileButton
        text: settingsPanel.controller.addProfileMode ? "Cancel" : "Add profile"
        bordered: settingsPanel.controller.addProfileMode
        focusable: true
        fontSize: Style.font.caption
        horizontalPadding: Style.spacing.lg
        verticalPadding: Style.spacing.xs
        enabled: !settingsPanel.controller.setupBusy
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(settingsAddProfileButton)
        onClicked: {
          settingsPanel.controller.addProfileMode = !settingsPanel.controller.addProfileMode
          settingsPanel.controller.setupUsername = ""
          settingsPanel.controller.setupPassword = ""
          settingsPanel.controller.feedbackText = ""
          if (settingsPanel.controller.addProfileMode)
            Qt.callLater(function() { profileNameField.forceActiveFocus(Qt.TabFocusReason) })
        }
      }
    }

    Text {
      width: parent.width
      text: "Each Rock site or account keeps its own login and Recent Links."
      textFormat: Text.PlainText
      color: settingsPanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      wrapMode: Text.WordWrap
    }

    Repeater {
      model: settingsPanel.controller.profiles

      delegate: CursorSurface {
        id: profileRow

        required property var modelData
        readonly property bool editing: settingsPanel.controller.editingProfileId ===
          profileRow.modelData.id

        width: settingsPanel.width
        implicitHeight: profileContent.implicitHeight + Style.spacing.rowPaddingX * 2
        current: profileRow.modelData.isActive
        bordered: true
        currentFill: Style.selectedFillFor(Color.foreground, Color.accent)

        ColumnLayout {
          id: profileContent
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          anchors.leftMargin: profileRow.borderLeft + Style.spacing.rowPaddingX
          anchors.rightMargin: profileRow.borderRight + Style.spacing.rowPaddingX
          spacing: Style.spacing.labelGap

          RowLayout {
            Layout.fillWidth: true
            spacing: Style.spacing.sm

            Column {
              Layout.fillWidth: true
              spacing: Style.spacing.xxs

              Text {
                width: parent.width
                text: profileRow.modelData.name
                textFormat: Text.PlainText
                color: Color.foreground
                font.family: Style.font.family
                font.pixelSize: Style.font.body
                font.weight: Font.DemiBold
                elide: Text.ElideRight
              }

              Text {
                width: parent.width
                text: String(profileRow.modelData.origin).replace("https://", "")
                textFormat: Text.PlainText
                color: settingsPanel.dim
                font.family: Style.font.family
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
            }

            Text {
              visible: profileRow.modelData.isActive
              text: "ACTIVE"
              textFormat: Text.PlainText
              color: Color.accent
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              font.bold: true
            }
          }

          Text {
            visible: profileRow.modelData.isActive
            Layout.fillWidth: true
            text: !settingsPanel.controller.rockConfigured
              ? "Login required"
              : settingsPanel.controller.magnusState === "available"
                ? "Connected · Magnus available"
                : settingsPanel.controller.magnusState === "unavailable"
                  ? "Connected · Search and Personal Links"
                  : settingsPanel.controller.magnusState === "error"
                    ? "Connected · Magnus check failed"
                    : "Connected · Checking Magnus…"
            textFormat: Text.PlainText
            color: settingsPanel.controller.rockConfigured ? Color.accent : Color.urgent
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }

          RowLayout {
            visible: !profileRow.editing
            Layout.fillWidth: true
            spacing: Style.spacing.xs

            Button {
              id: useProfileButton
              visible: !profileRow.modelData.isActive
              text: "Use"
              bordered: true
              focusable: true
              fontSize: Style.font.caption
              horizontalPadding: Style.spacing.md
              verticalPadding: Style.spacing.xs
              enabled: !settingsPanel.controller.setupBusy
              onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(useProfileButton)
              onClicked: settingsPanel.controller.switchProfile(profileRow.modelData.id)
            }

            Button {
              id: renameProfileButton
              text: "Rename"
              focusable: true
              fontSize: Style.font.caption
              horizontalPadding: Style.spacing.md
              verticalPadding: Style.spacing.xs
              enabled: !settingsPanel.controller.setupBusy
              onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(renameProfileButton)
              onClicked: {
                settingsPanel.beginRenameProfile(
                  profileRow.modelData.id, profileRow.modelData.name)
                Qt.callLater(function() {
                  profileRenameField.forceActiveFocus(Qt.TabFocusReason)
                })
              }
            }

            Button {
              id: changeLoginButton
              visible: profileRow.modelData.isActive &&
                settingsPanel.controller.rockConfigured
              text: settingsPanel.controller.editLoginMode ? "Cancel login" : "Login"
              tooltipText: "Change saved Rock login"
              focusable: true
              fontSize: Style.font.caption
              horizontalPadding: Style.spacing.md
              verticalPadding: Style.spacing.xs
              enabled: !settingsPanel.controller.setupBusy
              onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(changeLoginButton)
              onClicked: {
                settingsPanel.controller.editLoginMode = !settingsPanel.controller.editLoginMode
                settingsPanel.controller.setupUsername = ""
                settingsPanel.controller.setupPassword = ""
                if (settingsPanel.controller.editLoginMode)
                  Qt.callLater(function() {
                    activeUsernameField.forceActiveFocus(Qt.TabFocusReason)
                  })
              }
            }

            Button {
              id: testProfileButton
              visible: profileRow.modelData.isActive &&
                settingsPanel.controller.rockConfigured
              text: "Test"
              focusable: true
              fontSize: Style.font.caption
              horizontalPadding: Style.spacing.md
              verticalPadding: Style.spacing.xs
              enabled: !settingsPanel.controller.setupBusy
              onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(testProfileButton)
              onClicked: {
                settingsPanel.controller.beginSetup("Testing connection…")
                settingsPanel.controller.feedbackText = "Testing connection…"
                settingsPanel.controller.request({op: "profile_test"})
              }
            }

            Item { Layout.fillWidth: true }

            Button {
              id: signOutButton
              visible: profileRow.modelData.isActive &&
                settingsPanel.controller.rockConfigured
              text: settingsPanel.controller.pendingSignOut ? "Confirm sign out" : "Sign out"
              foreground: settingsPanel.controller.pendingSignOut ? Color.urgent : Color.foreground
              bordered: settingsPanel.controller.pendingSignOut
              focusable: true
              fontSize: Style.font.caption
              horizontalPadding: Style.spacing.md
              verticalPadding: Style.spacing.xs
              enabled: !settingsPanel.controller.setupBusy
              onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(signOutButton)
              onClicked: settingsPanel.controller.signOut()
            }

            Button {
              id: removeProfileButton
              text: settingsPanel.controller.pendingRemoveProfileId === profileRow.modelData.id
                ? "Confirm remove"
                : "Remove"
              foreground: settingsPanel.controller.pendingRemoveProfileId ===
                profileRow.modelData.id ? Color.urgent : settingsPanel.dim
              bordered: settingsPanel.controller.pendingRemoveProfileId ===
                profileRow.modelData.id
              focusable: true
              fontSize: Style.font.caption
              horizontalPadding: Style.spacing.md
              verticalPadding: Style.spacing.xs
              enabled: !settingsPanel.controller.setupBusy
              onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(removeProfileButton)
              onClicked: settingsPanel.controller.removeProfile(profileRow.modelData.id)
            }
          }

          RowLayout {
            visible: profileRow.editing
            Layout.fillWidth: true
            spacing: Style.spacing.sm

            TextField {
              id: profileRenameField
              Layout.fillWidth: true
              activeFocusOnTab: true
              maximumLength: 80
              placeholderText: "Profile name"
              text: profileRow.editing
                ? settingsPanel.controller.editingProfileName
                : ""
              selectByMouse: true
              onActiveFocusChanged: {
                settingsPanel.controller.profileRenameInputActive = activeFocus
                settingsPanel.controller.revealFocusedControl(profileRenameField)
              }
              onTextEdited: settingsPanel.controller.editingProfileName = text
              Keys.onReturnPressed: function(event) {
                event.accepted = true
                settingsPanel.saveProfileName(profileRow.modelData.id)
                Qt.callLater(function() {
                  renameProfileButton.forceActiveFocus(Qt.TabFocusReason)
                })
              }
              Keys.onEnterPressed: function(event) {
                event.accepted = true
                settingsPanel.saveProfileName(profileRow.modelData.id)
                Qt.callLater(function() {
                  renameProfileButton.forceActiveFocus(Qt.TabFocusReason)
                })
              }
              Keys.onEscapePressed: function(event) {
                event.accepted = true
                settingsPanel.cancelRenameProfile()
                Qt.callLater(function() {
                  renameProfileButton.forceActiveFocus(Qt.TabFocusReason)
                })
              }
            }

            Button {
              id: saveProfileNameButton
              text: "Save"
              bordered: true
              focusable: true
              fontSize: Style.font.caption
              horizontalPadding: Style.spacing.md
              enabled: settingsPanel.controller.editingProfileName.trim().length > 0 &&
                !settingsPanel.controller.setupBusy
              onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(saveProfileNameButton)
              onClicked: {
                settingsPanel.saveProfileName(profileRow.modelData.id)
                Qt.callLater(function() {
                  renameProfileButton.forceActiveFocus(Qt.TabFocusReason)
                })
              }
            }

            Button {
              id: cancelProfileRenameButton
              text: "Cancel"
              focusable: true
              fontSize: Style.font.caption
              horizontalPadding: Style.spacing.md
              enabled: !settingsPanel.controller.setupBusy
              onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(cancelProfileRenameButton)
              onClicked: {
                settingsPanel.cancelRenameProfile()
                Qt.callLater(function() {
                  renameProfileButton.forceActiveFocus(Qt.TabFocusReason)
                })
              }
            }
          }
        }
      }
    }

    BorderSurface {
      visible: settingsPanel.controller.addProfileMode
      width: parent.width
      implicitHeight: addProfileForm.implicitHeight + Style.spacing.rowPaddingX * 2
      color: Style.normalFillFor(Color.foreground, Color.accent)
      borderSpec: Border.controlSpec("normal", Color.foreground, Color.accent)
      radius: Style.cornerRadius

      Column {
        id: addProfileForm
        anchors.fill: parent
        anchors.margins: Style.spacing.rowPaddingX
        spacing: Style.spacing.rowGap

        Text {
          text: "Add a Rock profile"
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.weight: Font.DemiBold
        }

        TextField {
          id: profileNameField
          width: parent.width
          activeFocusOnTab: true
          maximumLength: 80
          placeholderText: "Profile name · Main Campus"
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
          placeholderText: "Rock domain · rock.example.org"
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
          password: true
          selectByMouse: true
          inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
          onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(passwordField)
          onTextChanged: settingsPanel.controller.setupPassword = text
          onAccepted: settingsPanel.controller.addProfile()
        }

        Button {
          id: addProfileButton
          anchors.right: parent.right
          text: settingsPanel.controller.setupBusy
            ? (settingsPanel.controller.setupSlow ? "Still signing in…" : "Signing in…")
            : "Add and connect"
          bordered: true
          focusable: true
          enabled: settingsPanel.controller.newProfileName.trim().length > 0 &&
            settingsPanel.controller.newProfileDomain.trim().length > 0 &&
            settingsPanel.controller.setupUsername.trim().length > 0 &&
            settingsPanel.controller.setupPassword.length > 0 &&
            !settingsPanel.controller.setupBusy
          onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(addProfileButton)
          onClicked: settingsPanel.controller.addProfile()
        }
      }
    }

    BorderSurface {
      visible: settingsPanel.controller.activeProfileId !== "" &&
        !settingsPanel.controller.addProfileMode &&
        (settingsPanel.controller.editLoginMode || !settingsPanel.controller.rockConfigured)
      width: parent.width
      implicitHeight: activeLoginForm.implicitHeight + Style.spacing.rowPaddingX * 2
      color: Style.normalFillFor(Color.foreground, Color.accent)
      borderSpec: Border.controlSpec("normal", Color.foreground, Color.accent)
      radius: Style.cornerRadius

      Column {
        id: activeLoginForm
        anchors.fill: parent
        anchors.margins: Style.spacing.rowPaddingX
        spacing: Style.spacing.rowGap

        Text {
          text: "Sign in to " + settingsPanel.controller.activeProfileName()
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.weight: Font.DemiBold
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
          password: true
          selectByMouse: true
          inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText
          onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(activePasswordField)
          onTextChanged: settingsPanel.controller.setupPassword = text
          onAccepted: settingsPanel.controller.saveRockCredentials()
        }

        Button {
          id: saveLoginButton
          anchors.right: parent.right
          text: settingsPanel.controller.setupBusy
            ? (settingsPanel.controller.setupSlow ? "Still signing in…" : "Signing in…")
            : "Save login"
          bordered: true
          focusable: true
          enabled: settingsPanel.controller.setupUsername.trim().length > 0 &&
            settingsPanel.controller.setupPassword.length > 0 &&
            !settingsPanel.controller.setupBusy
          onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(saveLoginButton)
          onClicked: settingsPanel.controller.saveRockCredentials()
        }
      }
    }
  }

  PanelSeparator {}

  Column {
    width: parent.width
    spacing: Style.spacing.rowGap

    PanelSectionHeader { text: "PREFERENCES" }

    Toggle {
      id: menuBarCheckBox
      width: parent.width
      label: "Show in the menu bar"
      description: "Super+R still opens Rock Arch when this is off."
      checked: settingsPanel.controller.preferenceShowMenuBar
      onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(menuBarCheckBox)
      onClicked: settingsPanel.toggleMenuBarPreference()
    }

    Toggle {
      id: personContextCheckBox
      width: parent.width
      label: "Show person context"
      description: "Include age, spouse, campus, and connection status when available."
      checked: settingsPanel.controller.preferencePersonContext
      onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(personContextCheckBox)
      onClicked: settingsPanel.controller.togglePersonContextPreference()
    }

    Toggle {
      id: recentLinksCheckBox
      width: parent.width
      label: "Remember Recent Links"
      description: "Keep up to 20 opened items on this computer."
      checked: settingsPanel.controller.preferenceRecentLinks
      onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(recentLinksCheckBox)
      onClicked: settingsPanel.controller.toggleRecentLinksPreference()
    }

    Toggle {
      id: closeAfterOpenCheckBox
      width: parent.width
      label: "Close after opening an item"
      description: "Return immediately to the Rock window."
      checked: settingsPanel.controller.preferenceCloseAfterOpen
      onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(closeAfterOpenCheckBox)
      onClicked: settingsPanel.controller.toggleCloseAfterOpenPreference()
    }
  }

  PanelSeparator {}

  Column {
    width: parent.width
    spacing: Style.spacing.rowGap

    PanelSectionHeader { text: "SEARCH CATEGORIES" }

    GridLayout {
      width: parent.width
      columns: 2
      columnSpacing: Style.spacing.rowGap
      rowSpacing: Style.spacing.sm

      Repeater {
        model: [
          {key: "People", label: "People"},
          {key: "Groups", label: "Groups"},
          {key: "Workflows", label: "Workflow Types"},
          {key: "Jobs", label: "Jobs"},
          {key: "Pages", label: "Pages"},
          {key: "Content Channel Items", label: "Content Items"}
        ]

        delegate: Button {
          id: categoryCheckBox

          required property var modelData

          Layout.fillWidth: true
          text: categoryCheckBox.modelData.label
          selected: settingsPanel.controller.categoryEnabled(categoryCheckBox.modelData.key)
          bordered: true
          leftAlign: true
          focusable: true
          fontSize: Style.font.bodySmall
          onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(categoryCheckBox)
          onClicked: settingsPanel.controller.toggleCategory(categoryCheckBox.modelData.key)
        }
      }
    }
  }

  PanelSeparator {}

  Column {
    width: parent.width
    spacing: Style.spacing.rowGap

    RowLayout {
      width: parent.width

      PanelSectionHeader {
        text: "UPDATES"
        Layout.fillWidth: true
      }

      Rectangle {
        Layout.preferredWidth: Style.spacing.lg
        Layout.preferredHeight: Style.spacing.lg
        radius: Style.cornerRadius > 0 ? width / 2 : 0
        color: settingsPanel.controller.updateAvailable ||
          settingsPanel.controller.updateState === "error"
          ? Color.urgent
          : Color.accent
      }
    }

    Text {
      width: parent.width
      text: "Version " + settingsPanel.controller.currentVersion + " · " +
        settingsPanel.controller.updateStatusText()
      textFormat: Text.PlainText
      color: settingsPanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      wrapMode: Text.WordWrap
    }

    RowLayout {
      width: parent.width
      spacing: Style.spacing.sm

      Button {
        id: checkUpdateButton
        text: settingsPanel.controller.updateState === "checking"
          ? "Checking…"
          : "Check now"
        bordered: true
        focusable: true
        enabled: settingsPanel.controller.updateManaged &&
          !settingsPanel.controller.updateBusy
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(checkUpdateButton)
        onClicked: settingsPanel.controller.checkForUpdates()
      }

      Button {
        id: installUpdateButton
        visible: settingsPanel.controller.updateAvailable ||
          settingsPanel.controller.updateState === "updating"
        text: settingsPanel.controller.updateState === "updating"
          ? "Updating…"
          : "Update now"
        bordered: true
        focusable: true
        enabled: settingsPanel.controller.updateAvailable &&
          !settingsPanel.controller.updateBusy
        onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(installUpdateButton)
        onClicked: settingsPanel.controller.startPluginUpdate()
      }

      Item { Layout.fillWidth: true }
    }

    Toggle {
      id: automaticUpdatesCheckBox
      width: parent.width
      label: "Install updates automatically"
      description: settingsPanel.controller.updateManaged
        ? "Check daily and install only after Omarchy validation."
        : "Available for Git-managed Omarchy installations."
      enabled: settingsPanel.controller.updateManaged &&
        settingsPanel.controller.updateState !== "updating"
      checked: settingsPanel.controller.preferenceAutomaticUpdates
      onActiveFocusChanged: settingsPanel.controller.revealFocusedControl(automaticUpdatesCheckBox)
      onClicked: settingsPanel.controller.toggleAutomaticUpdatesPreference()
    }

    Text {
      width: parent.width
      text: "Credentials stay in the desktop password manager."
      textFormat: Text.PlainText
      color: settingsPanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      horizontalAlignment: Text.AlignHCenter
    }
  }
}
