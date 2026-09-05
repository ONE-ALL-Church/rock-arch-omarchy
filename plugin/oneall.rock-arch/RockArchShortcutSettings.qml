pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: shortcutSettings
  required property var controller
  readonly property var model: controller.shortcut
  readonly property bool inputActive: visible && (shortcutField.activeFocus || model.editing || model.removing)
  readonly property var primaryButton: actionButton.visible ? actionButton : nextControl
  property var previousControl: null
  property var nextControl: null
  readonly property var lastButton: cancelButton.visible ? cancelButton : removeButton.visible
    ? removeButton : chooseButton.visible ? chooseButton : actionButton.visible ? actionButton : previousControl
  spacing: Style.spacing.rowGap
  onVisibleChanged: if (visible) model.refresh(true)
  Component.onCompleted: if (visible) model.refresh(true)
  Keys.onEscapePressed: function(event) {
    if (model.editing || model.removing) {
      model.cancel()
      actionButton.forceActiveFocus(Qt.TabFocusReason)
    } else event.accepted = false
  }

  PanelSectionHeader { text: "KEYBOARD SHORTCUT" }
  Text {
    width: parent.width
    text: shortcutSettings.model.busy ? "Checking shortcut…" : shortcutSettings.model.message()
    textFormat: Text.PlainText
    color: Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
    wrapMode: Text.WordWrap
  }
  TextField {
    id: shortcutField
    visible: shortcutSettings.model.editing
    width: parent.width
    text: shortcutSettings.model.draft
    placeholderText: "Super + Shift + R"
    maximumLength: 80
    enabled: !shortcutSettings.model.busy
    Accessible.name: "Shortcut, for example Super plus Shift plus R"
    onTextEdited: shortcutSettings.model.draft = shortcutField.text
    onAccepted: shortcutSettings.model.check()
    Keys.onEscapePressed: { shortcutSettings.model.cancel(); actionButton.forceActiveFocus(Qt.TabFocusReason) }
    KeyNavigation.tab: actionButton
    KeyNavigation.backtab: cancelButton
    onActiveFocusChanged: shortcutSettings.controller.revealFocusedControl(shortcutField)
  }
  RowLayout {
    visible: shortcutSettings.model.editing || shortcutSettings.model.removing ||
      !shortcutSettings.model.configured || shortcutSettings.model.canManage
    width: parent.width
    spacing: Style.spacing.sm
    Button {
      id: actionButton
      text: shortcutSettings.model.removing ? "Remove and show icon"
        : shortcutSettings.model.editing ? (shortcutSettings.model.canSave ? "Save shortcut" : "Check shortcut")
        : shortcutSettings.model.canManage ? "Change"
        : shortcutSettings.model.canSave ? "Add " + shortcutSettings.model.label(shortcutSettings.model.snapshot.combo)
        : "Check again"
      focusable: true
      bordered: true
      enabled: !shortcutSettings.model.busy
      fontSize: Style.font.bodySmall
      KeyNavigation.tab: chooseButton.visible ? chooseButton : removeButton.visible ? removeButton
        : cancelButton.visible ? cancelButton : shortcutSettings.nextControl
      KeyNavigation.backtab: shortcutField.visible ? shortcutField : shortcutSettings.previousControl
      onActiveFocusChanged: shortcutSettings.controller.revealFocusedControl(actionButton)
      onClicked: {
        var model = shortcutSettings.model
        if (model.removing) model.remove()
        else if (model.editing) { if (model.canSave) model.install(); else model.check() }
        else if (model.canManage) {
          model.choose()
          Qt.callLater(function() { shortcutField.forceActiveFocus(Qt.TabFocusReason); shortcutField.selectAll() })
        }
        else if (model.canSave) model.install()
        else model.refresh()
      }
    }
    Button {
      id: chooseButton
      visible: !shortcutSettings.model.editing && !shortcutSettings.model.removing &&
        shortcutSettings.model.snapshot.editable === true && !shortcutSettings.model.snapshot.currentCombo
      text: "Choose another"
      focusable: true
      enabled: !shortcutSettings.model.busy
      fontSize: Style.font.bodySmall
      KeyNavigation.tab: removeButton.visible ? removeButton : shortcutSettings.nextControl
      KeyNavigation.backtab: actionButton
      onActiveFocusChanged: shortcutSettings.controller.revealFocusedControl(chooseButton)
      onClicked: { shortcutSettings.model.choose(); Qt.callLater(function() { shortcutField.forceActiveFocus(Qt.TabFocusReason); shortcutField.selectAll() }) }
    }
    Button {
      id: removeButton
      visible: !shortcutSettings.model.editing && !shortcutSettings.model.removing &&
        shortcutSettings.model.snapshot.managed === true && shortcutSettings.model.snapshot.editable === true
      text: "Remove"
      focusable: true
      enabled: !shortcutSettings.model.busy
      fontSize: Style.font.bodySmall
      KeyNavigation.tab: shortcutSettings.nextControl
      KeyNavigation.backtab: actionButton
      onActiveFocusChanged: shortcutSettings.controller.revealFocusedControl(removeButton)
      onClicked: {
        shortcutSettings.model.removing = true
        shortcutSettings.model.notice = "Remove the Rock Arch shortcut? The menu-bar icon will be shown."
        actionButton.forceActiveFocus(Qt.TabFocusReason)
      }
    }
    Button {
      id: cancelButton
      visible: shortcutSettings.model.editing || shortcutSettings.model.removing
      text: "Cancel"
      focusable: true
      enabled: !shortcutSettings.model.busy
      fontSize: Style.font.bodySmall
      KeyNavigation.tab: shortcutSettings.nextControl || shortcutField
      KeyNavigation.backtab: actionButton
      onActiveFocusChanged: shortcutSettings.controller.revealFocusedControl(cancelButton)
      onClicked: { shortcutSettings.model.cancel(); actionButton.forceActiveFocus(Qt.TabFocusReason) }
    }
    Item { Layout.fillWidth: true }
  }
}
