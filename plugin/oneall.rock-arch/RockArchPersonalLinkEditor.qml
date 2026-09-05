pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: editor
  required property var controller
  required property var model
  property alias nameField: nameField
  readonly property bool inputActive: nameField.activeFocus || urlField.activeFocus || sectionField.popupOpen
  height: visible ? implicitHeight : 0
  spacing: Style.spacing.panelGap

  RowLayout {
    width: parent.width
    PanelSectionHeader { text: "ADD PERSONAL LINK"; Layout.fillWidth: true }
    Button {
      text: "Cancel"
      focusable: true
      enabled: !editor.model.saving
      onClicked: editor.model.cancel()
    }
  }
  Text {
    width: parent.width
    text: "Save to your Rock account · " + editor.controller.activeProfileName()
    textFormat: Text.PlainText
    color: Qt.darker(Color.foreground, 1.4)
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }
  Column {
    width: parent.width
    spacing: Style.spacing.labelGap
    Text {
      text: "Name"; textFormat: Text.PlainText
      color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.body
    }
    TextField {
      id: nameField
      width: parent.width
      text: editor.model.name
      maximumLength: 100
      enabled: !editor.model.busy
      Accessible.name: "Link name"
      onTextEdited: editor.model.name = text
      onAccepted: urlField.forceActiveFocus(Qt.TabFocusReason)
      onActiveFocusChanged: if (activeFocus) editor.controller.revealFocusedControl(nameField)
    }
  }
  Column {
    width: parent.width
    spacing: Style.spacing.labelGap
    Text {
      text: "Rock URL"; textFormat: Text.PlainText
      color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.body
    }
    TextField {
      id: urlField
      width: parent.width
      text: editor.model.url
      placeholderText: "/page/42"
      maximumLength: 2048
      enabled: !editor.model.busy
      Accessible.name: "Rock URL"
      onTextEdited: editor.model.url = text
      onActiveFocusChanged: if (activeFocus) editor.controller.revealFocusedControl(urlField)
    }
  }
  Dropdown {
    id: sectionField
    width: parent.width
    label: "Personal section"
    value: editor.model.sectionId
    options: editor.model.sections.map(function(item) { return {value: item.safeId, label: item.name} })
    enabled: !editor.model.busy && editor.model.sections.length > 0
    onChanged: function(value) { editor.model.sectionId = value }
  }
  Text {
    width: parent.width
    visible: editor.model.notice !== "" || editor.model.busy
    text: editor.model.busy ? (editor.model.saving ? "Saving to Rock…" : "Loading your personal sections…") : editor.model.notice
    textFormat: Text.PlainText
    color: Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.bodySmall
    wrapMode: Text.WordWrap
  }
  RowLayout {
    width: parent.width
    Item { Layout.fillWidth: true }
    Button {
      text: "Reload"
      visible: !editor.model.busy && editor.model.draftId === ""
      focusable: true
      onClicked: editor.model.reload()
    }
    Button {
      text: editor.model.saving ? "Saving…" : "Save link"
      tooltipText: "Save to Personal Links · Ctrl+S"
      focusable: true
      bordered: true
      enabled: editor.model.canSave
      onClicked: editor.model.save()
    }
  }
}
