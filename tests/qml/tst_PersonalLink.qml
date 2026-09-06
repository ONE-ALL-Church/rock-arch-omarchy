import QtQml
import QtTest
import "../../plugin/oneall.rock-arch" as RockArch

TestCase {
  name: "PersonalLink"
  property var model
  property var requests
  property int saves: 0
  Component { id: factory; RockArch.RockArchPersonalLinkState {} }
  function init() {
    requests = []; saves = 0
    model = createTemporaryObject(factory, this)
    verify(model !== null)
    model.requested.connect(function(payload) { requests.push(payload) })
    model.saved.connect(function() { saves++ })
  }
  function ready() {
    model.accept({requestId: model.requestId, draftId: "draft", name: "Directory",
      url: "https://rock.example.org/page/42", sectionId: "section", sections: [{safeId: "section", name: "Work"}]})
  }
  function test_delete_reviews_exact_target_then_sends_only_confirmed_draft() {
    var result = null
    model.deleted.connect(function(kind, groupId) { result = {kind: kind, groupId: groupId} })
    model.beginDelete("link", "opaque-delete")
    compare(requests[0].op, "personal_delete_prepare")
    compare(requests[0].targetId, "opaque-delete")
    verify(!model.canSave)
    model.accept({requestId: model.requestId, draftId: "draft", name: "Page", section: "Work", url: "https://rock.example.org/page/42", sections: []})
    verify(model.deleting)
    verify(model.canSave)
    compare(model.sectionName, "Work")
    compare(requests.length, 1)
    model.save()
    compare(requests[1], {op: "personal_delete_commit", draftId: "draft", confirmed: true, requestId: model.requestId})
    model.save()
    compare(requests.length, 2)
    model.accept({requestId: model.requestId, deleted: true, groupId: "work"})
    compare(result, {kind: "link", groupId: "work"})
    verify(!model.editing)
    compare(model.deleteTarget, "")
  }
  function test_delete_cancellation_and_interruption_never_repeat_mutation() {
    model.beginDelete("section", "opaque-section")
    model.cancel()
    compare(requests.length, 1)
    model.beginDelete("section", "opaque-section")
    model.accept({requestId: model.requestId, draftId: "draft", name: "Work", sections: []})
    model.save()
    model.interrupted()
    verify(model.notice.indexOf("may have deleted") >= 0)
    model.save()
    compare(requests.length, 3)
    model.reload()
    compare(requests[3].op, "personal_delete_prepare")
    compare(requests[3].targetId, "opaque-section")
    model.accept({requestId: model.requestId, error: "personal_section_not_empty"})
    verify(!model.canSave)
    verify(model.notice.indexOf("still has links") >= 0)
  }
  function test_begin_prefills_source_without_saving() {
    model.begin("rock-result")
    compare(requests[0].op, "personal_link_prepare")
    compare(requests[0].safeId, "rock-result")
    verify(model.busy)
    verify(!model.canSave)
    ready()
    verify(model.canSave)
    compare(model.name, "Directory")
    compare(requests.length, 1)
  }
  function test_section_form_only_needs_name_and_emits_section_result() {
    var result = null
    model.savedSection.connect(function(duplicate, name, groupId) { result = {duplicate: duplicate, name: name, groupId: groupId} })
    model.beginSection()
    compare(requests[0].op, "personal_section_prepare")
    model.accept({requestId: model.requestId, draftId: "section-draft", name: "", kind: "section", sections: []})
    verify(!model.canSave)
    model.name = "  Projects  "
    verify(model.canSave)
    model.save()
    compare(requests[1].op, "personal_section_save")
    compare(requests[1].name, "Projects")
    compare(requests[1].url, undefined)
    compare(requests[1].sectionId, undefined)
    model.accept({requestId: model.requestId, saved: true, alreadySaved: false, name: "Projects", groupId: "empty"})
    compare(result, {duplicate: false, name: "Projects", groupId: "empty"})
    compare(saves, 0)
    verify(!model.editing)
  }
  function test_empty_section_action_prefills_target_and_expired_target_falls_back() {
    model.begin("", "target")
    model.accept({requestId: model.requestId, draftId: "draft", name: "", url: "", sectionId: "default",
      sections: [{safeId: "default", name: "Work"}, {safeId: "target", name: "Projects"}]})
    compare(model.sectionId, "target")
    model.begin("", "removed")
    ready()
    compare(model.sectionId, "section")
  }
  function test_section_interruption_keeps_name_and_requires_explicit_reload() {
    model.beginSection()
    model.accept({requestId: model.requestId, draftId: "draft", name: "Projects", sections: []})
    model.save()
    model.interrupted()
    verify(model.notice.indexOf("saved this section") >= 0)
    model.save()
    compare(requests.length, 2)
    model.reload()
    compare(requests[2].op, "personal_section_prepare")
    compare(requests[2].name, "Projects")
  }
  function test_save_requires_ready_valid_fields_and_ignores_double_clicks() {
    model.begin("")
    model.save()
    compare(requests.length, 1)
    ready()
    model.name = " "
    model.save()
    compare(requests.length, 1)
    model.name = "Directory"
    model.save()
    compare(requests[1].op, "personal_link_save")
    verify(requests[1].confirmed)
    compare(requests[1].draftId, "draft")
    model.save()
    compare(requests.length, 2)
    model.accept({requestId: model.requestId, saved: true})
    verify(!model.editing)
    compare(saves, 1)
  }
  function test_stale_response_cannot_restore_cancelled_or_replaced_form() {
    model.begin("rock-first")
    var previous = model.requestId
    model.cancel()
    model.accept({requestId: previous, draftId: "old", sections: []})
    verify(!model.editing)
    model.begin("rock-second")
    model.accept({requestId: previous, draftId: "old", sections: []})
    verify(model.busy)
    compare(model.draftId, "")
  }
  function test_interruption_never_replays_save_and_displays_uncertain_outcome() {
    model.begin(""); ready(); model.save()
    var previous = model.requestId
    model.interrupted()
    verify(!model.canSave)
    verify(model.notice.indexOf("may have saved") >= 0)
    model.save()
    compare(requests.length, 2)
    model.accept({requestId: previous, saved: true})
    compare(saves, 0)
    model.reload()
    compare(requests[2].op, "personal_link_prepare")
    compare(requests[2].url, "https://rock.example.org/page/42")
  }
  function test_save_error_preserves_inputs_but_requires_new_draft() {
    model.begin(""); ready(); model.save()
    model.accept({requestId: model.requestId, error: "personal_link_section_changed"})
    compare(model.name, "Directory")
    compare(model.draftId, "")
    verify(!model.canSave)
    verify(model.notice.indexOf("choose a section") >= 0)
  }
  function test_closing_discards_private_fields_and_pending_response() {
    model.begin(""); ready()
    model.closed()
    compare(model.name, "")
    compare(model.url, "")
    compare(model.sections, [])
    compare(model.requestId, "")
  }
}
