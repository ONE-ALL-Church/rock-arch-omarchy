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

  property RockArchConnection connection: RockArchConnection {
    transport: brokerSocket
    onInterrupted: broker.interrupted()
  }

  property Process process: Process {
    command: ["/usr/bin/python3", "-m", "rock_arch_broker"]
    workingDirectory: broker.packageRoot
    running: true
    onStarted: broker.connection.retry()
  }

  property Socket socket: Socket {
    id: brokerSocket
    path: broker.socketPath
    connected: false
    onError: {
      connected = false
      broker.connection.failed()
    }
    parser: SplitParser { onRead: function(line) { broker.received(line) } }
  }
}
