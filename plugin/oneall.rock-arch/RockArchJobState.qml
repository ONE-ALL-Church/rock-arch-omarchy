import QtQml

QtObject {
  id: state
  property bool available: false
  property bool accessBusy: false
  property string accessRequestId: ""
  property int revision: 0
  property bool editing: false
  property bool busy: false
  property string phase: ""
  property string safeId: ""
  property string title: ""
  property string draftId: ""
  property string requestId: ""
  property string notice: ""
  property string lastStatus: ""
  property string lastRunAt: ""
  readonly property bool canRun: editing && !busy && phase === "confirm" && draftId !== ""
  signal requested(var payload)
  signal confirmationReady()
  signal dismissed()

  function refreshAccess() {
    if (accessBusy) return
    accessRequestId = "job-access-" + (++revision)
    accessBusy = true
    requested({op: "job_access", requestId: accessRequestId})
  }
  function acceptAccess(value) {
    if (!accessBusy || !value || value.requestId !== accessRequestId) return
    accessBusy = false
    available = value.available === true && value.state === "ready"
  }
  function send(payload) {
    requestId = "job-action-" + (++revision)
    payload.requestId = requestId
    busy = true
    timeout.restart()
    requested(payload)
  }
  function begin(result) {
    if (!available || editing || !result || result.category !== "Jobs") return
    editing = true
    safeId = String(result.safeId)
    title = String(result.title)
    phase = "preparing"
    notice = "Checking access…"
    send({op: "job_prepare", safeId: safeId})
  }
  function run() {
    if (!canRun) return
    var token = draftId
    draftId = ""
    phase = "sending"
    notice = "Requesting run…"
    send({op: "job_run", draftId: token, confirmed: true})
  }
  function checkStatus() {
    if (!editing || busy || (phase !== "requested" && phase !== "uncertain")) return
    send({op: "job_status", safeId: safeId})
  }
  function accept(value) {
    if (!editing || !busy || !value || value.requestId !== requestId) return
    timeout.stop()
    busy = false
    if (value.error) {
      var wasSending = phase === "sending"
      draftId = ""
      phase = value.error === "job_run_uncertain" ? "uncertain" : "error"
      notice = phase === "uncertain" ? "Rock may have started this job. Check its status before trying again."
        : value.error === "job_run_rejected" ? "Rock rejected the run request."
        : value.error === "job_not_found" ? "This job is no longer available. Search again."
        : "Job access or configuration changed. Close and try again."
      if (wasSending || value.error.indexOf("access") >= 0) available = false
      return
    }
    if (value.state === "confirm" && value.draftId && phase === "preparing") {
      draftId = String(value.draftId)
      title = String(value.title || title)
      phase = "confirm"
      notice = "Run this job now with its current Rock settings?"
      confirmationReady()
    } else if (value.state === "requested" && phase === "sending") {
      phase = "requested"
      notice = "Run requested. This does not confirm completion."
      statusDelay.restart()
      confirmationReady()
    } else if (value.state === "status" && (phase === "requested" || phase === "uncertain")) {
      lastStatus = String(value.lastStatus || "Not recorded")
      lastRunAt = String(value.lastRunAt || "")
    } else {
      interrupted()
    }
  }
  function interrupted() {
    available = false
    accessBusy = false
    accessRequestId = ""
    if (!editing) return
    timeout.stop()
    statusDelay.stop()
    requestId = ""
    busy = false
    draftId = ""
    if (phase === "sending" || phase === "requested" || phase === "uncertain") {
      phase = "uncertain"
      notice = "Rock may have started this job. Check its status before trying again."
    } else {
      phase = "error"
      notice = "The access check was interrupted. Close and try again."
    }
  }
  function close() {
    timeout.stop()
    statusDelay.stop()
    editing = false; busy = false; phase = ""; safeId = ""; title = ""
    draftId = ""; requestId = ""; notice = ""; lastStatus = ""; lastRunAt = ""
  }
  function cancel() { close(); dismissed() }
  function reset() {
    close()
    available = false; accessBusy = false; accessRequestId = ""
  }
  property Timer timeout: Timer { interval: 30000; onTriggered: state.interrupted() }
  property Timer statusDelay: Timer { interval: 1000; onTriggered: state.checkStatus() }
}
