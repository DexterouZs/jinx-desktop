// Short, measured two-line cues paced against actual audio activity.
// Timing is approximate; no extra recognition pass delays speech.
export function makeCues(text,width,measure,weights=[]){
 const words=String(text||'').trim().split(/\s+/).filter(Boolean),fragments=[];
 words.forEach((word,index)=>{
  let rest=word;
  while(rest){
   let n=rest.length;
   while(n>1&&measure(rest.slice(0,n))>width)n--;
   const part=rest.slice(0,n);rest=rest.slice(n);
   fragments.push({text:part,weight:(weights[index]||word.length||1)*part.length/word.length,broken:!!rest});
  }
 });
 const lines=[];let line='',weight=0;
 for(const f of fragments){
  const joined=line?line+' '+f.text:f.text;
  if(line&&measure(joined)>width){lines.push({text:line,weight});line='';weight=0}
  line=line?line+' '+f.text:f.text;weight+=f.weight;
  if(f.broken){lines.push({text:line,weight});line='';weight=0}
 }
 if(line)lines.push({text:line,weight});
 const cues=[];let at=0;
 for(let i=0;i<lines.length;){
  // Leave two lines for the final cue; a short trailing line otherwise flashes
  // by alone (for example just "memory." after a hardware description).
  const count=lines.length-i===3?1:2;
  const pair=lines.slice(i,i+count),weight=pair.reduce((n,x)=>n+x.weight,0);i+=count;
  cues.push({text:pair.map(x=>x.text).join('\n'),start:at,end:at+weight});at+=weight;
 }
 for(const cue of cues){cue.start/=at||1;cue.end/=at||1}
 return cues;
}
export class Subtitles {
 constructor(){this.id=null;this.cues=[];this.ended=0;this.last=''}
 set(speech,width,measure,now=performance.now()){
  this.id=speech.id;this.speech=speech;this.anchor=now-(speech.position_ms??Math.max(0,(Date.now()/1000-speech.started)*1000));
  this.cues=makeCues(speech.display_text||speech.text,width,measure,speech.word_weights);
  const levels=speech.envelope?.levels||[];this.step=speech.envelope?.step_ms||20;
  this.activity=[0];for(const v of levels)this.activity.push(this.activity.at(-1)+(v>.015?.55+.45*v:0));
  this.ended=0;this.last='';
 }
 sample(now=performance.now(),speaking=true){
  if(!this.speech)return '';
  if(!speaking){if(!this.ended)this.ended=now;return now-this.ended<1000?this.last:''}
  this.ended=0;
  const ms=Math.max(0,now-this.anchor),duration=this.speech.duration*1000;
  let progress=Math.min(1,ms/Math.max(duration,1));
  const total=this.activity.at(-1);
  if(total>0&&!this.speech.streaming){
   const f=Math.min(ms/this.step,this.activity.length-1),i=Math.floor(f);
   progress=(this.activity[i]+((this.activity[i+1]??this.activity[i])-this.activity[i])*(f-i))/total;
  }
  const cue=this.cues.find(c=>progress<c.end)||this.cues.at(-1);
  this.last=cue?.text||'';return this.last;
 }
 clear(){this.speech=null;this.last='';this.ended=0;this.id=null}
}
