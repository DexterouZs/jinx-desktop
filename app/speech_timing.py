"""Small private waveform envelopes for smooth avatar timing; no recogniser or model."""
import numpy as np

def envelope(samples,rate):
 samples=np.asarray(samples,dtype=np.float32)
 if samples.ndim==2:samples=samples.mean(axis=1)
 if not len(samples) or rate<=0:return {'step_ms':20,'levels':[]}
 # At most 2000 samples even for a long voice chunk. A quiet waveform stays quiet.
 hop=max(int(rate*.02),int(np.ceil(len(samples)/2000)))
 padded=np.pad(samples,(0,(-len(samples))%hop))
 rms=np.sqrt(np.mean(padded.reshape(-1,hop)**2,axis=1))
 peak=float(np.percentile(rms,90))
 if peak<25:levels=np.zeros_like(rms)
 else:
  floor=max(25,peak*.045)
  levels=np.clip((rms-floor)/max(1,peak-floor),0,1)**.65
 return {'step_ms':round(hop/rate*1000,3),'levels':np.round(levels,3).tolist()}
