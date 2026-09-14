import QtQuick
import QtQuick.Window
Item {
 id: root
 opacity: attention.active ? 1 : 0
 Behavior on opacity { NumberAnimation { duration: 260 } }
 onOpacityChanged: if(opacity===0 && !attention.active && root.Window.window) root.Window.window.hide()
 Repeater {
  model: 4
  Canvas {
   width: 150; height: 150
   x: index%2 ? root.width-width : 0
   y: index>=2 ? root.height-height : 0
   rotation: index===0 ? 0 : index===1 ? 90 : index===2 ? 270 : 180
   onPaint: {
    const ctx=getContext("2d");ctx.clearRect(0,0,width,height);
    const wash=ctx.createRadialGradient(0,0,0,0,0,145);
    wash.addColorStop(0,"rgba(58,147,255,0.32)");wash.addColorStop(.4,"rgba(55,139,255,0.13)");wash.addColorStop(1,"rgba(45,125,250,0)");
    ctx.fillStyle=wash;ctx.fillRect(0,0,width,height);
    for(let spread=12;spread>=0;spread-=2){
     ctx.beginPath();ctx.moveTo(5,90);ctx.lineTo(5,25);ctx.quadraticCurveTo(5,5,25,5);ctx.lineTo(90,5);
     const line=ctx.createLinearGradient(0,0,90,90);line.addColorStop(0,"rgba(94,178,255,"+(spread===0?.72:.025)+")");line.addColorStop(1,"rgba(76,149,255,0)");
     ctx.strokeStyle=line;ctx.lineWidth=spread+1.5;ctx.lineCap="round";ctx.stroke();
    }
   }
  }
 }
}
