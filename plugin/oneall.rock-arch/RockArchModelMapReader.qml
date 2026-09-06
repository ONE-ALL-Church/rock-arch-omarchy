pragma ComponentBehavior: Bound

import QtQuick
import qs.Commons
import qs.Ui

Column {
  id: reader
  required property var controller
  property alias filterField: filterField
  readonly property color dim: Qt.darker(Color.foreground, 1.4)
  spacing: Style.spacing.panelGap

  RockArchModelMapView {
    id: modelView
    detail: reader.controller.knowledgeDetail
  }

  Shortcut {
    sequence: "Ctrl+F"
    enabled: reader.visible && reader.controller.opened
    onActivated: {
      filterField.forceActiveFocus(Qt.ShortcutFocusReason)
      filterField.selectAll()
      reader.controller.revealFocusedControl(filterField)
    }
  }

  TextField {
    id: filterField
    width: parent.width
    maximumLength: 120
    placeholderText: "Filter properties and methods…"
    text: modelView.filter
    selectByMouse: true
    onTextEdited: modelView.filter = text
    onActiveFocusChanged: reader.controller.revealFocusedControl(filterField)
    Keys.onEscapePressed: {
      if (modelView.filter) modelView.filter = ""
      else reader.controller.closeKnowledgeDetail()
    }
  }

  Repeater {
    model: modelView.sections
    delegate: Column {
      id: section
      required property var modelData
      readonly property bool expanded: modelView.isExpanded(modelData.key)
      width: reader.width
      spacing: Style.spacing.rowGap

      Button {
        id: sectionButton
        width: parent.width
        leftAlign: true
        text: (section.expanded ? "▾ " : "▸ ") + section.modelData.title + " · " +
          (modelView.filtering ? section.modelData.rows.length + " / " : "") + section.modelData.total
        tooltipText: modelView.filtering ? "Clear the filter to collapse sections" : "Expand or collapse · Enter"
        fontSize: Style.font.bodySmall
        bordered: false
        focusable: true
        onActiveFocusChanged: reader.controller.revealFocusedControl(sectionButton)
        onClicked: modelView.setExpanded(section.modelData.key, !section.expanded)
        Keys.onLeftPressed: modelView.setExpanded(section.modelData.key, false)
        Keys.onRightPressed: modelView.setExpanded(section.modelData.key, true)
        Keys.onEscapePressed: reader.controller.closeKnowledgeDetail()
      }

      Column {
        visible: section.expanded
        width: parent.width
        spacing: Style.spacing.panelGap
        leftPadding: Style.spacing.rowPaddingX
        rightPadding: Style.spacing.rowPaddingX

        Text {
          visible: text.length > 0
          width: parent.width - parent.leftPadding - parent.rightPadding
          text: section.modelData.notice
          textFormat: Text.PlainText
          color: reader.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          wrapMode: Text.Wrap
        }

        Text {
          visible: modelView.filtering && section.modelData.rows.length === 0
          text: "No matching " + section.modelData.title.toLowerCase()
          textFormat: Text.PlainText
          color: reader.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.bodySmall
        }

        Repeater {
          model: section.expanded ? section.modelData.rows : []
          delegate: Column {
            required property var modelData
            width: reader.width - Style.spacing.rowPaddingX * 2
            spacing: Style.spacing.labelGap

            Text {
              width: parent.width
              text: parent.modelData.title
              textFormat: Text.PlainText
              color: Color.foreground
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              font.weight: Font.DemiBold
              wrapMode: Text.Wrap
            }
            Text {
              visible: text.length > 0
              width: parent.width
              text: parent.modelData.subtitle
              textFormat: Text.PlainText
              color: reader.dim
              font.family: Style.font.family
              font.pixelSize: Style.font.caption
              wrapMode: Text.Wrap
            }
            Text {
              visible: text.length > 0
              width: parent.width
              text: parent.modelData.body || "No description in this source snapshot."
              textFormat: Text.PlainText
              color: Color.foreground
              font.family: Style.font.family
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.Wrap
              lineHeight: 1.25
            }
            PanelSeparator {}
          }
        }
      }
    }
  }
}
