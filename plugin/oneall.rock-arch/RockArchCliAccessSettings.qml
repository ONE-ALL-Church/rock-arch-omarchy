pragma ComponentBehavior: Bound
import QtQuick
import qs.Commons
import qs.Ui

Column {
  id: access
  required property var controller
  spacing: Style.spacing.rowGap

  PanelSectionHeader { text: "CLI AND AGENT ACCESS" }

  Toggle {
    id: readAccess
    width: parent.width
    label: "Read access"
    description: !access.controller.preferenceTerminalAccess
      ? "Rock commands are disabled. Local settings remain editable."
      : access.controller.terminalError === "cli_launcher_conflict"
        ? "Another rock-arch command is already installed."
        : access.controller.terminalError === "cli_launcher_managed_manually"
          ? "Terminal setup is managed outside this checkout."
          : access.controller.terminalError
            ? "The rock-arch command could not be installed."
            : access.controller.terminalInstalled
              ? (access.controller.terminalInPath
                ? "Search, inspect, and preview with rock-arch."
                : "Add ~/.local/bin to your terminal's PATH to use rock-arch.")
              : "The rock-arch command is not available."
    checked: access.controller.preferenceTerminalAccess
    onActiveFocusChanged: access.controller.revealFocusedControl(readAccess)
    onClicked: access.controller.toggleTerminalAccessPreference()
  }

  Toggle {
    id: mutationAccess
    width: parent.width
    label: "Allow mutations"
    description: !access.controller.preferenceTerminalAccess
      ? "Read access is required to use Rock commands."
      : checked
        ? "Only the actions enabled below are allowed. Confirmation is still required."
        : "CLI changes to Rock and Magnus are disabled."
    checked: access.controller.preferenceTerminalMutationAccess
    enabled: access.controller.preferenceTerminalAccess
    opacity: enabled ? 1 : 0.5
    onActiveFocusChanged: access.controller.revealFocusedControl(mutationAccess)
    onClicked: access.controller.toggleTerminalMutationAccessPreference()
  }

  Column {
    width: parent.width - Style.spacing.rowPaddingX
    x: Style.spacing.rowPaddingX
    visible: access.controller.preferenceTerminalMutationAccess
    enabled: access.controller.preferenceTerminalAccess
    opacity: enabled ? 1 : 0.5
    spacing: Style.spacing.rowGap

    Repeater {
      model: [
        {action: "addLinks", label: "Add links"},
        {action: "addSections", label: "Add sections"},
        {action: "deleteLinks", label: "Delete links"},
        {action: "deleteSections", label: "Delete sections"},
        {action: "runJobs", label: "Run jobs"},
        {action: "buildMagnus", label: "Start Magnus builds"}
      ]
      delegate: Toggle {
        id: actionToggle
        required property var modelData
        width: parent.width
        label: modelData.label
        titleSize: Style.font.body
        description: modelData.action === "deleteSections"
          ? "Sections with links also require Delete links."
          : modelData.action === "addSections"
            ? "Includes the first Links section created for a bookmark."
            : ""
        checked: access.controller.preferenceTerminalMutationActions.indexOf(modelData.action) >= 0
        onActiveFocusChanged: access.controller.revealFocusedControl(actionToggle)
        onClicked: access.controller.toggleTerminalMutationAction(modelData.action)
      }
    }
  }
}
