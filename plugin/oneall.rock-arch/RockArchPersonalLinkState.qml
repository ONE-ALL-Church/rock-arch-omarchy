import QtQml

QtObject {
  id: state
  property bool editing: false
  property bool busy: false
  property bool saving: false
  property string draftId: ""
  property string requestId: ""
  property int revision: 0
  property string name: ""
  property string url: ""
  property string sectionId: ""
  property var sections: []
  property string notice: ""
  readonly property bool canSave: editing && !busy && draftId !== "" &&
    name.trim().length > 0 && name.trim().length <= 100 && url.trim().length > 0 &&
    sections.some(function(item) { return item.safeId === state.sectionId })
  signal requested(var payload)
  signal focusRequested()
  signal cancelled()
  signal saved(bool alreadySaved, string name, string section)

  function send(payload) {
    requestId = "personal-link-" + (++revision)
    payload.requestId = requestId
    busy = true
    requested(payload)
  }
  function begin(safeId) {
    closed()
    editing = true
    var payload = {op: "personal_link_prepare"}
    if (safeId) payload.safeId = safeId
    send(payload)
  }
  function reload() {
    if (!editing || busy) return
    notice = ""
    draftId = ""
    send({op: "personal_link_prepare", name: name, url: url})
  }
  function save() {
    if (!canSave) return
    saving = true
    notice = ""
    send({op: "personal_link_save", draftId: draftId, name: name.trim(),
      url: url.trim(), sectionId: sectionId, confirmed: true})
  }
  function accept(value) {
    if (!editing || !busy || !value || value.requestId !== requestId) return
    var wasSaving = saving
    busy = false
    saving = false
    if (value.error) {
      if (wasSaving) draftId = ""
      notice = message(String(value.error))
      return
    }
    if (value.saved === true) {
      closed()
      saved(value.alreadySaved === true, String(value.name || ""), String(value.section || ""))
      return
    }
    if (!value.draftId || !Array.isArray(value.sections)) {
      draftId = ""
      notice = "Rock Arch couldn't load the link form. Reload to try again."
      return
    }
    draftId = String(value.draftId)
    name = String(value.name || "")
    url = String(value.url || "")
    sections = value.sections
    if (!sections.some(function(item) { return item.safeId === state.sectionId }))
      sectionId = String(value.sectionId || "")
    focusRequested()
  }
  function interrupted() {
    if (!editing || !busy) return
    notice = saving
      ? "Rock may have saved this link. Check Links before trying again."
      : "Connection interrupted. Reload to try again."
    busy = false
    saving = false
    draftId = ""
    requestId = ""
  }
  function closed() {
    editing = false
    busy = false
    saving = false
    draftId = ""
    requestId = ""
    name = ""
    url = ""
    sectionId = ""
    sections = []
    notice = ""
  }
  function cancel() {
    if (saving) return
    closed()
    cancelled()
  }
  function message(code) {
    if (code === "personal_link_name_invalid") return "Enter a name of 1–100 characters."
    if (code === "personal_link_url_invalid") return "Use an HTTPS URL on this Rock instance, or a path such as /page/42."
    if (code === "personal_link_draft_expired") return "This link form has expired. Reload before saving."
    if (code === "personal_link_account_changed") return "The Rock account changed. Reopen Add link to continue."
    if (code === "personal_link_section_changed") return "That personal section changed. Reload and choose a section."
    if (code === "personal_link_save_uncertain") return "Rock may have saved this link. Check Links before trying again."
    if (code === "personal_links_not_authorized") return "Rock doesn't permit this action for your account. Your Rock administrator can review Personal Links API access."
    if (code === "personal_links_preview_only") return "Saving Personal Links is unavailable in Preview."
    if (code === "personal_link_source_invalid") return "That search result has expired. Search again and choose Save."
    if (code === "personal_link_rejected") return "Rock rejected the link. Check its name, URL, and section."
    if (code === "rock_login_required" || code === "rock_login_failed") return "Sign in to Rock again, then reopen Add link."
    return "Rock Arch couldn't load or save this link. Reload to try again."
  }
}
