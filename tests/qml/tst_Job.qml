import QtQml
import QtTest
import "../../plugin/oneall.rock-arch" as RockArch

TestCase {
  name: "Job"
  property var model
  property var requests
  Component { id: factory; RockArch.RockArchJobState {} }
  function init() {
    requests = []
    model = createTemporaryObject(factory, this)
    verify(model !== null)
    model.requested.connect(function(payload) { requests.push(payload) })
  }
  function access(allowed) {
    model.refreshAccess()
    model.acceptAccess({requestId: model.accessRequestId, available: allowed, state: allowed ? "ready" : "unavailable"})
  }
  function prepare() {
    access(true)
    model.begin({safeId: "job-result", title: "Test job", category: "Jobs"})
    model.accept({requestId: model.requestId, state: "confirm", draftId: "draft", title: "Test job"})
  }
  function test_access_is_required_and_stale_permission_response_is_ignored() {
    model.begin({safeId: "job-result", category: "Jobs"})
    compare(requests.length, 0)
    model.refreshAccess()
    var id = model.accessRequestId
    model.reset()
    model.acceptAccess({requestId: id, available: true, state: "ready"})
    verify(!model.available)
    access(false)
    verify(!model.available)
  }
  function test_confirmation_and_double_click_cannot_submit_twice() {
    prepare()
    verify(model.canRun)
    compare(requests.length, 2)
    model.run()
    compare(requests[2].op, "job_run")
    verify(requests[2].confirmed)
    compare(requests[2].draftId, "draft")
    model.run()
    compare(requests.length, 3)
    model.accept({requestId: model.requestId, state: "requested"})
    compare(model.phase, "requested")
    verify(!model.canRun)
    verify(model.notice.indexOf("does not confirm completion") >= 0)
  }
  function test_history_failure_does_not_allow_rerunning_accepted_job() {
    prepare()
    model.run()
    model.accept({requestId: model.requestId, state: "requested", recentLinkSaved: false})
    compare(model.phase, "requested")
    verify(!model.canRun)
    verify(model.notice.indexOf("Recent link couldn't be saved") >= 0)
    model.run()
    compare(requests.length, 3)
  }

  function test_cancel_and_profile_reset_invalidate_late_responses() {
    access(true)
    model.begin({safeId: "job-result", title: "Test job", category: "Jobs"})
    var id = model.requestId
    model.cancel()
    model.accept({requestId: id, state: "confirm", draftId: "old"})
    verify(!model.editing)
    verify(!model.canRun)
    prepare()
    model.reset()
    verify(!model.available)
    verify(!model.canRun)
  }
  function test_interrupted_send_is_uncertain_and_never_repeated() {
    prepare(); model.run()
    var id = model.requestId
    model.interrupted()
    compare(model.phase, "uncertain")
    verify(!model.available)
    model.run()
    compare(requests.length, 3)
    model.accept({requestId: id, state: "requested"})
    compare(model.phase, "uncertain")
    model.checkStatus()
    compare(requests[3].op, "job_status")
    model.accept({requestId: model.requestId, state: "status", lastStatus: "Success", lastRunAt: "2026-09-01"})
    compare(model.phase, "uncertain")
    verify(model.notice.indexOf("may have started") >= 0)
  }
  function test_failed_confirmation_cannot_keep_a_usable_draft() {
    prepare(); model.run()
    model.accept({requestId: model.requestId, error: "job_access_changed"})
    verify(!model.canRun)
    verify(!model.available)
    compare(model.phase, "error")
    model.run()
    compare(requests.length, 3)
  }
}
