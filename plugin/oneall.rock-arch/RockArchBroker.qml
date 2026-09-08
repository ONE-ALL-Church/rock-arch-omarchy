import QtQml
import Quickshell.Io

// Quickshell owns the child process and socket for this plugin instance.
QtObject {
  id: broker
  required property string packageRoot
  required property string socketPath
  signal received(string line)
  signal interrupted()

  function request(payload) { connection.request(payload) }
  function dropCredentials() { connection.dropCredentials() }
  function dropPersonalLinkRequests() { connection.dropPersonalLinkRequests() }
  function dropJobRequests() { connection.dropJobRequests() }

  property RockArchConnection connection: RockArchConnection {
    transport: broker.socket
    onInterrupted: broker.interrupted()
  }

  property Process process: Process {
    command: ["/usr/bin/python3", "-B", "-m", "rock_arch_broker"]
    workingDirectory: broker.packageRoot
    running: true
    onStarted: broker.connection.retry()
  }

  // Quickshell 0.3 retains a failed pre-connect QLocalSocket. Toggling its
  // connected flag cannot revive it; replace that socket after an error.
  property Socket socket: null
  function replaceSocket() {
    var previous = socket
    socket = socketFactory.createObject(broker)
    if (previous) { previous.connected = false; previous.destroy() }
  }
  Component.onCompleted: replaceSocket()

  property Component socketFactory: Component {
    Socket {
      id: socket
      path: broker.socketPath
      connected: false
      onConnectionStateChanged: {
        if (connected) broker.connection.flushRequests()
        else broker.connection.retry()
      }
      onError: Qt.callLater(function() {
        if (broker.socket !== socket) return
        broker.replaceSocket()
        broker.connection.failed()
      })
      parser: SplitParser { onRead: function(line) { broker.received(line) } }
    }
  }
}
