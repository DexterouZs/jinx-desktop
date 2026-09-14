import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Effects
import QtWebEngine
Window {
 id: root; width: 532; height: 668; visible: false; color: "transparent"
 flags: Qt.FramelessWindowHint | Qt.Tool
 title: "Jinx"
 property bool editing: false
 property bool pageLoaded: false
 property int loadFailures: 0
 property var web: avatarLoader.item
 function publishLayout() {
  const value=nativeControls.layout();editing=value.unlocked;
  if(web)web.runJavaScript("window.setNativeLayout && window.setNativeLayout("+JSON.stringify(value)+")");
 }
 Connections { target: nativeControls; function onLayoutChanged() { layoutUpdate.restart(); } }
 Timer { id: layoutUpdate; interval: 16; onTriggered: root.publishLayout() }
 Loader {
  id: avatarLoader; anchors.fill: parent; active: !nativeControls.sleeping
  onActiveChanged: { root.pageLoaded=false; root.loadFailures=0; if(active)reloadTimer.restart();else reloadTimer.stop() }
  sourceComponent: Component { WebEngineView {
   anchors.fill: parent; backgroundColor: "transparent"
   settings.errorPageEnabled: false
   url: "http://127.0.0.1:17341/avatar/index.html"
   settings.playbackRequiresUserGesture: false
   onPermissionRequested: function(request) { request.deny() }
   onNewWindowRequested: function(request) { }
   onNavigationRequested: function(request) {
    if (!request.url.toString().startsWith("http://127.0.0.1:17341/avatar/")) request.reject()
   }
   onJavaScriptConsoleMessage: function(level, message, lineNumber, sourceID) { console.log("Jinx3D:", message) }
   onLoadingChanged: function(info) {
    if(info.status===WebEngineView.LoadStartedStatus) root.pageLoaded=false
    else if(info.status===WebEngineView.LoadFailedStatus) {
     root.pageLoaded=false; root.loadFailures++; reloadTimer.restart()
    } else if(info.status===WebEngineView.LoadSucceededStatus) {
     root.pageLoaded=true; root.loadFailures=0; reloadTimer.stop(); initialLayout.restart()
    }
   }
   onRenderProcessTerminated: { root.pageLoaded=false; root.loadFailures++; reloadTimer.restart() }
  } }
 }
 Row {
  anchors.right: parent.right; anchors.rightMargin: 70
  anchors.bottom: parent.bottom; anchors.bottomMargin: 55
  spacing: 7
  visible: !nativeControls.sleeping && !root.pageLoaded
  BusyIndicator { width: 22; height: 22; running: parent.visible && root.loadFailures<5 }
  Button {
   text: root.loadFailures<5 ? "Waking Jinx…" : "Retry Jinx"
   enabled: root.loadFailures>=5
   background: Rectangle { color: "#99121924"; radius: 12 }
   contentItem: Text { text: parent.text; color: "#d5dce5"; font.pixelSize: 12 }
   onClicked: { root.loadFailures=0; nativeControls.startBackend(); reloadTimer.restart() }
  }
 }
 Button {
  id: sleepSkill; width: 46; height: 46
  anchors.right: parent.right; anchors.rightMargin: 14; anchors.bottom: parent.bottom; anchors.bottomMargin: 46
  padding: 5; enabled: !nativeControls.sleepPending
  Accessible.name: nativeControls.sleeping ? "Wake Jinx" : "Put Jinx to sleep"
  ToolTip.visible: hovered; ToolTip.text: nativeControls.sleeping ? "Wake Jinx" : "Sleep · release AI and avatar resources"
  background: Rectangle { radius: 23; color: sleepSkill.hovered ? "#283c57" : "#db152133"; border.width: 2; border.color: nativeControls.sleeping ? "#98a5b8" : "#76e1e8" }
  contentItem: Item {
   Image {
    id: skillPicture; anchors.fill: parent; visible: false
    source: nativeControls.sleeping ? "icons/wake-jinx.jpg" : "icons/sleep-skull.jpg"
    sourceSize: nativeControls.sleeping ? Qt.size(237, 237) : Qt.size(216, 384)
    sourceClipRect: nativeControls.sleeping ? Qt.rect(54, 5, 150, 150) : Qt.rect(0, 96, 216, 216)
    fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
   }
   Rectangle { id: skillMask; anchors.fill: parent; radius: width/2; visible: false; layer.enabled: true; color: "white" }
   MultiEffect { anchors.fill: parent; source: skillPicture; maskEnabled: true; maskSource: skillMask; autoPaddingEnabled: false }
  }
  onClicked: nativeControls.toggleSleep()
 }
 Timer { id: initialLayout; interval: 500; onTriggered: root.publishLayout() }
 Timer { id: reloadTimer; interval: root.loadFailures<5 ? 2000 : 10000; onTriggered: { if(web && !nativeControls.sleeping)web.url="http://127.0.0.1:17341/avatar/index.html?retry="+Date.now() } }
 Timer {
  interval: root.editing ? 16 : 250; repeat: true; running: !nativeControls.sleeping
  onTriggered: {
   if(!web)return;
   web.runJavaScript("({action:window.consumeNativeAction ? window.consumeNativeAction() : '', active:window.jinxInteractionActive ? window.jinxInteractionActive() : false})", function(result){
    nativeControls.setInteractionActive(!!(result && result.active));
    const action=result ? result.action : null;
    if(action==="layout")root.publishLayout()
    else if(action==="settings")nativeControls.openSettings()
    else if(action==="start")nativeControls.startBackend()
    else if(action==="sleep")nativeControls.toggleSleep()
    else if(action && action.kind==="unlock")nativeControls.setUnlocked(action.value)
    else if(action && action.kind==="scale")nativeControls.setScale(action.value,action.persist)
    else if(action && action.kind==="move")nativeControls.moveAvatar(action.dx,action.dy,action.id,action.finished)
    else if(action && action.kind==="reset")nativeControls.resetLayout()
   })
  }
 }
}
