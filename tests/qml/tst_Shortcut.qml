import QtQml
import QtTest
import "../../plugin/oneall.rock-arch" as RockArch

TestCase {
  name: "ShortcutSetup"
  property var model
  property var requests
  property int icons: 0
  Component { id: factory; RockArch.RockArchShortcut {} }

  function init() {
    requests = []; icons = 0
    model = createTemporaryObject(factory, this)
    verify(model !== null)
    model.requested.connect(function(payload) { requests.push(payload) })
    model.showIconRequested.connect(function() { icons++ })
  }
  function available(combo) {
    model.accept({state: "available", combo: combo || "SUPER + R", currentCombo: "", editable: true, revision: "checked"})
  }
  function configured(managed) {
    model.accept({state: "configured", combo: "SUPER + R", currentCombo: "SUPER + R", currentActive: true,
      managed: managed, editable: true, revision: "checked"})
  }
  function test_setup_is_opt_in_and_uses_fixed_operation() {
    available()
    compare(requests.length, 0)
    model.install()
    compare(requests, [{op: "shortcut_install", combo: "SUPER + R", revision: "checked", confirmed: true}])
    model.install()
    compare(requests.length, 1)
  }
  function test_changing_candidate_requires_new_conflict_check() {
    available()
    model.choose()
    model.draft = "shift+super+r"
    verify(!model.canSave)
    model.install()
    compare(requests.length, 0)
    model.check()
    compare(requests[0].combo, "SUPER + SHIFT + R")
    available("SUPER + SHIFT + R")
    verify(model.canSave)
    model.install()
    compare(requests[1].op, "shortcut_install")
  }
  function test_conflict_is_displayed_and_cannot_be_saved() {
    model.accept({state: "conflict", combo: "SUPER + CTRL + R", conflict: "Reminder", editable: true})
    verify(model.message().indexOf("Reminder") >= 0)
    model.install()
    compare(requests.length, 0)
  }
  function test_external_binding_is_recognized_and_cannot_be_managed() {
    configured(false)
    verify(model.configured)
    verify(!model.canManage)
    verify(model.message().indexOf("already opens Rock Arch") >= 0)
    model.removing = true
    model.remove()
    compare(requests.length, 0)
  }
  function test_removal_restores_menu_icon_and_requires_confirmation() {
    configured(true)
    model.remove()
    compare(requests.length, 0)
    model.removing = true
    model.remove()
    compare(icons, 1)
    compare(requests[0].op, "shortcut_remove")
    verify(requests[0].confirmed)
  }
  function test_interruption_requires_fresh_status_and_does_not_replay_mutation() {
    available()
    model.install()
    model.interrupted()
    verify(!model.busy)
    verify(!model.canSave)
    model.install()
    compare(requests.length, 1)
    model.refresh()
    compare(requests[1].op, "shortcut_status")
  }
  function test_preview_and_invalid_keys_cannot_be_saved() {
    model.accept({state: "unavailable", editable: false, error: "preview_mode"})
    model.install()
    compare(requests.length, 0)
    verify(model.message().indexOf("Preview") >= 0)
    available()
    model.choose()
    model.draft = "Super+R; other-command"
    model.check()
    compare(requests.length, 0)
    verify(model.notice.indexOf("Use Super") >= 0)
  }
  function test_closing_discards_stale_forms_and_feedback() {
    configured(true)
    model.choose()
    model.removing = true
    model.notice = "Old feedback"
    model.closed()
    verify(!model.editing)
    verify(!model.removing)
    compare(model.notice, "")
  }
  function test_save_completes_setup_with_a_simple_confirmation() {
    available()
    model.choose()
    model.install()
    model.accept({state: "configured", combo: "SUPER + R", currentCombo: "SUPER + R", currentActive: true,
      managed: true, editable: true, revision: "saved", saved: true})
    verify(!model.editing)
    verify(!model.busy)
    verify(model.canManage)
    compare(model.notice, "Super + R is configured.")
    var resultNotice = model.notice
    model.refresh(true)
    configured(true)
    compare(model.message(), resultNotice)
  }
}
