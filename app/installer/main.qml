import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
Window {
 id: root; visible: false; color: "transparent"; title: "Jinx · Software installation"
 flags: Qt.FramelessWindowHint | Qt.Tool
 Rectangle {
  anchors.fill: parent; radius: 24; color: "#f019202d"; border.width: 1; border.color: "#586577"
  ColumnLayout {
   anchors.fill: parent; anchors.margins: 25; spacing: 16
   Label { text: "JINX  /  SOFTWARE"; color: "#91a2bb"; font.pixelSize: 12 }
   Label { text: installer.title; color: "#f2f5fa"; font.pixelSize: 27; Layout.fillWidth: true; wrapMode: Text.Wrap }
   ScrollView {
    Layout.fillWidth: true; Layout.fillHeight: true; clip: true
    TextArea { readOnly: true; text: installer.review; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: "#d9e0ed"; font.pixelSize: 14; selectByMouse: true; background: Rectangle { color: "transparent" } }
   }
   Label { text: installer.message; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#bac7dc"; font.pixelSize: 14 }
   RowLayout {
    Layout.alignment: Qt.AlignRight; spacing: 12
    Button { text: installer.finished ? "Close" : "Not now"; onClicked: installer.close() }
    Button { text: "Cancel install"; visible: installer.actionable; onClicked: installer.cancel() }
    Button { text: "Install"; highlighted: true; visible: installer.actionable; onClicked: installer.install() }
   }
  }
 }
}
