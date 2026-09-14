import {test} from 'node:test';
import assert from 'node:assert/strict';
import {activityText,bubbleKind,modelBadge} from './bubbles.mjs';

test('thought bubbles explain activity without publishing reasoning or arguments',()=>{
 const state={busy:true,phase:'Thinking carefully',deliberate:true,active_model:'qwen3.8:27b-jinx',thinking:'private trace',tool_activity:{name:'jinx_web_read',arguments:'private URL'}};
 assert.equal(activityText(state),'Reading a webpage');
 assert.equal(modelBadge(state,'thought'),'Qwen 3.8 27B · careful');
 assert.equal(bubbleKind(state,'status','Reading'),'thought');
 delete state.tool_activity;
 assert.equal(activityText(state),'Thinking this through');
});
test('speech, listening and idle states have the correct bubble kind',()=>{
 assert.equal(bubbleKind({busy:true},'speech','Hello'),'speech');
 assert.equal(modelBadge({},'speech'),'Jinx');
 assert.equal(bubbleKind({busy:true,ptt:true,phase:'Listening — speak now'},'status','Listening'),'status');
 assert.equal(bubbleKind({},'status',''),'hidden');
 assert.equal(modelBadge({active_model:'qwen3.5:4b'},'thought'),'Qwen 3.5 4B · quick');
});
