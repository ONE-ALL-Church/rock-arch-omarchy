import QtQml
import QtTest
import "../../plugin/oneall.rock-arch" as RockArch
import "../../plugin/oneall.rock-arch/RockArchAccountResponses.js" as Account

TestCase {
  name: "BrokerConnection"
  property var socket
  property var connection

  Component {
    id: socketFactory
    QtObject {
      property bool connected: false
      property var messages: []
      property int flushes: 0
      property bool disconnectAfterWrite: false
      function write(line) {
        messages = messages.concat([JSON.parse(line)])
        if (disconnectAfterWrite) connected = false
      }
      function flush() { flushes++ }
    }
  }
  Component {
    id: connectionFactory
    RockArch.RockArchConnection { retryInterval: 10000 }
  }

  function init() {
    socket = createTemporaryObject(socketFactory, this)
    connection = createTemporaryObject(connectionFactory, this, {transport: socket})
    verify(connection !== null)
  }

  function test_reconnect_delivers_latest_query_and_distinct_link_sections() {
    connection.request({op: "search", query: "old"})
    connection.request({op: "navigation_status", section: "personal"})
    connection.request({op: "navigation_status", section: "quick_returns"})
    connection.request({op: "search", query: "current"})
    connection.request({op: "navigation_status", section: "personal"})
    compare(socket.messages.length, 0)
    connection.retryInterval = 1
    connection.retry()
    tryCompare(socket, "connected", true)
    compare(socket.messages, [
      {op: "navigation_status", section: "quick_returns"},
      {op: "search", query: "current"},
      {op: "navigation_status", section: "personal"}
    ])
    compare(connection.requestQueue.length, 0)
  }

  function test_close_or_timeout_purges_all_queued_login_forms() {
    for (var op of ["rock_configure", "profile_add", "profile_credentials_update"])
      connection.request({op: op, username: "synthetic", password: "private-fixture"})
    connection.request({op: "status"})
    connection.dropCredentials()
    socket.connected = true
    compare(socket.messages, [{op: "status"}])
    verify(JSON.stringify(connection.requestQueue).indexOf("private-fixture") === -1)
  }

  function test_sent_mutations_and_credentials_are_never_replayed() {
    socket.connected = true
    connection.request({op: "rock_configure", password: "synthetic"})
    connection.request({op: "magnus_build", safeId: "opaque-app", confirmed: true})
    socket.connected = false
    connection.failed()
    socket.connected = true
    compare(socket.messages.length, 2)
    compare(connection.requestQueue.length, 0)
  }

  function test_interrupted_capability_probe_recovers_once() {
    var state = {
      searchCapabilitiesInFlight: true,
      searchCapabilitiesState: "checking",
      probeSearchCapabilities: function() {
        if (this.searchCapabilitiesInFlight) return
        this.searchCapabilitiesInFlight = true
        this.searchCapabilitiesState = "checking"
        connection.request({op: "search_capabilities"})
      }
    }
    connection.interrupted.connect(function() { Account.interrupted(state) })
    connection.failed()
    connection.failed()
    socket.connected = true
    compare(socket.messages, [{op: "search_capabilities"}])
    verify(state.searchCapabilitiesInFlight)
  }

  function test_partial_disconnect_keeps_only_unsent_requests() {
    connection.request({op: "status"})
    connection.request({op: "search", query: "pending"})
    socket.disconnectAfterWrite = true
    socket.connected = true
    compare(socket.messages, [{op: "status"}])
    compare(connection.requestQueue, [{op: "search", query: "pending"}])
  }
}
