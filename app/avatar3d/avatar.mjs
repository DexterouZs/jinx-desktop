import * as THREE from 'three';
import {TalkingHead} from './vendor/talkinghead.mjs';
import {SpeechMotion} from './speech-motion.mjs';
import {activityText,bubbleKind,modelBadge} from './bubbles.mjs';
import {Subtitles} from './subtitles.mjs';
import {RenderGate,pollDelay,ringDelay,ladderOptions} from './idle-loop.mjs';
const subtitles=new Subtitles(),subtitleMeasure=document.createElement('canvas').getContext('2d');
const speechMotion=new SpeechMotion();
let silentSubtitleUntil=0,lastWrittenReply='';
let renderedFrames=0;
const $=id=>document.getElementById(id);
let nativeLayout={scale:1,unlocked:false},drag=null,dragSerial=0;
const gate=new RenderGate();
let pendingIds=new Set();
let hidden=document.hidden,interactionAt=null,paused=false,ringRunning=false;
let state={},online=false,head=null,ready=false,nativeAction='',activation=false,error='',lastPhase='',speechId='',visemes=null,speech=null,captionUntil=0,lastGesture=0,previousViseme='sil',level=0,loopActive=true;
let statusReceivedAt=0;
window.jinxInteractionActive=()=>!!(online && performance.now()-statusReceivedAt<10000 && !state.suspended && (state.conversation||state.busy||state.ptt||state.phase==='Speaking'||state.filler_speaking));
window.consumeNativeAction=()=>{let a=nativeAction;nativeAction='';return a};
window.setNativeLayout=value=>{
 gate.o=ladderOptions(value.idleLoop);
 nativeLayout=value;document.body.classList.toggle('editing',!!value.unlocked);
 $('unlockAvatar').textContent=value.unlocked?'Lock position':'Unlock to move';
 $('moveHint').textContent=value.unlocked?'Drag Jinx herself, then lock her position.':'Unlock, then drag Jinx to move her.';
 if(document.activeElement.id!=='avatarSize')$('avatarSize').value=Math.round(value.scale*100);
 $('avatarSize').min=Math.ceil(value.minScale*100);$('avatarSize').max=Math.floor(value.maxScale*100);
 $('avatarSizeValue').value=Math.round(value.scale*100)+'%';
};
nativeAction='layout';
$('unlockAvatar').onclick=()=>{nativeAction={kind:'unlock',value:!nativeLayout.unlocked};$('menu').classList.remove('open')};
$('avatarSize').oninput=e=>{nativeAction={kind:'scale',value:Number(e.target.value)/100,persist:false};$('avatarSizeValue').value=e.target.value+'%'};
$('avatarSize').onchange=e=>{nativeAction={kind:'scale',value:Number(e.target.value)/100,persist:true}};
$('resetAvatar').onclick=()=>{nativeAction={kind:'reset'}};
$('avatarVoiceSpeed').oninput=e=>{$('avatarVoiceSpeedValue').value=Number(e.target.value).toFixed(2)+'×'};
$('avatarVoiceSpeed').onchange=e=>act('/settings',{voice_speed:Number(e.target.value)});
$('stage').onpointerdown=e=>{
 if(!nativeLayout.unlocked||e.button!==0)return;
 e.preventDefault();drag={id:String(++dragSerial),x:e.clientX,y:e.clientY};
 try{$('stage').setPointerCapture(e.pointerId)}catch(_){}
 $('menu').classList.remove('open');
};
$('stage').onpointermove=e=>{if(drag)nativeAction={kind:'move',id:drag.id,dx:e.clientX-drag.x,dy:e.clientY-drag.y,finished:false}};
function finishMove(e){if(drag){
 if(nativeAction && nativeAction.kind==='move' && nativeAction.id===drag.id)nativeAction.finished=true;
 else nativeAction={kind:'move',id:drag.id,dx:0,dy:0,finished:true};
 drag=null;
}}
$('stage').onpointerup=finishMove;$('stage').onpointercancel=finishMove;

