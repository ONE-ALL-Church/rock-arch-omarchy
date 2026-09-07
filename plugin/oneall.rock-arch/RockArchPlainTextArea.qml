import QtQuick
import QtQuick.Controls as QQC

// Remote file content must never be interpreted as markup or load resources.
QQC.TextArea {
  textFormat: TextEdit.PlainText
  readOnly: true
  selectByMouse: true
  wrapMode: TextEdit.NoWrap
}
