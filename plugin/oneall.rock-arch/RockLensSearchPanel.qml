pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

Column {
  id: searchPanel

  required property var controller
  required property var searchField
  property alias resultRepeater: resultRepeater
  property alias quickReturnRepeater: quickReturnRepeater
  property alias clearButton: clearRecentButton
  property alias buildConfirmButton: recentBuildConfirmButton
  property alias knowledgeBackButton: knowledgeBackButton
  property alias knowledgeSourceButton: knowledgeSourceButton
  readonly property color dim: Qt.darker(Color.foreground, 1.4)

  height: visible ? implicitHeight : 0
  spacing: Style.spacing.rowGap

  function closeKnowledgeDetail() {
    var selected = searchPanel.controller.resultCursor
    searchPanel.controller.knowledgeDetail = null
    searchPanel.controller.knowledgeBusy = false
    searchPanel.controller.feedbackText = ""
    if (selected >= 0)
      Qt.callLater(function() { searchPanel.controller.selectResult(selected) })
    else
      searchPanel.controller.focusSearch()
  }

  function openKnowledgeSource() {
    var detail = searchPanel.controller.knowledgeDetail
    if (!detail || detail.canOpenSource !== true || searchPanel.controller.knowledgeBusy)
      return
    searchPanel.controller.knowledgeBusy = true
    searchPanel.controller.feedbackText = "Opening source…"
    searchPanel.controller.request({op: "knowledge_open_source", safeId: detail.safeId})
  }

  Column {
    visible: !searchPanel.controller.showRecentLinks &&
      searchPanel.controller.knowledgeDetail === null
    width: searchPanel.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.rowGap

    BorderSurface {
      visible: searchPanel.controller.knowledgeScope
      width: parent.width
      implicitHeight: knowledgePrivacyText.implicitHeight + Style.spacing.lg * 2
      color: Style.normalFillFor(Color.accent, Color.accent)
      borderSpec: Border.controlSpec("normal", Color.accent, Color.accent)
      radius: Style.cornerRadius

      Text {
        id: knowledgePrivacyText
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

    Repeater {
      id: resultRepeater
      model: searchPanel.controller.results

      delegate: Item {
        id: resultRow

        required property var modelData
        required property int index
        readonly property bool rowSelected: resultRow.index === searchPanel.controller.resultCursor ||
          (searchPanel.controller.resultCursor < 0 && resultRow.index === 0 &&
            searchPanel.searchField.activeFocus && searchPanel.controller.results.length > 0)

        width: searchPanel.width
        height: Style.space(54)
        clip: true

        RockLensSelectionChrome {
          anchors.fill: parent
          selected: resultRow.rowSelected
        }

        Column {
          anchors.left: parent.left
          anchors.right: openButton.visible ? openButton.left : parent.right
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
            text: searchPanel.controller.displayCategory(resultRow.modelData.category) +
              " · " + resultRow.modelData.subtitle + " · " + resultRow.modelData.status
            textFormat: Text.PlainText
            color: searchPanel.dim
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        MouseArea {
          anchors.fill: parent
          anchors.rightMargin: openButton.visible ? openButton.width + Style.spacing.sm : 0
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            searchPanel.controller.selectResult(resultRow.index)
            if (resultRow.modelData.category === "People")
              searchPanel.controller.request({op: "person_quick_look", safeId: resultRow.modelData.safeId})
          }
          onDoubleClicked: {
            searchPanel.controller.resultCursor = resultRow.index
            searchPanel.controller.activateResult(resultRow.index)
          }
        }

        Button {
          id: openButton
          visible: resultRow.modelData.canOpen === true &&
            (searchPanel.controller.contextName === "PROD" ||
              resultRow.modelData.category === "Knowledge") && resultRow.rowSelected
          anchors.right: parent.right
          anchors.rightMargin: Style.spacing.sm
          anchors.verticalCenter: parent.verticalCenter
          text: resultRow.modelData.category === "Knowledge" ? "Read" : "Open"
          tooltipText: resultRow.modelData.category === "Knowledge"
            ? "Read in Rock Arch · Enter"
            : "Open in Rock · Enter"
          fontSize: Style.font.caption
          bordered: true
          focusable: false
          z: 2
          onClicked: {
            searchPanel.controller.resultCursor = resultRow.index
            searchPanel.controller.activateResult(resultRow.index)
          }
        }
      }
    }

    Column {
      visible: searchPanel.controller.results.length === 0
      width: parent.width
      topPadding: Style.spacing.xxxl
      bottomPadding: Style.spacing.huge
      spacing: Style.spacing.labelGap

      Text {
        width: parent.width
        text: searchPanel.controller.contextName === "PROD" && !searchPanel.controller.rockConfigured
          && !searchPanel.controller.knowledgeScope
          ? "Rock login required"
          : searchPanel.controller.knowledgeScope &&
            searchPanel.controller.queryWithoutScope(searchPanel.controller.query).length < 3
            ? "Search Rock Knowledge"
            : searchPanel.controller.knowledgeScope
              ? "No knowledge matches"
              : "No matching results"
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
      }

      Text {
        width: parent.width
        text: searchPanel.controller.contextName === "PROD" && !searchPanel.controller.rockConfigured
          && !searchPanel.controller.knowledgeScope
          ? "Open Settings to sign in."
          : searchPanel.controller.knowledgeScope &&
            searchPanel.controller.queryWithoutScope(searchPanel.controller.query).length < 3
            ? "Ask a Rock question using at least three characters."
            : searchPanel.controller.knowledgeScope
              ? "Try different words or a more specific Rock question."
              : "Try a name, ID, GUID, or category prefix."
        textFormat: Text.PlainText
        color: searchPanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
      }
    }

    BorderSurface {
      visible: searchPanel.controller.quickLook !== null
      width: parent.width
      implicitHeight: quickLookContent.implicitHeight + Style.spacing.rowPaddingX * 2
      color: Style.normalFillFor(Color.foreground, Color.accent)
      borderSpec: Border.controlSpec("normal", Color.foreground, Color.accent)
      radius: Style.cornerRadius

      Column {
        id: quickLookContent
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: Style.spacing.rowPaddingX
        anchors.rightMargin: Style.spacing.rowPaddingX
        spacing: Style.spacing.xxs

        Text {
          width: parent.width
          text: searchPanel.controller.quickLook ? searchPanel.controller.quickLook.displayName : ""
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.weight: Font.DemiBold
          elide: Text.ElideRight
        }

        Text {
          width: parent.width
          text: searchPanel.controller.quickLook ? searchPanel.controller.quickLook.subtitle : ""
          textFormat: Text.PlainText
          color: searchPanel.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }

        Text {
          visible: text !== ""
          width: parent.width
          text: searchPanel.controller.quickLook ? searchPanel.controller.quickLook.campus : ""
          textFormat: Text.PlainText
          color: searchPanel.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }
    }
  }

  Column {
    visible: searchPanel.controller.knowledgeDetail !== null
    width: searchPanel.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.panelGap

    RowLayout {
      width: parent.width
      spacing: Style.spacing.sm

      Button {
        id: knowledgeBackButton
        text: "Back"
        tooltipText: "Back to Knowledge results · Esc"
        bordered: true
        focusable: true
        enabled: !searchPanel.controller.knowledgeBusy
        KeyNavigation.right: knowledgeSourceButton.visible
          ? knowledgeSourceButton : knowledgeBackButton
        KeyNavigation.tab: knowledgeSourceButton.visible
          ? knowledgeSourceButton : knowledgeBackButton
        KeyNavigation.backtab: knowledgeSourceButton.visible
          ? knowledgeSourceButton : knowledgeBackButton
        Keys.onEscapePressed: searchPanel.closeKnowledgeDetail()
        onActiveFocusChanged: searchPanel.controller.revealFocusedControl(knowledgeBackButton)
        onClicked: searchPanel.closeKnowledgeDetail()
      }

      Item { Layout.fillWidth: true }

      Button {
        id: knowledgeSourceButton
        visible: searchPanel.controller.knowledgeDetail &&
          searchPanel.controller.knowledgeDetail.canOpenSource === true
        text: searchPanel.controller.knowledgeBusy ? "Opening…" : "Open source"
        tooltipText: "Open the cited public source"
        bordered: true
        focusable: true
        enabled: !searchPanel.controller.knowledgeBusy
        KeyNavigation.left: knowledgeBackButton
        KeyNavigation.tab: knowledgeBackButton
        KeyNavigation.backtab: knowledgeBackButton
        Keys.onEscapePressed: searchPanel.closeKnowledgeDetail()
        onActiveFocusChanged: searchPanel.controller.revealFocusedControl(knowledgeSourceButton)
        onClicked: searchPanel.openKnowledgeSource()
      }
    }

    Column {
      width: parent.width
      spacing: Style.spacing.labelGap

      PanelSectionHeader {
        text: searchPanel.controller.knowledgeDetail
          ? String(searchPanel.controller.knowledgeDetail.kind || "KNOWLEDGE").toUpperCase()
          : "KNOWLEDGE"
      }

      Text {
        width: parent.width
        text: searchPanel.controller.knowledgeDetail
          ? searchPanel.controller.knowledgeDetail.title : ""
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.heading
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
      }

      Text {
        width: parent.width
        text: searchPanel.controller.knowledgeDetail
          ? searchPanel.controller.knowledgeDetail.trust + " · " +
            searchPanel.controller.knowledgeDetail.claimTier + " · " +
            searchPanel.controller.knowledgeDetail.version
          : ""
        textFormat: Text.PlainText
        color: searchPanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }
    }

    PanelSeparator {}

    Text {
      width: parent.width
      text: searchPanel.controller.knowledgeDetail
        ? searchPanel.controller.knowledgeDetail.body : ""
      textFormat: Text.PlainText
      color: Color.foreground
      font.family: Style.font.family
      font.pixelSize: Style.font.bodySmall
      lineHeight: 1.25
      wrapMode: Text.WordWrap
    }

    Text {
      width: parent.width
      text: searchPanel.controller.knowledgeDetail
        ? searchPanel.controller.knowledgeDetail.attribution +
          (searchPanel.controller.knowledgeDetail.sourceHost
            ? " · " + searchPanel.controller.knowledgeDetail.sourceHost : "")
        : ""
      textFormat: Text.PlainText
      color: searchPanel.dim
      font.family: Style.font.family
      font.pixelSize: Style.font.caption
      wrapMode: Text.WordWrap
    }
  }

  Column {
    visible: searchPanel.controller.showRecentLinks
    width: searchPanel.width
    height: visible ? implicitHeight : 0
    spacing: Style.spacing.rowGap

    RowLayout {
      width: parent.width

      PanelSectionHeader {
        text: "RECENT LINKS"
        Layout.fillWidth: true
      }

      Button {
        id: clearRecentButton
        visible: searchPanel.controller.contextName === "PROD"
        text: searchPanel.controller.pendingClearRecent ? "Confirm clear" : "Clear"
        tooltipText: "Clear Recent Links · X"
        foreground: searchPanel.controller.pendingClearRecent ? Color.urgent : Color.foreground
        bordered: searchPanel.controller.pendingClearRecent
        focusable: true
        fontSize: Style.font.caption
        horizontalPadding: Style.spacing.lg
        verticalPadding: Style.spacing.xs
        enabled: searchPanel.controller.quickReturns.length > 0 && !searchPanel.controller.setupBusy
        KeyNavigation.tab: clearRecentButton
        KeyNavigation.backtab: clearRecentButton
        onActiveFocusChanged: searchPanel.controller.revealFocusedControl(clearRecentButton)
        onClicked: searchPanel.controller.clearRecentLinks()
      }
    }

    Column {
      visible: searchPanel.controller.quickReturns.length === 0
      width: parent.width
      topPadding: Style.spacing.xxxl
      bottomPadding: Style.spacing.huge
      spacing: Style.spacing.labelGap

      Text {
        width: parent.width
        text: searchPanel.controller.contextName === "PROD"
          ? "No recent links yet"
          : "Recent Links are hidden in preview mode"
        textFormat: Text.PlainText
        color: Color.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
      }

      Text {
        width: parent.width
        text: searchPanel.controller.contextName === "PROD"
          ? "Search Rock and open an item to add it here."
          : "Start typing to search preview data."
        textFormat: Text.PlainText
        color: searchPanel.dim
        font.family: Style.font.family
        font.pixelSize: Style.font.bodySmall
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
      }
    }

    BorderSurface {
      visible: searchPanel.controller.pendingMagnusBuildId !== "" &&
        searchPanel.controller.pendingMagnusBuildRecent
      width: parent.width
      implicitHeight: buildRecentConfirm.implicitHeight + Style.spacing.rowPaddingX * 2
      color: Style.normalFillFor(Color.urgent, Color.urgent)
      borderSpec: Border.controlSpec("normal", Color.urgent, Color.urgent)
      radius: Style.cornerRadius

      ColumnLayout {
        id: buildRecentConfirm
        anchors.fill: parent
        anchors.margins: Style.spacing.rowPaddingX
        spacing: Style.spacing.labelGap

        Text {
          Layout.fillWidth: true
          text: "Deploy " + searchPanel.controller.pendingMagnusBuildTitle + " again?"
          textFormat: Text.PlainText
          color: Color.foreground
          font.family: Style.font.family
          font.pixelSize: Style.font.body
          font.weight: Font.DemiBold
          wrapMode: Text.WordWrap
        }

        Text {
          Layout.fillWidth: true
          text: "This starts a production mobile-app build."
          textFormat: Text.PlainText
          color: searchPanel.dim
          font.family: Style.font.family
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        RowLayout {
          Item { Layout.fillWidth: true }

          Button {
            id: recentBuildCancelButton
            text: "Cancel"
            focusable: true
            enabled: !searchPanel.controller.magnusActionBusy
            KeyNavigation.right: recentBuildConfirmButton
            KeyNavigation.tab: recentBuildConfirmButton
            KeyNavigation.backtab: recentBuildConfirmButton
            Keys.onEscapePressed: searchPanel.controller.cancelMagnusBuild()
            onClicked: searchPanel.controller.cancelMagnusBuild()
          }

          Button {
            id: recentBuildConfirmButton
            text: searchPanel.controller.magnusActionBusy ? "Deploying…" : "Deploy again"
            foreground: Color.urgent
            bordered: true
            focusable: true
            enabled: !searchPanel.controller.magnusActionBusy
            KeyNavigation.left: recentBuildCancelButton
            KeyNavigation.tab: recentBuildCancelButton
            KeyNavigation.backtab: recentBuildCancelButton
            Keys.onEscapePressed: searchPanel.controller.cancelMagnusBuild()
            onClicked: searchPanel.controller.confirmMagnusBuild()
          }
        }
      }
    }

    Repeater {
      id: quickReturnRepeater
      model: searchPanel.controller.quickReturns

      delegate: Item {
        id: recentRow

        required property var modelData
        required property int index
        readonly property bool rowSelected: recentRow.index === searchPanel.controller.recentCursor ||
          (searchPanel.controller.recentCursor < 0 && recentRow.index === 0 &&
            searchPanel.searchField.activeFocus && searchPanel.controller.quickReturns.length > 0)

        width: searchPanel.width
        height: Style.space(54)
        clip: true

        RockLensSelectionChrome {
          anchors.fill: parent
          selected: recentRow.rowSelected
        }

        Column {
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          anchors.leftMargin: Style.spacing.rowPaddingX
          anchors.rightMargin: Style.spacing.rowPaddingX
          spacing: Style.spacing.xxs

          Text {
            width: parent.width
            text: recentRow.modelData.title
            textFormat: Text.PlainText
            color: Color.foreground
            font.family: Style.font.family
            font.pixelSize: Style.font.body
            font.weight: Font.DemiBold
            elide: Text.ElideRight
          }

          Text {
            width: parent.width
            text: recentRow.modelData.kind === "Magnus Build"
              ? "Last deployed " + searchPanel.controller.relativeTime(recentRow.modelData.lastUsedAt) +
                " · Enter to deploy again"
              : recentRow.modelData.kind
            textFormat: Text.PlainText
            color: searchPanel.dim
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        MouseArea {
          anchors.fill: parent
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            searchPanel.controller.selectRecent(recentRow.index)
            searchPanel.controller.activateRecent(recentRow.index)
          }
        }
      }
    }
  }
}
