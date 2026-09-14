import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {DEFAULTS,RenderGate,pollDelay,ringDelay,ladderOptions} from './idle-loop.mjs';
const base={ready:true,hidden:false,paused:false,suspended:false,busy:false,ptt:false,
            conversation:false,speaking:false,subtitles:false,interactionAt:null};
const g=new RenderGate();
for(const now of [0,30000,180000,3600000,86400000]){
 const d=g.evaluate(base,now);
 assert.equal(d.running,true);assert.equal(d.fps,30);assert.equal(d.reason,'idle');
}
for(const flag of ['busy','ptt','conversation','speaking','subtitles','interactionAt']){
 const d=g.evaluate({...base,[flag]:flag==='interactionAt'?100:true},100);
 assert.equal(d.running,true);assert.equal(d.fps,30);assert.equal(d.reason,'active');
}
for(const [flag,value,reason] of [['ready',false,'not-ready'],['hidden',true,'hidden'],['paused',true,'paused'],['suspended',true,'suspended']]){
 for(const busy of [false,true]){
  const d=g.evaluate({...base,busy,[flag]:value},100);
  assert.equal(d.running,false);assert.equal(d.reason,reason);assert.equal(d.fps,null);
  assert.equal(g.evaluate(base,101).running,true);
 }
}
assert.deepEqual(ladderOptions(),DEFAULTS);
assert.deepEqual(ladderOptions({restFPS:6,restAfter:30000,sleepAfter:180000}),DEFAULTS);
assert.deepEqual(ladderOptions({activeFPS:Infinity,idleFPS:NaN}),DEFAULTS);
assert.equal(ladderOptions({idleFPS:4}).fps.idle,30);
assert.equal(ladderOptions({activeFPS:120}).fps.active,60);
assert.equal(new RenderGate({fps:{idle:6}}).evaluate(base).fps,30);
assert.equal(pollDelay({hidden:true}),4000);assert.equal(pollDelay({busy:true}),90);
assert.equal(pollDelay({ptt:true}),90);assert.equal(pollDelay(),900);
assert.equal(ringDelay({drawing:false}),null);assert.equal(ringDelay({drawing:true}),250);
assert.equal(ringDelay({drawing:true,busy:true}),33);
// The real adapter must stop while hidden and restart once, without creating
// burst timers or restarting an empty status ring on every status response.
const source=readFileSync(new URL('./avatar.mjs',import.meta.url),'utf8');
const adapter=source.slice(source.indexOf('function applyGate(){'),source.indexOf('function noteInteraction(){'));
let starts=0,stops=0;const signals={...base};
const ctx=vm.createContext({gate:new RenderGate(),head:{start(){starts++},stop(){stops++}},
 performance:{now:()=>3600000},gateSignals:()=>signals,loopActive:true,
 ringDrawing:()=>false,startRing(){throw Error('empty ring restarted')}});
vm.runInContext(adapter,ctx);ctx.applyGate();ctx.applyGate();
assert.equal(starts,0);assert.equal(stops,0);assert.ok(ctx.head.animFrameDur<1000/30);
signals.hidden=true;ctx.applyGate();ctx.applyGate();assert.equal(stops,1);
signals.hidden=false;ctx.applyGate();ctx.applyGate();assert.equal(starts,1);
console.log('PASS: continuous minimum30fps, legacy settings, hidden/pause stops, wake, polling and real adapter');