async function api(path,body){let r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});let j=await r.json();if(!r.ok)throw Error(j.error||'Jinx is unavailable');return j}
async function act(path,body={}){try{await api(path,body);error=''}catch(e){error=e.message}}
function talk(){
 if(nativeLayout.unlocked)return;
 $('menu').classList.remove('open');error='';
 if(!online){nativeAction='start';activation=true;setTimeout(()=>{activation=false},12000);return}
 head?.audioCtx.resume();paused=false;noteInteraction();
 if(state.conversation||state.busy||state.ptt)act('/stop');else act('/conversation',{unmute:!!state.muted});
}
$('stage').onclick=talk;$('stage').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();talk()}};
$('stage').oncontextmenu=e=>{e.preventDefault();$('menu').classList.toggle('open')};
$('menuButton').onclick=()=>$('menu').classList.toggle('open');
$('closeMenu').onclick=()=>$('menu').classList.remove('open');
document.addEventListener('keydown',e=>{if(e.key==='Escape')$('menu').classList.remove('open')});
$('settingsButton').onclick=()=>{nativeAction='settings';$('menu').classList.remove('open')};
$('screenEnabled').onchange=e=>act('/settings',{screen_enabled:e.target.checked});
for(const [id,text] of [['lookScreen','Look at my screen and briefly describe what you see.'],['readScreen','Read this page aloud']])$(id).onclick=()=>{$('menu').classList.remove('open');act('/chat',{text,spoken:true})};
$('stopScreen').onclick=()=>act('/stop');
$('readClipboardButton').onclick=()=>{$('menu').classList.remove('open');act('/chat',{text:'Read my clipboard aloud',spoken:true})};
$('wake').onchange=e=>act('/settings',{listening:e.target.checked});$('thinkingSounds').onchange=e=>act('/settings',{thinking_sounds:e.target.checked});
$('voice').onchange=e=>act('/settings',{speak:e.target.checked});
$('modelChoice').onchange=e=>act('/settings',{ai_mode:e.target.value});

$('voiceChoice').onchange=e=>act('/settings',{voice:e.target.value});$('voicePreview').onclick=()=>act('/voice-preview');
$('typeButton').onclick=()=>{$('menu').classList.remove('open');$('compose').showModal();$('text').focus()};$('closeCompose').onclick=()=>$('compose').close();
$('send').onclick=()=>{let text=$('text').value.trim();if(text){act('/chat',{text,spoken:true});$('text').value='';$('compose').close()}};
let reviewed=null;
$('reviewButton').onclick=()=>{reviewed=(state.pending||[]).at(-1);if(!reviewed)return;$('fields').textContent=reviewed.fields.review||reviewed.kind.replaceAll('_',' ')+'\n\n'+Object.entries(reviewed.fields).map(([k,v])=>k+':\n'+v).join('\n\n');$('confirm').textContent=reviewed.kind==='software_install'?'Install':'Confirm';$('review').showModal()};
for(let [id,path] of [['confirm','/confirm'],['discard','/reject']])$(id).onclick=()=>{if(reviewed)act(path,{id:reviewed.id});$('review').close();reviewed=null};$('closeReview').onclick=()=>$('review').close();
function startSubtitles(value){
 const box=$('caption');box.dataset.kind='speech';
 const style=getComputedStyle(box);subtitleMeasure.font=style.font;
 const width=box.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight)-2;
 subtitles.set(value,Math.max(120,width),text=>subtitleMeasure.measureText(text).width);
}
function subtitlePlaying(){return !!state.speech&&(state.phase==='Speaking'||state.filler_speaking)||(!state.busy&&!state.ptt&&performance.now()<silentSubtitleUntil)}
window.addEventListener('resize',()=>{if(state.speech)startSubtitles({...state.speech,position_ms:performance.now()-speechMotion.anchor})});
function updateActivityInfo(){
 const box=$('caption'),kind=bubbleKind(state,box.dataset.kind,box.textContent);
 $('activityInfo').dataset.kind=kind;$('modelBadge').textContent=modelBadge(state,kind);
}
function renderSubtitles(){
 if(!online||error||state.error)return;
 const box=$('caption'),active=subtitlePlaying();
 if(active){box.dataset.kind='speech';box.textContent=subtitles.sample(performance.now(),true)}
 else if(!state.error&&!error&&!state.busy&&!state.ptt){
  const text=subtitles.sample(performance.now(),false);
  if(text){box.dataset.kind='speech';box.textContent=text}
 }
 updateActivityInfo();
}
function animateLips(dt=16.67){
 if(!ready)return;
 renderedFrames++;renderSubtitles();
 const active=!!state.speech&&(state.phase==='Speaking'||state.filler_speaking);
 const frame=speechMotion.sample(performance.now(),active,dt,level);
 // TalkingHead applies morphs after this callback. Use its realtime channel so
 // mood/idle updates cannot overwrite our mouth in the same frame.
 for(const v of head.visemeNames){
  const morph=head.mtAvatar['viseme_'+v];
  if(morph)Object.assign(morph,{realtime:frame.weights[v]||0,needsUpdate:true});
 }
}
function gateSignals(){
 return {ready,hidden,paused,suspended:!!state.suspended,busy:!!state.busy,ptt:!!state.ptt,
         conversation:!!state.conversation,
         speaking:state.phase==='Speaking'||!!state.filler_speaking,
         subtitles:subtitlePlaying(),interactionAt};
}
// Single place that turns the gate's decision into a real start/stop. Called
// from poll(), from discrete events, and on visibility changes.
function applyGate(){
 if(!head)return;
 const d=gate.evaluate(gateSignals(),performance.now());
 // Small tolerance prevents 60 Hz vsync from halving the requested rate.
 if(d.running)head.animFrameDur=1000/d.fps-.75;
 if(d.running&&!loopActive){head.start();loopActive=true}
 else if(!d.running&&loopActive){head.stop();loopActive=false}
 if(d.running&&ringDrawing())startRing();
 return d;
}
function noteInteraction(){interactionAt=performance.now();gate.wake(interactionAt);applyGate()}
// Poll and input events refresh activity; no separate idle animation timer.
document.addEventListener('visibilitychange',()=>{hidden=document.hidden;if(!hidden)gate.wake(performance.now());applyGate()});
for(const ev of ['pointerdown','pointermove','keydown','wheel'])
 window.addEventListener(ev,noteInteraction,{passive:true});

