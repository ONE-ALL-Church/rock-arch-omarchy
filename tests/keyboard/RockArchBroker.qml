import QtQml
QtObject {
 required property string packageRoot
 required property string socketPath
 signal received(string line)
 signal interrupted()
 property var requests: []
 function request(payload) { requests = requests.concat([payload]) }
 function dropCredentials() {}
 function dropPersonalLinkRequests() {}
 function dropJobRequests() {}
}
