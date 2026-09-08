import QtQml
QtObject {
 required property string packageRoot
 required property string socketPath
 signal received(string line)
 signal interrupted()
 function request(payload) {}
 function dropCredentials() {}
 function dropPersonalLinkRequests() {}
 function dropJobRequests() {}
}