async function initialise(){
 try{
  head=new TalkingHead($('stage'),{cameraView:'upper',cameraDistance:-.25,cameraY:.37,cameraRotateEnable:false,cameraPanEnable:false,cameraZoomEnable:false,lipsyncModules:['en'],lipsyncLang:'en',modelFPS:30,modelPixelRatio:Math.min(devicePixelRatio,1.5)/devicePixelRatio,modelMovementFactor:.5,avatarIdleEyeContact:.65,avatarIdleHeadMove:.25,avatarSpeakingEyeContact:.85,avatarSpeakingHeadMove:.35,lightAmbientIntensity:.10,lightDirectIntensity:2.35,lightDirectColor:0xffeee0,lightSpotIntensity:0,lightSpotColor:0x65c8ff,avatarMood:'neutral',ttsEndpoint:null,update:animateLips});
  await head.showAvatar({url:'./avatars/jinx-character.glb',body:'F',avatarMood:'neutral',lipsyncLang:'en'});
  // RoomEnvironment otherwise lights every surface like a bright studio box.
  // Keep the painted skin and fabric detail, with a soft directional portrait setup.
  head.scene.environmentIntensity=.09;
  head.renderer.toneMappingExposure=1.0;
  head.lightDirect.position.set(-2.2,2.7,1.8);
  head.lightDirect.target.position.set(0,1.45,0);
  head.scene.add(head.lightDirect.target);
  const fill=new THREE.DirectionalLight(0xc5d9ff,.24);
  fill.position.set(1.8,1.8,1.5);fill.target.position.set(0,1.45,0);
  const rim=new THREE.DirectionalLight(0x83b7ff,1.45);
  rim.position.set(1.1,2.1,-1.6);rim.target.position.set(0,1.45,0);
  head.scene.add(fill,fill.target,rim,rim.target);
  // TalkingHead multiplies modelPixelRatio by devicePixelRatio itself.
  // A 1024px filtered shadow map keeps portrait self-shadowing without a 4MP pass.
  // Fill and rim remain shadow-free to keep animation responsive.
  head.renderer.shadowMap.enabled=true;
  head.renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  head.lightDirect.castShadow=true;
  head.lightDirect.shadow.mapSize.set(1024,1024);
  Object.assign(head.lightDirect.shadow.camera,{left:-1.2,right:1.2,top:1.2,bottom:-1.2,near:.1,far:7});
  head.lightDirect.shadow.camera.updateProjectionMatrix();
  head.lightDirect.shadow.bias=-.00015;
  head.lightDirect.shadow.normalBias=.008;
  head.scene.traverse(mesh=>{
   if(!mesh.isMesh)return;
   mesh.receiveShadow=true;
   mesh.castShadow=!/eyelash|eyebrow|eye$/i.test(mesh.name);
  });

  ready=true;window.jinx3d={head,get state(){return state},get layout(){return {...nativeLayout}},get ready(){return ready},get renderedFrames(){return renderedFrames},get mouth(){return {...speechMotion.weights}},get subtitles(){return subtitles.cues}};
  head.lookAtCamera(2000);head.playGesture('handup',1.5,false,900);$('caption').textContent='Click Jinx to talk';captionUntil=Date.now()+6500;
  console.log('3D avatar ready; bones and facial morph targets loaded');
 }catch(e){error='Avatar failed to load: '+e.message;console.error(error);$('caption').textContent=error;}
}
async function poll(){
 try{
  state=await api('/status');online=true;statusReceivedAt=performance.now();
  const choices=state.ai_choices||[];
  const signature=JSON.stringify(choices);
  if($('modelChoice').dataset.choices!==signature){$('modelChoice').replaceChildren(...choices.map(c=>new Option(c.label,c.id)));$('modelChoice').dataset.choices=signature;}
  if(document.activeElement.id!=='modelChoice')$('modelChoice').value=state.ai_mode||'auto';
  $('modelChoice').disabled=!!(state.busy||state.ptt||state.conversation);
  $('modelHint').textContent=(choices.find(c=>c.id===(state.ai_mode||'auto'))||{}).description||'';
  const nextPendingIds=new Set((state.pending||[]).map(p=>p.id));
  if([...nextPendingIds].some(id=>!pendingIds.has(id))){gate.wake(performance.now());applyGate()}
  pendingIds=nextPendingIds;
  $('screenEnabled').checked=state.screen_enabled!==false;for(const id of ['lookScreen','readScreen'])$(id).disabled=!!(state.busy||state.ptt||state.conversation)||state.screen_enabled===false;
  if(activation){activation=false;await act('/conversation',{unmute:!!state.muted})}
  let phase=state.phase||'Ready';
  if(state.speech&&state.speech.id!==speechId&&ready){
   speechId=state.speech.id;speech=state.speech;
   visemes=head.lipsyncWordsToVisemes(head.lipsyncPreProcessText(speech.text,'en'),'en');
   speechMotion.set(speech,visemes);startSubtitles(speech);gate.wake(performance.now());applyGate();
  }else if(ready&&state.speech&&state.speech.id===speechId&&(state.speech.envelope?.levels?.length!==speech?.envelope?.levels?.length||state.speech.streaming!==speech?.streaming)){
   // A streamed sentence grows without restarting its playback clock.
   speech=state.speech;speechMotion.set(speech,visemes);startSubtitles(speech);
  }
  if(ready){
   // Capture belongs to PipeWire in the backend; TalkingHead's listening mode
   // requires a browser AnalyserNode and must not be enabled without one.
   head.isSpeaking=phase==='Speaking'||!!state.filler_speaking;head.isListening=false;
   applyGate();
   if(phase!==lastPhase){
    gate.wake(performance.now());applyGate();
    if(phase==='Listening — speak now')head.lookAtCamera(15000);
    if(phase==='Speaking'){
     captionUntil=Date.now()+7000;head.lookAtCamera(4000);
     if(Date.now()-lastGesture>9000){head.playGesture('side',2.5,Math.random()>.5,900);lastGesture=Date.now()}
     head.setMood(/glad|lovely|happy|welcome|hello/i.test(speech?.text||'')?'happy':'neutral');
    }
    if(lastPhase==='Speaking'&&phase!=='Speaking')captionUntil=Date.now()+6500;
   }
  }
  lastPhase=phase;let active=state.busy||state.ptt;document.body.classList.toggle('active',!!active);
  let n=(state.pending||[]).length;document.body.classList.toggle('pending',n>0);$('reviewButton').style.display=n?'':'none';$('reviewButton').textContent='Review '+n;

  $('thinkingSounds').checked=state.thinking_sounds!==false;$('wake').checked=!!state.listening;$('voice').checked=!!state.speak;if(document.activeElement.id!=='voiceChoice')$('voiceChoice').value=state.voice||'kokoro_emma';$('voicePreview').disabled=!!(state.busy||state.ptt||state.conversation);if(document.activeElement.id!=='avatarVoiceSpeed'){$('avatarVoiceSpeed').value=state.voice_speed||1;$('avatarVoiceSpeedValue').value=Number(state.voice_speed||1).toFixed(2)+'×';}
  if(state.busy||state.ptt)silentSubtitleUntil=0;
  const lastReply=state.messages?.at(-1);
  if(!state.busy&&!state.ptt&&lastReply?.role==='assistant'&&lastReply.content!==lastWrittenReply){
   lastWrittenReply=lastReply.content;
   if(state.speak===false){
    const text=lastReply.content.replace(/[*#`]/g,'').trim();
    const duration=Math.max(3,text.length/16);silentSubtitleUntil=performance.now()+duration*1000;
    startSubtitles({id:'written-'+Date.now(),text,position_ms:0,duration});
   }
  }
  const speaking=subtitlePlaying();
  let message=error||state.error||'';
  if(!message&&!speaking){
   if(nativeLayout.unlocked&&!active)message='Drag Jinx to move her';
   else if(phase==='Listening — speak now')message='Listening…';
   else if(phase==='Transcribing')message='Understanding…';
   else if(phase==='Your turn')message='Listening…';
   else if(active)message=activityText(state);
   else message=subtitles.sample(performance.now(),false);
  }
  if(ready){
   if(speaking&&!message)renderSubtitles();
   else{$('caption').dataset.kind=message&&message===subtitles.last?'speech':'status';$('caption').textContent=message}
  }
 }catch(e){online=false;$('caption').textContent='Jinx is offline · click her to start'}
 updateActivityInfo();
 setTimeout(poll,pollDelay({hidden,busy:state.busy,ptt:state.ptt,reason:gate.reason}));
}
const ring=$('ring'),ctx=ring.getContext('2d');let angle=0;
function draw(){
 let dpr=Math.min(devicePixelRatio,1.5),w=innerWidth,h=innerHeight;
 if(ring.width!==Math.round(w*dpr)||ring.height!==Math.round(h*dpr)){ring.width=Math.round(w*dpr);ring.height=Math.round(h*dpr)}
 ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 let listening=state.phase==='Listening — speak now'||state.phase==='Opening microphone';let speaking=state.phase==='Speaking';let thinking=!speaking&&(state.busy||state.phase==='Transcribing'||activation);
 level+=(Math.max(0,Math.min(1,state.audio_level||0))-level)*.4;
 if(listening||thinking||speaking){
  let cx=w/2,cy=(h-55)*.62,r=Math.min(w/2-14,(h-90)/2);ctx.strokeStyle=listening?'#93e4dc':thinking?'#d0dced':'#a5c9ee';ctx.globalAlpha=.24;ctx.lineWidth=1;
  ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.stroke();
  if(thinking){angle+=.08;for(let i=0;i<28;i++){ctx.globalAlpha=(i+1)/30;ctx.lineWidth=2.5;ctx.lineCap='round';ctx.beginPath();ctx.arc(cx,cy,r,angle+i*.06,angle+i*.06+.05);ctx.stroke()}}
  else{for(let i=0;i<90;i++){let a=i/90*Math.PI*2,l=1+level*(5+9*Math.sin(a*3)**2);ctx.globalAlpha=.35+level*.6;ctx.lineWidth=1.7;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(cx+Math.cos(a)*(r-l*.25),cy+Math.sin(a)*(r-l*.25));ctx.lineTo(cx+Math.cos(a)*(r+l*.75),cy+Math.sin(a)*(r+l*.75));ctx.stroke()}}
 }
 const next=ringDelay({drawing:listening||thinking||speaking,busy:state.busy,ptt:state.ptt});
 if(next==null){ringRunning=false;ctx.clearRect(0,0,w,h);return}
 setTimeout(draw,next);
}
function ringDrawing(){return state.phase==='Listening — speak now'||state.phase==='Opening microphone'||state.phase==='Speaking'||state.busy||state.phase==='Transcribing'||activation}
function startRing(){if(!ringRunning){ringRunning=true;draw()}}
initialise();poll();startRing();
