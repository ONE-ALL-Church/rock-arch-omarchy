import QtQuick

// One focus stop for a list whose rows use the shared keyboard cursor.
Item {
  required property var controller
  activeFocusOnTab: true
  Accessible.role: Accessible.List
  onActiveFocusChanged: if (activeFocus) controller.ensureListSelection()
}
