pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: knowledgePanel

  required property var controller
  property alias queryField: knowledgeField
  property alias resultRepeater: knowledgeResultRepeater
  property alias backButton: knowledgeBackButton
  property alias sourceButton: knowledgeSourceButton
  property alias linkRepeater: knowledgeLinkRepeater
  readonly property color dim: Qt.darker(Color.foreground, 1.4)

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.panelGap

  BorderSurface {
    width: parent.width
    implicitHeight: privacyText.implicitHeight + Style.spacing.lg * 2
    color: Style.normalFillFor(Color.accent, Color.accent)
    borderSpec: Border.controlSpec("normal", Color.accent, Color.accent)
    radius: Style.cornerRadius

    Text {
      id: privacyText
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      anchors.leftMargin: Style.spacing.rowPaddingX
      anchors.rightMargin: Style.spacing.rowPaddingX
      text: "Public search · Your query is sent to Rock Agent KB. Don't include names or private church data."
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }
  }

  TextField {
    id: knowledgeField
    visible: knowledgePanel.controller.knowledgeDetail === null
    width: parent.width
    text: knowledgePanel.controller.knowledgeQuery
    maximumLength: 120
    placeholderText: "Search public Rock knowledge…"
    selectByMouse: true
    inputMethodHints: Qt.ImhNoPredictiveText
    onTextEdited: {
      knowledgePanel.controller.knowledgeQuery = text
      knowledgePanel.controller.knowledgeCursor = -1
      knowledgePanel.controller.knowledgeResults = []
      knowledgePanel.controller.feedbackText = ""
      knowledgePanel.controller.scheduleKnowledgeSearch()
    }
    Keys.priority: Keys.BeforeItem
    Keys.onPressed: function(event) {
      if (event.key === Qt.Key_Escape) {
        knowledgePanel.controller.escapePanel()
        event.accepted = true
      } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
        knowledgePanel.controller.moveCursor(0, event.key === Qt.Key_Down ? 1 : -1)
        event.accepted = true
      } else if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
        var backwards = event.key === Qt.Key_Backtab || (event.modifiers & Qt.ShiftModifier)
        knowledgePanel.controller.moveTab(backwards ? -1 : 1)
        event.accepted = true
      } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
        knowledgePanel.controller.activateKnowledgeResult(0)
        event.accepted = true
      }
    }
  }

  Column {
    visible: knowledgePanel.controller.knowledgeDetail === null &&
      knowledgePanel.controller.knowledgeQuery.trim().length === 0
    width: parent.width
    spacing: Style.spacing.labelGap

    PanelSectionHeader { text: "SEARCH AREAS" }

    Text {
      width: parent.width
      text: "Use a prefix when you know where to look. A plain question searches everything."
      textFormat: Text.PlainText
      color: knowledgePanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      wrapMode: Text.WordWrap
    }

    Text {
      width: parent.width
      text: "mm:  Model Map        is:  issues        idea:  feature ideas\nlava:  Lava contexts    recipe:  recipes    guide:  concept guides"
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      lineHeight: 1.45
      wrapMode: Text.WordWrap
    }

    Text {
      width: parent.width
      text: "Examples:  mm: Group Member   ·   is: check-in labels   ·   lava: workflow"
      textFormat: Text.PlainText
      color: knowledgePanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }
  }

  Column {
    visible: knowledgePanel.controller.knowledgeDetail === null &&
      knowledgePanel.controller.knowledgeQuery.trim().length > 0
    width: parent.width
    spacing: Style.spacing.rowGap

    Repeater {
      id: knowledgeResultRepeater
      model: knowledgePanel.controller.knowledgeResults

      delegate: Item {
        id: resultRow

        required property var modelData
        required property int index
        readonly property bool rowSelected: resultRow.index === knowledgePanel.controller.knowledgeCursor ||
          (knowledgePanel.controller.knowledgeCursor < 0 && resultRow.index === 0 &&
            knowledgeField.activeFocus && knowledgePanel.controller.knowledgeResults.length > 0)

        width: knowledgePanel.width
        height: Style.space(54)
        clip: true

        RockLensSelectionChrome {
          anchors.fill: parent
          selected: resultRow.rowSelected
        }

        Column {
          anchors.left: parent.left
          anchors.right: readButton.visible ? readButton.left : parent.right
          anchors.verticalCenter: parent.verticalCenter
          anchors.leftMargin: Style.spacing.rowPaddingX
          anchors.rightMargin: Style.spacing.rowPaddingX
          spacing: Style.spacing.xxs

          Text {
            width: parent.width
            text: resultRow.modelData.title
            textFormat: Text.PlainText
            color: Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            font.weight: Font.DemiBold
            elide: Text.ElideRight
          }

          Text {
            width: parent.width
            text: resultRow.modelData.status + " · " + resultRow.modelData.subtitle
            textFormat: Text.PlainText
            color: knowledgePanel.dim
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        MouseArea {
          anchors.fill: parent
          anchors.rightMargin: readButton.visible ? readButton.width + Style.spacing.sm : 0
          cursorShape: Qt.PointingHandCursor
          onClicked: knowledgePanel.controller.selectKnowledgeResult(resultRow.index)
          onDoubleClicked: knowledgePanel.controller.activateKnowledgeResult(resultRow.index)
        }

        Button {
          id: readButton
          visible: resultRow.rowSelected
          anchors.right: parent.right
          anchors.rightMargin: Style.spacing.sm
          anchors.verticalCenter: parent.verticalCenter
          text: "Read"
          tooltipText: "Read in Rock Arch · Enter"
          fontSize: Style.font.caption
          bordered: true
          focusable: false
          z: 2
          onClicked: knowledgePanel.controller.activateKnowledgeResult(resultRow.index)
        }
      }
    }

    Column {
      visible: knowledgePanel.controller.knowledgeResults.length === 0 &&
        !knowledgePanel.controller.knowledgeSearchInFlight
      width: parent.width
      topPadding: Style.spacing.xxxl
      bottomPadding: Style.spacing.huge
      spacing: Style.spacing.labelGap

      Text {
        width: parent.width
        text: knowledgePanel.controller.knowledgeQueryWithoutScope().length < 2
          ? "Keep typing" : "No knowledge matches"
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        textFormat: Text.PlainText
      }

      Text {
        width: parent.width
        text: "Try different words, a more specific Rock question, or another search-area prefix."
        color: knowledgePanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
      }
    }
  }

  Column {
    visible: knowledgePanel.controller.knowledgeDetail !== null
    width: parent.width
    spacing: Style.spacing.panelGap

    RowLayout {
      width: parent.width
      spacing: Style.spacing.sm

      Button {
        id: knowledgeBackButton
        text: "Back"
        tooltipText: knowledgePanel.controller.knowledgeHistory.length
          ? "Back to the previous knowledge item · Esc"
          : "Back to Knowledge results · Esc"
        bordered: true
        focusable: true
        enabled: !knowledgePanel.controller.knowledgeBusy
        KeyNavigation.right: knowledgeSourceButton.visible
          ? knowledgeSourceButton : knowledgeBackButton
        Keys.onEscapePressed: knowledgePanel.controller.closeKnowledgeDetail()
        onActiveFocusChanged: knowledgePanel.controller.revealFocusedControl(knowledgeBackButton)
        onClicked: knowledgePanel.controller.closeKnowledgeDetail()
      }

      Item { Layout.fillWidth: true }

      Button {
        id: knowledgeSourceButton
        visible: knowledgePanel.controller.knowledgeDetail &&
          knowledgePanel.controller.knowledgeDetail.canOpenSource === true
        text: knowledgePanel.controller.knowledgeBusy ? "Opening…" : "Open source"
        tooltipText: "Open the cited public source"
        bordered: true
        focusable: true
        enabled: !knowledgePanel.controller.knowledgeBusy
        KeyNavigation.left: knowledgeBackButton
        Keys.onEscapePressed: knowledgePanel.controller.closeKnowledgeDetail()
        onActiveFocusChanged: knowledgePanel.controller.revealFocusedControl(knowledgeSourceButton)
        onClicked: knowledgePanel.controller.openKnowledgeSource()
      }
    }

    Column {
      width: parent.width
      spacing: Style.spacing.labelGap

      PanelSectionHeader {
        text: knowledgePanel.controller.knowledgeDetail
          ? String(knowledgePanel.controller.knowledgeDetail.kind || "KNOWLEDGE").toUpperCase()
          : "KNOWLEDGE"
      }

      Text {
        width: parent.width
        text: knowledgePanel.controller.knowledgeDetail
          ? knowledgePanel.controller.knowledgeDetail.title : ""
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.heading
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
      }

      Text {
        width: parent.width
        text: knowledgePanel.controller.knowledgeDetail
          ? knowledgePanel.controller.knowledgeDetail.trust + " · " +
            knowledgePanel.controller.knowledgeDetail.claimTier + " · " +
            knowledgePanel.controller.knowledgeDetail.version
          : ""
        textFormat: Text.PlainText
        color: knowledgePanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }
    }

    PanelSeparator {}

    Text {
      width: parent.width
      text: knowledgePanel.controller.knowledgeDetail
        ? knowledgePanel.controller.knowledgeDetail.body : ""
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      lineHeight: 1.25
      wrapMode: Text.WordWrap
    }

    Column {
      visible: knowledgePanel.controller.knowledgeDetail &&
        Array.isArray(knowledgePanel.controller.knowledgeDetail.links) &&
        knowledgePanel.controller.knowledgeDetail.links.length > 0
      width: parent.width
      spacing: Style.spacing.rowGap

      PanelSectionHeader { text: "RELATED" }

      Repeater {
        id: knowledgeLinkRepeater
        model: knowledgePanel.controller.knowledgeDetail &&
          Array.isArray(knowledgePanel.controller.knowledgeDetail.links)
          ? knowledgePanel.controller.knowledgeDetail.links : []

        delegate: Button {
          id: relatedButton

          required property var modelData
          required property int index

          width: knowledgePanel.width
          text: modelData.title + "  ·  " + modelData.kind
          tooltipText: modelData.subtitle + " · Enter"
          selected: index === knowledgePanel.controller.knowledgeLinkCursor
          bordered: false
          focusable: true
          horizontalPadding: Style.spacing.rowPaddingX
          verticalPadding: Style.spacing.sm
          onActiveFocusChanged: if (activeFocus) {
            knowledgePanel.controller.knowledgeLinkCursor = index
            knowledgePanel.controller.revealFocusedControl(relatedButton)
          }
          Keys.onEscapePressed: knowledgePanel.controller.closeKnowledgeDetail()
          onClicked: knowledgePanel.controller.activateKnowledgeLink(index)
        }
      }
    }

    Text {
      width: parent.width
      text: knowledgePanel.controller.knowledgeDetail
        ? knowledgePanel.controller.knowledgeDetail.attribution +
          (knowledgePanel.controller.knowledgeDetail.sourceHost
            ? " · " + knowledgePanel.controller.knowledgeDetail.sourceHost : "")
        : ""
      textFormat: Text.PlainText
      color: knowledgePanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }
  }
}
