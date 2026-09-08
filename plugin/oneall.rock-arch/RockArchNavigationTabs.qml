pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

FocusScope {
  id: navigation
  required property var controller
  readonly property var tabs: controller.navigationTabs
  readonly property string selectedKey: controller.viewMode === "settings" ? controller.settingsReturnView : controller.viewMode
  readonly property bool inputActive: activeFocus
  activeFocusOnTab: true
  implicitHeight: buttons.implicitHeight
  Accessible.role: Accessible.PageTabList
  Accessible.name: "Workspaces"

  function focusCurrent() {
    var index = tabs.findIndex(function(tab) { return tab.key === selectedKey })
    var button = tabButtons.itemAt(Math.max(0, index))
    if (button) button.forceActiveFocus(Qt.TabFocusReason)
  }
  function selectAt(index) {
    if (index < 0 || index >= tabs.length) return
    controller.openTab(tabs[index].key, true)
    Qt.callLater(focusCurrent)
  }
  function move(direction) {
    var index = tabs.findIndex(function(tab) { return tab.key === selectedKey })
    selectAt((index + direction + tabs.length) % tabs.length)
  }
  Keys.onLeftPressed: move(-1)
  Keys.onRightPressed: move(1)
  Keys.onPressed: function(event) {
    if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) return
    if (event.key === Qt.Key_Home) { selectAt(0); event.accepted = true }
    else if (event.key === Qt.Key_End) { selectAt(tabs.length - 1); event.accepted = true }
  }
  Keys.onDownPressed: controller.focusWorkspace(false)
  Keys.onTabPressed: controller.moveTab(1)
  Keys.onBacktabPressed: controller.moveTab(-1)

  RowLayout {
    id: buttons
    anchors.left: parent.left
    anchors.right: parent.right
    spacing: Style.spacing.xs
    Repeater {
      id: tabButtons
      model: navigation.controller.onboardingFlowActive ? [] : navigation.controller.navigationTabs
      delegate: Button {
        id: tab
        required property var modelData
        text: tab.modelData.label
        tooltipText: tab.modelData.label + " · " + tab.modelData.shortcut + " · Ctrl+Tab"
        selected: navigation.controller.viewMode === tab.modelData.key
        fontSize: Style.font.bodySmall
        horizontalPadding: Style.spacing.lg
        verticalPadding: Style.spacing.xs
        focusable: true
        activeFocusOnTab: false
        focus: navigation.selectedKey === modelData.key
        enabled: navigation.controller.workspaceNavigationEnabled
        Accessible.role: Accessible.PageTab
        Accessible.name: modelData.label
        Accessible.description: modelData.shortcut
        Accessible.onPressAction: clicked()
        onClicked: navigation.controller.openTab(modelData.key, true)
      }
    }
    Item { Layout.fillWidth: true }
  }
}
