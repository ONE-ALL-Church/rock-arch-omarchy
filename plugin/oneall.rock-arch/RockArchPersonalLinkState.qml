import QtQml

QtObject {
  id: state
  property bool editing: false
  property bool busy: false
  property bool saving: false
  property string kind: "link"
  readonly property bool deleting: kind.indexOf("delete-") === 0
  property string deleteTarget: ""
  property string sectionName: ""
  property string draftId: ""
  property string requestId: ""
  property int revision: 0
  property string name: ""
  property string url: ""
  property string sectionId: ""
  property var sections: []
  property string notice: ""
  readonly property bool canSave: editing && !busy && draftId !== "" &&
    (deleting || (name.trim().length > 0 && name.trim().length <= 100 && (kind === "section" ||
    (url.trim().length > 0 && sections.some(function(item) { return item.safeId === state.sectionId })))))
  signal requested(var payload)
  signal focusRequested()
  signal cancelled(bool wasDeleting)
  signal saved(bool alreadySaved, string name, string section)
  signal deleted(string kind, string groupId)
  signal savedSection(bool alreadySaved, string name, string groupId)

  function send(payload) {
    requestId = "personal-link-" + (++revision)
    payload.requestId = requestId
    busy = true
    requested(payload)
  }
  function begin(safeId, preferredSection) {
    closed()
    editing = true
    sectionId = preferredSection || ""
    var payload = {op: "personal_link_prepare"}
    if (safeId) payload.safeId = safeId
    send(payload)
  }
  function beginDelete(itemKind, targetId) {
    closed()
    kind = "delete-" + itemKind
    deleteTarget = targetId
    editing = true
    send({op: "personal_delete_prepare", kind: itemKind, targetId: targetId})
  }
  function beginSection() {
    closed()
    kind = "section"
    editing = true
    send({op: "personal_section_prepare"})
  }
  function reload() {
    if (!editing || busy) return
    notice = ""
    draftId = ""
    send(deleting ? {op: "personal_delete_prepare", kind: kind.slice(7), targetId: deleteTarget}
      : kind === "section" ? {op: "personal_section_prepare", name: name}
      : {op: "personal_link_prepare", name: name, url: url})
  }
  function save() {
    if (!canSave) return
    saving = true
    notice = ""
    send(deleting ? {op: "personal_delete_commit", draftId: draftId, confirmed: true}
      : kind === "section" ? {op: "personal_section_save", draftId: draftId, name: name.trim(), confirmed: true}
      : {op: "personal_link_save", draftId: draftId, name: name.trim(),
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
    if (value.deleted === true && deleting) {
      var deletedKind = kind.slice(7)
      closed()
      deleted(deletedKind, String(value.groupId || ""))
      return
    }
    if (value.saved === true) {
      var wasSection = kind === "section"
      closed()
      if (wasSection) savedSection(value.alreadySaved === true, String(value.name || ""), String(value.groupId || ""))
      else saved(value.alreadySaved === true, String(value.name || ""), String(value.section || ""))
      return
    }
    if (!value.draftId || !Array.isArray(value.sections)) {
      draftId = ""
      notice = "Rock Arch couldn't load the form. Reload to try again."
      return
    }
    draftId = String(value.draftId)
    name = String(value.name || "")
    sectionName = String(value.section || "")
    url = String(value.url || "")
    sections = value.sections
    if (!sections.some(function(item) { return item.safeId === state.sectionId }))
      sectionId = String(value.sectionId || "")
    focusRequested()
  }
  function interrupted() {
    if (!editing || !busy) return
    notice = saving
      ? (deleting ? "Rock may have deleted this item. Check Links before trying again." : "Rock may have saved this " + kind + ". Check Links before trying again.")
      : "Connection interrupted. Reload to try again."
    busy = false
    saving = false
    draftId = ""
    requestId = ""
  }
  function closed() {
    editing = false
    kind = "link"
    deleteTarget = ""
    sectionName = ""
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
    var wasDeleting = deleting
    closed()
    cancelled(wasDeleting)
  }
  function message(code) {
    if (code === "personal_section_not_empty") return "This section still has links. Delete or move them in Rock before deleting the section."
    if (code === "personal_delete_not_owned") return "Only your own private links and sections can be deleted here."
    if (code === "personal_delete_target_invalid" || code === "personal_delete_target_missing") return "This item is no longer available. Cancel and refresh Links."
    if (code === "personal_delete_target_changed") return "This item changed. Reload to review it before deleting."
    if (code === "personal_delete_uncertain") return "Rock may have deleted this item. Check Links before trying again."
    if (code === "personal_delete_rejected") return "Rock rejected the deletion. Cancel and refresh Links."
    if (code === "personal_link_name_invalid") return "Enter a name of 1–100 characters."
    if (code === "personal_link_url_invalid") return "Use an HTTPS URL on this Rock instance, or a path such as /page/42."
    if (code === "personal_link_draft_expired") return deleting ? "This confirmation has expired. Reload before deleting." : "This form has expired. Reload before saving."
    if (code === "personal_link_account_changed") return "The Rock account changed. Reopen this action to continue."
    if (code === "personal_link_section_changed") return "That personal section changed. Reload and choose a section."
    if (code === "personal_link_save_uncertain") return "Rock may have saved this " + kind + ". Check Links before trying again."
    if (code === "personal_section_limit") return "This account has reached Rock Arch's limit of 100 personal sections."
    if (code === "personal_links_not_authorized") return "Rock doesn't permit this action for your account. Your Rock administrator can review Personal Links API access."
    if (code === "personal_links_preview_only") return "Saving Personal Links is unavailable in Preview."
    if (code === "personal_link_source_invalid") return "That search result has expired. Search again and choose Save."
    if (code === "personal_link_rejected") return kind === "section" ? "Rock rejected the section. Check its name." : "Rock rejected the link. Check its name, URL, and section."
    if (code === "rock_login_required" || code === "rock_login_failed") return "Sign in to Rock again, then reopen this action."
    return deleting ? "Rock Arch couldn't check or delete this item. Reload to try again." : "Rock Arch couldn't load or save this " + kind + ". Reload to try again."
  }
}
