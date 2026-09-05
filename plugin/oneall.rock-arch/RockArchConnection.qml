import QtQml

// Transport-independent queue, exercised by Qt Quick Test with a fake socket.
QtObject {
  id: connection
  required property var transport
  property var requestQueue: []
  property int retryInterval: 150
  signal interrupted()

  function request(payload) {
    var next = []
    var coalesce = payload.op === "search" || payload.op === "knowledge_search" ||
      payload.op === "search_capabilities" || payload.op === "status" || payload.op === "navigation_status"
    for (var index = 0; index < requestQueue.length; index++) {
      var queued = requestQueue[index]
      var sameNavigationSection = payload.op !== "navigation_status" || queued.section === payload.section
      if (!coalesce || queued.op !== payload.op || !sameNavigationSection) next.push(queued)
    }
    requestQueue = next.concat([payload])
    if (transport.connected) flushRequests()
    else retry()
  }

  function dropCredentials() {
    requestQueue = requestQueue.filter(function(payload) {
      return payload.op !== "rock_configure" && payload.op !== "profile_add" &&
        payload.op !== "profile_credentials_update"
    })
  }

  function flushRequests() {
    if (!transport.connected || !requestQueue.length) return
    while (transport.connected && requestQueue.length) {
      var payload = requestQueue[0]
      requestQueue = requestQueue.slice(1)
      transport.write(JSON.stringify(payload) + "\n")
    }
    transport.flush()
  }

  function retry() {
    if (requestQueue.length) reconnectTimer.restart()
  }

  function failed() {
    interrupted()
    retry()
  }

  property Connections transportSignals: Connections {
    target: connection.transport
    function onConnectedChanged() {
      if (connection.transport.connected) connection.flushRequests()
      else connection.retry()
    }
  }

  property Timer reconnectTimer: Timer {
    interval: connection.retryInterval
    onTriggered: {
      if (!connection.requestQueue.length) return
      if (connection.transport.connected) connection.flushRequests()
      else {
        connection.transport.connected = false
        connection.transport.connected = true
      }
    }
  }
}
