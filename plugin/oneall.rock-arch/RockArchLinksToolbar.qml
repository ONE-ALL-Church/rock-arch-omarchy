pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import qs.Commons
import qs.Ui

RowLayout {
  id: toolbar

  required property var controller
  property alias addButton: addAction
  readonly property bool canAdd: controller.rockConfigured && controller.contextName === "PROD"
  readonly property bool inputActive: viewChoice.activeFocus || addAction.activeFocus || addMenu.opened
  readonly property var views: [
    {value: "sections", label: "Sections", description: "Browse links by section"},
    {value: "alpha", label: "A–Z", description: "All links alphabetically"}
  ]
  signal listFocusRequested()

  spacing: Style.spacing.controlGap

  function focusView() { viewChoice.forceActiveFocus(Qt.TabFocusReason) }
  function focusLast() {
    if (canAdd) addAction.forceActiveFocus(Qt.BacktabFocusReason)
    else focusView()
  }
  function closeMenu() { addMenu.restoreFocus = false; addMenu.close() }
  function openAddMenu() { if (visible && canAdd) addMenu.open() }
  function activateView(index) {
    viewChoice.forceActiveFocus()
    viewChoice.cursor = index
    controller.setLinkView(views[index].value)
  }
  function activateAdd(index) {
    addMenu.restoreFocus = false
    addMenu.close()
    if (index === 1) controller.beginPersonalSection()
    else controller.beginPersonalLink("")
  }
  onVisibleChanged: if (!visible) { addMenu.restoreFocus = false; addMenu.close() }
  onCanAddChanged: if (!canAdd) { addMenu.restoreFocus = false; addMenu.close() }

  FocusScope {
    id: viewChoice
    property int cursor: 0
    implicitWidth: choices.implicitWidth
    implicitHeight: choices.implicitHeight
    activeFocusOnTab: true
    Accessible.role: Accessible.Grouping
    Accessible.name: "Links view"
    onActiveFocusChanged: if (activeFocus) cursor = toolbar.controller.preferencePersonalLinksView === "alpha" ? 1 : 0
    Keys.onLeftPressed: cursor = Math.max(0, cursor - 1)
    Keys.onRightPressed: cursor = Math.min(toolbar.views.length - 1, cursor + 1)
    Keys.onReturnPressed: toolbar.activateView(cursor)
    Keys.onEnterPressed: toolbar.activateView(cursor)
    Keys.onSpacePressed: toolbar.activateView(cursor)
    Keys.onDownPressed: toolbar.listFocusRequested()
    Keys.onTabPressed: { if (toolbar.canAdd) addAction.forceActiveFocus(Qt.TabFocusReason); else toolbar.listFocusRequested() }
    Keys.onBacktabPressed: toolbar.controller.focusTabBar()
    Keys.onPressed: function(event) {
      if (event.text === "h") { cursor = Math.max(0, cursor - 1); event.accepted = true }
      else if (event.text === "l") { cursor = Math.min(toolbar.views.length - 1, cursor + 1); event.accepted = true }
    }

    Row {
      id: choices
      spacing: Style.spacing.md
      Repeater {
        model: toolbar.views
        Button {
          required property var modelData
          required property int index
          text: modelData.label
          fontSize: Style.font.bodySmall
          height: Math.max(Style.spacing.controlHeight, implicitHeight)
          bordered: true
          focusable: true
          activeFocusOnTab: false
          focus: viewChoice.cursor === index
          selected: toolbar.controller.preferencePersonalLinksView === modelData.value
          hasCursor: viewChoice.activeFocus && viewChoice.cursor === index
          tooltipText: modelData.description
          Accessible.role: Accessible.RadioButton
          Accessible.name: modelData.label
          Accessible.description: modelData.description
          Accessible.checkable: true
          Accessible.checked: selected
          Accessible.onPressAction: toolbar.activateView(index)
          onClicked: toolbar.activateView(index)
        }
      }
    }
  }

  Item { Layout.fillWidth: true }

  Button {
    id: addAction
    visible: toolbar.canAdd
    text: "Add  󰅀"
    fontSize: Style.font.bodySmall
    Layout.preferredHeight: viewChoice.implicitHeight
    focusable: true
    bordered: true
    tooltipText: "Add link or section · Ctrl+N"
    Accessible.role: Accessible.Button
    Accessible.name: "Add link or section"
    Accessible.description: "Opens a menu"
    Accessible.onPressAction: clicked()
    onClicked: addMenu.opened ? addMenu.close() : toolbar.openAddMenu()
    Keys.onDownPressed: toolbar.openAddMenu()
    Keys.onTabPressed: toolbar.listFocusRequested()
    Keys.onBacktabPressed: toolbar.focusView()

    QQC.Popup {
      id: addMenu
      property int cursor: 0
      property bool restoreFocus: true
      width: Math.max(Style.space(128), menuItems.implicitWidth + leftPadding + rightPadding)
      x: addAction.width - width
      y: addAction.height + Style.spacing.xxs
      implicitHeight: menuItems.implicitHeight + topPadding + bottomPadding
      padding: Style.spacing.xxs
      focus: true
      closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutsideParent
      background: BorderSurface {
        color: Color.popups.background
        borderSpec: Border.surfaceSpec("popups", "border", Color.popups.border, Style.normalBorderWidth)
        radius: Style.cornerRadius
      }
      onOpened: { cursor = 0; restoreFocus = true; menuItems.forceActiveFocus() }
      onClosed: if (restoreFocus && toolbar.visible) addAction.forceActiveFocus(Qt.PopupFocusReason)

      contentItem: ColumnLayout {
        id: menuItems
        spacing: Style.spacing.labelGap
        Keys.onEscapePressed: addMenu.close()
        Keys.onUpPressed: addMenu.cursor = Math.max(0, addMenu.cursor - 1)
        Keys.onDownPressed: addMenu.cursor = Math.min(1, addMenu.cursor + 1)
        Keys.onReturnPressed: toolbar.activateAdd(addMenu.cursor)
        Keys.onEnterPressed: toolbar.activateAdd(addMenu.cursor)
        Keys.onSpacePressed: toolbar.activateAdd(addMenu.cursor)
        Keys.onTabPressed: { addMenu.restoreFocus = false; addMenu.close(); toolbar.listFocusRequested() }
        Keys.onBacktabPressed: { addMenu.restoreFocus = false; addMenu.close(); toolbar.focusView() }
        Keys.onPressed: function(event) {
          if (event.text === "j") { addMenu.cursor = Math.min(1, addMenu.cursor + 1); event.accepted = true }
          else if (event.text === "k") { addMenu.cursor = Math.max(0, addMenu.cursor - 1); event.accepted = true }
        }
        Repeater {
          model: ["Link…", "Section…"]
          Button {
            required property string modelData
            required property int index
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(Style.spacing.popupRowHeight, implicitHeight)
            text: modelData
            leftAlign: true
            hasCursor: addMenu.cursor === index
            Accessible.role: Accessible.MenuItem
            Accessible.name: modelData
            Accessible.onPressAction: toolbar.activateAdd(index)
            onHovered: function(hovered) { if (hovered) addMenu.cursor = index }
            onClicked: toolbar.activateAdd(index)
          }
        }
      }
    }
  }
}
