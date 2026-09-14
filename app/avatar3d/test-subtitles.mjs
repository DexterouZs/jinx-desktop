import assert from 'node:assert/strict';
import {makeCues,Subtitles} from './subtitles.mjs';
const text='The kernel is 7.2.3-1-cachyos-deckify, with 3.5Gi available and no failed system services. The graphics processor has 16GB of memory.';
for(const width of [120,210,420]){
 const cues=makeCues(text,width,x=>x.length*8);
 assert(cues.length>=2);
 assert.equal(cues.map(x=>x.text).join('').replace(/\s/g,''),text.replace(/\s/g,''));
 for(const cue of cues){assert(cue.text.split('\n').length<=2);assert(cue.text.split('\n').every(x=>x.length*8<=width));assert(cue.end>cue.start);}
 assert.equal(cues[0].start,0);assert.equal(cues.at(-1).end,1);
}
const track=new Subtitles(),speech={id:'test',text,position_ms:0,duration:6,envelope:{step_ms:20,levels:[...Array(20).fill(0),...Array(100).fill(.8),...Array(30).fill(0),...Array(150).fill(.8)]}};
const orphan=makeCues('one two three four five six seven eight nine ten.',20,x=>x.length);
assert.equal(orphan.length,2);assert.equal(orphan.at(-1).text.split('\n').length,2);
track.set(speech,210,x=>x.length*8,0);
const first=track.sample(0);assert(first);assert.equal(track.sample(200),first);
assert.notEqual(track.sample(5000),first);assert.equal(track.sample(6100),track.cues.at(-1).text);
assert(track.sample(6200,false));assert.equal(track.sample(7300,false),'');
track.set({...speech,id:'new',position_ms:2000},210,x=>x.length*8,10000);assert.equal(track.anchor,8000);
track.clear();assert.equal(track.sample(10001),'');
console.log('PASS: complete text, two measured lines, narrow widths, waveform clock, chunk replacement and expiry');
