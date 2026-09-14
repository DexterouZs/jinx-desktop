// Visible activity summaries from application state; no model reasoning trace.
export function activityText(state={}){
 const tools={jinx_logs:'Checking system logs',jinx_system:'Checking your system',jinx_shell:'Working in the terminal',jinx_web_search:'Searching the web',jinx_web_read:'Reading a webpage',jinx_calendar:'Checking your calendar',jinx_memory:'Looking up your saved notes',jinx_document:'Reading your document',jinx_software:'Checking software options',jinx_light:'Working with your lights',jinx_music:'Working with Spotify',jinx_propose:'Preparing your confirmation',jinx_apps:'Working with your apps'};
 if(state.tool_activity?.name)return tools[state.tool_activity.name]||'Using a local tool';
 const phase=state.phase||'';
 if(state.deliberate&&/Thinking|answer|request/i.test(phase))return 'Thinking this through';
 const labels={
  'Preparing a quick reply':'A quick thought…',
  'Thinking':'Thinking…',
  'Preparing an answer':'Putting the answer together',
  'Working on your request':'Working on your request',
  'Thinking carefully':'Thinking this through',
  'Transcribing':'Understanding what you said',
  'Preparing voice':'Getting ready to speak',
  'Looking at your screen':'Looking at your screen',
  'Understanding your screen':'Checking what is on screen',
  'Listening — speak now':'Listening to you',
  'Opening microphone':'Opening the microphone',
  'Your turn':'Your turn…',
  'Stopping':'Stopping…',
 };
 return labels[phase]||'Working on your request';
}
export function bubbleKind(state={},captionKind='status',text=''){
 if(!text)return 'hidden';
 if(captionKind==='speech')return 'speech';
 if(state.error)return 'status';
 if(state.busy&&!state.ptt&&!/Listening|microphone|Your turn/.test(state.phase||''))return 'thought';
 return 'status';
}
export function modelBadge(state={},kind='status'){
 if(kind==='speech')return 'Jinx';
 if(kind!=='thought')return '';
 if(state.phase==='Transcribing')return (state.speech_backend||'').includes('NPU')?'Listening · AMD NPU':'Listening';
 if(state.phase==='Preparing voice')return 'Breeze · voice';
 const name=state.active_model||'';
 if(name.includes('27b'))return 'Qwen 3.8 27B · '+(state.deliberate?'careful':'capable');
 if(name.includes('4b'))return 'Qwen 3.5 4B · quick';
 if(name==='Direct tools')return 'Jinx · on your device';
 return 'Jinx';
}
