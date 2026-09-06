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
  property alias cancelButton: cancelButton
  readonly property string deleteLabel: model.kind === "delete-section" ? (model.linkCount > 0 ? "Delete section and links" : "Delete section") : "Delete link"
  readonly property bool inputActive: nameField.activeFocus || urlField.activeFocus || sectionField.popupOpen
  height: visible ? implicitHeight : 0
  spacing: Style.spacing.panelGap

  RowLayout {
    width: parent.width
    PanelSectionHeader { text: editor.model.deleting ? (editor.model.kind === "delete-section" ? "DELETE SECTION" : "DELETE PERSONAL LINK") : editor.model.kind === "section" ? "ADD PERSONAL SECTION" : "ADD PERSONAL LINK"; Layout.fillWidth: true }
    Button {
      id: cancelButton
      text: "Cancel"
      focusable: true
      enabled: !editor.model.saving
      onClicked: editor.model.cancel()
    }
  }
  Text {
    width: parent.width
    text: editor.model.deleting ? editor.controller.activeProfileName() : (editor.model.kind === "section" ? "Private section in " : "Save to your Rock account · ") + editor.controller.activeProfileName()
    textFormat: Text.PlainText
    color: Qt.darker(Color.foreground, 1.4)
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }
  Text {
    visible: editor.model.deleting && editor.model.name !== ""
    width: parent.width
    text: editor.model.kind === "delete-section"
      ? "Delete “" + editor.model.name + "” and all links inside it?\nCurrently contains " + editor.model.linkCount + (editor.model.linkCount === 1 ? " link." : " links.") + "\nThis permanently deletes the section and its contents from your Rock account."
      : "Delete “" + editor.model.name + "”?\nSection: " + editor.model.sectionName + "\nThis removes the bookmark from your Rock account."
    textFormat: Text.PlainText
    color: Color.foreground
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    wrapMode: Text.WordWrap
  }
  Text {
    visible: editor.model.deleting && editor.model.url !== ""
    width: parent.width
    text: editor.model.url
    textFormat: Text.PlainText
    color: Qt.darker(Color.foreground, 1.4)
    font.family: Style.font.family
    font.pixelSize: Style.font.caption
    wrapMode: Text.WrapAnywhere
    maximumLineCount: 3
    elide: Text.ElideMiddle
  }
  Column {
    visible: !editor.model.deleting
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
      Accessible.name: editor.model.kind === "section" ? "Section name" : "Link name"
      onTextEdited: editor.model.name = text
      onAccepted: { if (editor.model.kind === "section") editor.model.save(); else urlField.forceActiveFocus(Qt.TabFocusReason) }
      onActiveFocusChanged: if (activeFocus) editor.controller.revealFocusedControl(nameField)
    }
  }
  Column {
    visible: editor.model.kind === "link"
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
    visible: editor.model.kind === "link"
    label: "Personal section"
    value: editor.model.sectionId
    options: editor.model.sections.map(function(item) { return {value: item.safeId, label: item.name} })
    enabled: !editor.model.busy && editor.model.sections.length > 0
    onChanged: function(value) { editor.model.sectionId = value }
  }
  Text {
    width: parent.width
    visible: editor.model.notice !== "" || editor.model.busy
    text: editor.model.busy ? (editor.model.saving ? (editor.model.deleting ? "Deleting from Rock…" : "Saving to Rock…") : editor.model.deleting ? "Checking this item…" : "Loading your personal sections…") : editor.model.notice
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
      text: editor.model.saving ? (editor.model.deleting ? "Deleting…" : "Saving…") : editor.model.deleting ? editor.deleteLabel : editor.model.kind === "section" ? "Create section" : "Save link"
      tooltipText: editor.model.deleting ? editor.deleteLabel : editor.model.kind === "section" ? "Create section · Ctrl+S" : "Save to Personal Links · Ctrl+S"
      focusable: true
      bordered: true
      enabled: editor.model.canSave
      onClicked: editor.model.save()
    }
  }
}
