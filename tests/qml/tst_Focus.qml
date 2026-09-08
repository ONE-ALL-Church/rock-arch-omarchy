import QtQuick
import QtTest
import "../../plugin/oneall.rock-arch/RockArchFocus.js" as Focus
import "../../plugin/oneall.rock-arch/RockArchSearchScopes.js" as Scopes
import "../../plugin/oneall.rock-arch"

Item {
  width: 200; height: 100
  Item {
    id: controls
    Item { id: first; activeFocusOnTab: true }
    FocusScope {
      id: composite
      activeFocusOnTab: true
      Item { id: nested; activeFocusOnTab: true }
    }
    Item { visible: false; Item { activeFocusOnTab: true } }
    Item { enabled: false; Item { activeFocusOnTab: true } }
    Item { id: last; activeFocusOnTab: true }
  }
  RockArchKeyCatcher { id: catcher }
  SignalSpy { id: tabSpy; target: catcher; signalName: "tabRequested" }
  SignalSpy { id: textSpy; target: catcher; signalName: "textKey" }
  SignalSpy { id: backspaceSpy; target: catcher; signalName: "backspaceRequested" }
  TestCase {
    name: "FocusContract"
    when: windowShown
    function init() {
      catcher.blocked = false; catcher.formMode = false; catcher.commandMode = true; catcher.backspaceEnabled = true
      catcher.forceActiveFocus(); tabSpy.clear(); textSpy.clear(); backspaceSpy.clear()
    }
    function test_composites_have_one_stop_and_unavailable_controls_are_skipped() {
      compare(Focus.stops(controls), [first, composite, last])
      compare(Focus.next(Focus.stops(controls), nested, 1), last)
      compare(Focus.next(Focus.stops(controls), nested, -1), first)
      compare(Focus.next(Focus.stops(controls), last, 1), first)
      compare(Focus.next([], first, 1), null)
    }
    function test_modified_keys_never_become_plain_navigation_or_actions() {
      keyClick(Qt.Key_Tab, Qt.ControlModifier)
      keyClick(Qt.Key_Backtab, Qt.ControlModifier | Qt.ShiftModifier)
      keyClick(Qt.Key_C, Qt.ControlModifier)
      keyClick(Qt.Key_Backspace, Qt.ControlModifier)
      compare(tabSpy.count, 0); compare(textSpy.count, 0); compare(backspaceSpy.count, 0)
      keyClick(Qt.Key_Tab)
      compare(tabSpy.count, 1)
    }
    function test_scope_examples_are_static_and_permission_filtered() {
      var options = Scopes.options(["People", "Groups", "Defined Types"], ["Defined Types"])
      compare(Scopes.placeholder(options), "Search Rock… dt: Status")
      compare(Scopes.placeholder([]), "Search Rock by name or ID")
    }
  }
}
