import assert from 'node:assert/strict';
import {SpeechMotion} from './speech-motion.mjs';
const v={visemes:['aa','PP','O','FF'],times:[0,250,500,750],durations:[250,250,250,250]};
const levels=[...Array(10).fill(0),...Array(25).fill(.9),...Array(15).fill(0),...Array(25).fill(.9),...Array(10).fill(0)];
const m=new SpeechMotion();m.set({id:'one',position_ms:0,duration:1.7,envelope:{step_ms:20,levels}},v,0);
const rows=[];
for(let t=0;t<2000;t+=1000/60){const f=m.sample(t,true,1000/60);rows.push({t,...f});assert(Object.values(f.weights).every(x=>x>=0&&x<=.62));}
const peak=f=>Math.max(0,...Object.values(f.weights));
assert(rows.filter(f=>f.t<150).every(f=>peak(f)===0),'Leading silence must stay closed');
assert(rows.some(f=>Object.values(f.weights).filter(x=>x>.025).length>1),'Adjacent shapes should overlap');
assert(rows.filter(f=>f.t>880&&f.t<960).every(f=>peak(f)<.02),'Real internal pause must close the mouth');
assert(peak(rows.at(-1))<.005,'Mouth must settle after audio ends');
// New speech IDs anchor independently, and stop closes promptly.
m.set({id:'two',position_ms:300,duration:1.7,envelope:{step_ms:20,levels}},v,3000);
assert.equal(m.sample(3000,true).elapsed,300);
for(let i=0;i<20;i++)m.sample(3000+i*16.67,false,16.67);
assert(Math.max(0,...Object.values(m.weights))<.005,'Stop must clear stale mouth motion');
console.log('PASS: waveform pauses, blended shapes, bounded amplitude, chunk clock and stop');
// Upstream timings are relative units, not milliseconds. Scaling units must
// preserve the animation rather than blend a whole sentence simultaneously.
const a=new SpeechMotion(),b=new SpeechMotion();
const speech={id:'scale',position_ms:0,duration:1.7,envelope:{step_ms:20,levels}};
a.set(speech,v,0);b.set(speech,{...v,times:v.times.map(x=>x/100),durations:v.durations.map(x=>x/100)},0);
for(let t=0;t<1700;t+=16.67){const x=a.sample(t,true),y=b.sample(t,true);for(const k of new Set([...Object.keys(x.weights),...Object.keys(y.weights)]))assert(Math.abs((x.weights[k]||0)-(y.weights[k]||0))<.00001);}
console.log('PASS: relative upstream viseme time units preserve the same animation');

// Streaming updates extend the same clock and keep moving after the first buffer.
const stream=new SpeechMotion();
stream.set({id:'stream',streaming:true,position_ms:0,duration:3,envelope:{step_ms:20,levels:Array(40).fill(.8)}},v,0);
stream.sample(600,true);
stream.set({id:'stream',streaming:true,position_ms:700,duration:3,envelope:{step_ms:20,levels:Array(120).fill(.8)}},v,700);
assert.equal(stream.sample(1800,true).elapsed,1800);
assert(Object.keys(stream.sample(1800,true).weights).length>0);
console.log('PASS: streaming updates retain clock and extend mouth animation');
