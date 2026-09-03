import QtQuick

// Rock Arch-local variant of Omarchy's PanelKeyCatcher. It keeps the shared
// navigation semantics and adds one explicit Backspace action for returning a
// highlighted item to the search editor.
Item {
  id: root
  clip: true

  property bool blocked: false
  property bool formMode: false
  property bool commandMode: false
  property bool backspaceEnabled: false

  signal moveRequested(int dx, int dy)
  signal activateRequested()
  signal returnRequested()
  signal closeRequested()
  signal deleteRequested()
  signal tabRequested(int direction)
  signal textKey(string text)
  signal backspaceRequested()

  focus: true
  Keys.priority: Keys.BeforeItem
  Keys.onPressed: function(event) {
    if (event.key === Qt.Key_Escape) {
      closeRequested(); event.accepted = true; return
    }

    // Magnus previews use native Tab focus, but their displayed single-key
    // commands still need to work from a focused action button.
    if (!blocked && commandMode && event.text && event.text.length === 1 &&
        "dchor".indexOf(event.text.toLowerCase()) >= 0) {
      textKey(event.text); event.accepted = true; return
    }

    // Forms use Qt's native focus chain so Tab, Shift+Tab, typing, and control
    // activation reach the focused field or button. Escape remains global.
    if (blocked || formMode) return

    if (backspaceEnabled && event.key === Qt.Key_Backspace &&
        !(event.modifiers & (Qt.AltModifier | Qt.MetaModifier))) {
      backspaceRequested(); event.accepted = true; return
    }
    if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
      tabRequested((event.modifiers & Qt.ShiftModifier) ||
        event.key === Qt.Key_Backtab ? -1 : 1)
      event.accepted = true
      return
    }
    if (event.key === Qt.Key_Down || event.text === "j") {
      moveRequested(0, 1); event.accepted = true; return
    }
    if (event.key === Qt.Key_Up || event.text === "k") {
      moveRequested(0, -1); event.accepted = true; return
    }
    if (event.key === Qt.Key_Right || event.text === "l") {
      moveRequested(1, 0); event.accepted = true; return
    }
    if (event.key === Qt.Key_Left || event.text === "h") {
      moveRequested(-1, 0); event.accepted = true; return
    }
    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
      returnRequested()
      activateRequested(); event.accepted = true; return
    }
    if (event.key === Qt.Key_Space) {
      activateRequested(); event.accepted = true; return
    }
    if (event.key === Qt.Key_Delete || event.text === "x" || event.text === "X") {
      deleteRequested(); event.accepted = true; return
    }
    if (event.text && event.text.length === 1) textKey(event.text)
  }
}
