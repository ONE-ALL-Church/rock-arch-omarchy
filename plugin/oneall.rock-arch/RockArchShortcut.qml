import QtQml

QtObject {
  id: shortcut
  property var snapshot: ({state: "unknown", combo: "SUPER + R", currentCombo: "", currentActive: false, managed: false, editable: false})
  property bool busy: false
  property bool editing: false
  property bool removing: false
  property string draft: "SUPER + R"
  property string notice: ""
  readonly property bool configured: snapshot.currentActive === true
  readonly property bool canManage: snapshot.managed === true && snapshot.editable === true
  readonly property bool canSave: !busy && snapshot.editable === true &&
    !snapshot.error && snapshot.state === "available" && normalizedDraft() === snapshot.combo
  signal requested(var payload)
  signal showIconRequested()

  function label(combo) { return String(combo || "Super + R").replace(/SUPER/g, "Super").replace(/CTRL/g, "Ctrl").replace(/ALT/g, "Alt").replace(/SHIFT/g, "Shift") }
  function normalizedDraft() {
    var parts = draft.toUpperCase().split("+").map(function(value) { return value.trim() })
    var key = parts.pop()
    var mods = ["SUPER", "CTRL", "ALT", "SHIFT"]
    if (parts.indexOf("SUPER") < 0 || !/^([A-Z0-9]|F([1-9]|1[0-2]))$/.test(key)) return ""
    for (var i = 0; i < parts.length; i++)
      if (mods.indexOf(parts[i]) < 0 || parts.indexOf(parts[i]) !== i) return ""
    return mods.filter(function(mod) { return parts.indexOf(mod) >= 0 }).concat([key]).join(" + ")
  }
  function send(op, combo, preserveNotice) {
    if (busy) return
    busy = true
    if (!preserveNotice) notice = ""
    requestTimeout.restart()
    requested({op: op, combo: combo || "", revision: snapshot.revision || "", confirmed: op !== "shortcut_status"})
  }
  function refresh(preserveNotice) { send("shortcut_status", editing ? normalizedDraft() : "", preserveNotice === true) }
  function check() {
    if (!normalizedDraft()) {
      notice = "Use Super with a letter, number, or F1–F12. You can add Ctrl, Alt, or Shift."
      return
    }
    send("shortcut_status", normalizedDraft())
  }
  function choose() {
    editing = true
    removing = false
    draft = snapshot.combo || "SUPER + R"
    notice = ""
  }
  function cancel() {
    editing = false
    removing = false
    refresh()
  }
  function install() {
    if (!canSave) return
    send("shortcut_install", normalizedDraft())
  }
  function remove() {
    if (busy || !snapshot.managed || !snapshot.editable || !removing) return
    if (snapshot.error) { refresh(); return }
    showIconRequested()
    send("shortcut_remove", snapshot.currentCombo)
  }
  function accept(value) {
    requestTimeout.stop()
    busy = false
    snapshot = value
    if (!editing) draft = value.combo || "SUPER + R"
    if (value.saved) {
      editing = false
      removing = false
      draft = value.combo || "SUPER + R"
      notice = value.currentActive ? label(value.currentCombo) + " is configured." : "Shortcut removed."
    }
  }
  function interrupted() {
    if (!busy) return
    requestTimeout.stop()
    busy = false
    snapshot = Object.assign({}, snapshot, {revision: "", editable: false})
    notice = "The connection was interrupted. Check again before making another change."
  }
  function closed() {
    editing = false
    removing = false
    notice = ""
  }
  function message() {
    if (notice) return notice
    var errors = {
      preview_mode: "Shortcut changes are unavailable in Preview.",
      source_checkout: "Install Rock Arch through Omarchy to manage shortcuts here.",
      invalid_shortcut: "Use Super with a letter, number, or F1–F12, plus optional Ctrl, Alt, or Shift.",
      config_changed: "Bindings changed since the last check. Check again before saving.",
      shortcut_conflict: "That shortcut is already assigned. Choose another.",
      config_errors: "Hyprland has configuration errors. Fix them before adding a shortcut.",
      managed_block_changed: "The Rock Arch binding was edited outside this interface. Manage it in your Hyprland configuration.",
      not_managed: "This shortcut is managed in your Hyprland configuration.",
      icon_restore_failed: "Could not save the menu-bar icon preference. The shortcut was kept so you can still open Rock Arch.",
      change_rolled_back: "Hyprland could not apply the change. Your previous configuration was restored.",
      rollback_conflict: "Another edit prevented automatic restore. Review bindings.lua and its .rock-arch-shortcut-backup file.",
      rollback_failed: "The previous file was restored, but Hyprland still needs attention. Check hyprctl configerrors and reload.",
      unsupported_config: "Automatic setup needs Omarchy’s bindings.lua configuration. Add a shortcut manually on this setup.",
      unsafe_config: "This configuration is linked, shared, or has unsafe permissions. Manage the shortcut manually.",
      config_unavailable: "Could not read the Omarchy configuration. Manage the shortcut manually.",
      hyprland_unavailable: "Could not reach Hyprland. Check again from your Omarchy desktop.",
      bindings_unavailable: "Could not check active bindings. Check again before saving.",
      keymap_unavailable: "Could not resolve physical shortcuts for this keyboard layout. Manage the shortcut in your Hyprland configuration."
    }
    if (snapshot.error) return errors[snapshot.error] || "Could not change the shortcut. Check again."
    if (editing && normalizedDraft() !== snapshot.combo) return "Check this shortcut before saving."
    if (snapshot.state === "conflict") return label(snapshot.combo) + " is used by " + (snapshot.conflict || "another action") + ". Choose another shortcut."
    if (configured && !snapshot.managed) return label(snapshot.currentCombo) + " already opens Rock Arch."
    if (configured) return label(snapshot.currentCombo) + " opens Rock Arch."
    if (snapshot.managed) return "The saved shortcut is inactive. Check for configuration changes or choose another shortcut."
    if (snapshot.state === "available") return label(snapshot.combo) + " is available. Adding a shortcut is optional."
    return "Check whether a shortcut is available."
  }
  property Timer requestTimeout: Timer { interval: 15000; onTriggered: shortcut.interrupted() }
}
