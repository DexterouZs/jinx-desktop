// Text supplies shapes; the actual waveform supplies pauses and an articulation clock.
// This remains approximate phoneme alignment, with no additional inference latency.
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
export class SpeechMotion {
 constructor(){this.clear()}
 clear(){this.track=null;this.weights={};this.id=null}
 set(speech,visemes,now=performance.now()){
  this.id=speech.id;this.speech=speech;this.anchor=now-Math.max(0,speech.position_ms??(Date.now()/1000-speech.started)*1000);
  const e=speech.envelope,levels=e?.levels||[],step=e?.step_ms||20;
  const cumulative=[0];
  for(const v of levels)cumulative.push(cumulative.at(-1)+(v>.015?(.55+.45*v):0));
  this.track={levels,step,cumulative,total:cumulative.at(-1),visemes,span:(visemes.times.at(-1)||0)+(visemes.durations.at(-1)||0)};
 }
 sample(now=performance.now(),active=true,dt=16.67,fallbackLevel=0){
  const t=this.track,s=this.speech,desired={};
  let elapsed=s?now-this.anchor:0,energy=0;
  if(active&&t&&elapsed>=0&&elapsed<s.duration*1000){
   let position=elapsed/(s.duration*1000)*t.span;
   if(t.levels.length){
    const f=clamp(elapsed/t.step,0,t.levels.length-1),i=Math.floor(f),mix=f-i;
    energy=t.levels[i]*(1-mix)+(t.levels[i+1]??t.levels[i])*mix;
    if(t.total>0&&!s.streaming)position=(t.cumulative[i]+(t.cumulative[i+1]-t.cumulative[i])*mix)/t.total*t.span;
   }else energy=clamp(fallbackLevel*2);
   // Short anticipation/release overlaps avoid switching between isolated poses.
   // Enforce silence independently so silent padding cannot hold an open mouth.
   const gate=smooth(energy/.12),v=t.visemes;
   const stretch=s.duration*1000/Math.max(t.span,1);
   const overlap=55/Math.max(stretch,.1);
   let sum=0;
   for(let i=0;i<v.visemes.length;i++){
    const name=v.visemes[i],start=v.times[i],end=start+v.durations[i];
    if(position<start-overlap||position>end+overlap||name==='sil')continue;
    const w=smooth((position-start+overlap)/(overlap*2))*smooth((end+overlap-position)/(overlap*2));
    desired[name]=(desired[name]||0)+w;sum+=w;
   }
   for(const name of Object.keys(desired)){
    // Bilabials need a confident closure; rounded vowels need less deformation.
    const gain=name==='PP'?.62:['O','U'].includes(name)?.43:.52;
    desired[name]=desired[name]/Math.max(sum,1)*gain*(.55+.45*energy)*gate;
   }
  }
  for(const name of new Set([...Object.keys(this.weights),...Object.keys(desired)])){
   const goal=desired[name]||0,old=this.weights[name]||0;
   const alpha=1-Math.exp(-clamp(dt,0,100)/(goal>old?32:48));
   this.weights[name]=old+(goal-old)*alpha;
   if(this.weights[name]<.0005)delete this.weights[name];
  }
  return {weights:{...this.weights},energy,elapsed};
 }
}
