from runtime_paths import state_dir, models_dir, config_dir, runtime_dir
"""On-demand FastFlowLM speech recognition on the AMD NPU.

Powered by https://github.com/ROCm/FastFlowLM. No speech is written to logs.
The worker lives inside Jinx's systemd cgroup and exits after idle or shutdown.
"""
import atexit
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
import uuid

MODEL_PATH=models_dir()/'flm'
class SpeechCancelled(Exception):pass
class NpuUnavailable(RuntimeError):pass

class NpuSpeech:
    def __init__(self,idle_seconds=60,start_timeout=15,request_timeout=20):
        self.process=None
        self.port=None
        self.idle_seconds=idle_seconds
        self.start_timeout=start_timeout
        self.request_timeout=request_timeout
        self.lock=threading.RLock()
        self.idle_timer=None
        self.retry_after=0
        self.last_error=''
        self.generation=0
        self.stuck_processes=[]
        atexit.register(self.release)

    def _stop(self):
        if self.idle_timer:self.idle_timer.cancel();self.idle_timer=None
        p=self.process;self.process=None;self.port=None
        if p is not None and p.poll() is None:
            try:
                p.terminate()
                try:p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
                    try:p.wait(timeout=.2)
                    except subprocess.TimeoutExpired:
                        # A driver-blocked D-state task cannot exit until the kernel
                        # releases it. Do not raise past the CPU fallback or spawn more.
                        self.stuck_processes.append(p)
                        self.last_error='NPU driver is blocked; CPU recognition is available. Restart Linux before retrying the NPU.'
            except ProcessLookupError:pass

    def release(self):
        with self.lock:self._stop()

    def _expire(self,generation):
        with self.lock:
            if generation==self.generation:self._stop()

    def _request(self,path,payload=None,content_type=None,timeout=2):
        headers={'Content-Type':content_type} if content_type else {}
        request=urllib.request.Request(f'http://127.0.0.1:{self.port}'+path,data=payload,headers=headers)
        # Audio must never pass through an environment-configured HTTP proxy.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request,timeout=timeout) as response:
            data=response.read(1024*1024+1)
        if len(data)>1024*1024:raise NpuUnavailable('Invalid NPU response size')
        return json.loads(data)

    def _start(self,cancelled):
        if cancelled():raise SpeechCancelled()
        if self.process is not None and self.process.poll() is None:return
        self._stop()
        self.stuck_processes=[p for p in self.stuck_processes if p.poll() is None]
        if self.stuck_processes:raise NpuUnavailable('NPU driver is still blocked; using CPU recognition')
        if time.monotonic()<self.retry_after:raise NpuUnavailable('NPU cooling down after a failed request')
        binary=shutil.which('flm')
        if not binary or not (MODEL_PATH/'models/Whisper-V3-Turbo-NPU2/model.q4nx').is_file():
            raise NpuUnavailable('NPU speech runtime or model is unavailable')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));self.port=listener.getsockname()[1]
        env={**os.environ,'FLM_MODEL_PATH':str(MODEL_PATH),'FLM_DISABLE_UPDATE_CHECK':'1'}
        # Do not store FLM stdout: it contains recognized speech.
        self.process=subprocess.Popen([binary,'serve','--asr','1','--host','127.0.0.1','--port',str(self.port),'--pmode','powersaver','--cors','0'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
        deadline=time.monotonic()+self.start_timeout
        while time.monotonic()<deadline:
            if cancelled():raise SpeechCancelled()
            if self.process.poll() is not None:raise NpuUnavailable('NPU speech worker failed to start')
            try:
                self._request('/v1/models',timeout=.25)
                return
            except (OSError,ValueError):time.sleep(.05)
        raise NpuUnavailable('NPU speech startup timed out')

    def transcribe(self,path,cancelled=lambda:False):
        with self.lock:
            self.generation+=1
            if self.idle_timer:self.idle_timer.cancel();self.idle_timer=None
            try:
                self._start(cancelled)
                audio=Path(path).read_bytes()
                if len(audio)>16*1024*1024:raise NpuUnavailable('Audio exceeds the speech request limit')
                boundary='jinx-'+uuid.uuid4().hex
                body=(f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-v3\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()+audio+f'\r\n--{boundary}--\r\n'.encode())
                result=queue.Queue(maxsize=1)
                def request():
                    try:result.put((True,self._request('/v1/audio/transcriptions',body,'multipart/form-data; boundary='+boundary,timeout=self.request_timeout)))
                    except Exception as exc:result.put((False,exc))
                threading.Thread(target=request,daemon=True,name='jinx-npu-request').start()
                deadline=time.monotonic()+self.request_timeout+1
                while time.monotonic()<deadline:
                    if cancelled():raise SpeechCancelled()
                    try:ok,data=result.get(timeout=.05)
                    except queue.Empty:continue
                    if not ok:raise NpuUnavailable('NPU speech request failed') from data
                    if not isinstance(data,dict) or not isinstance(data.get('text'),str):
                        raise NpuUnavailable('NPU returned no transcription')
                    if cancelled():raise SpeechCancelled()
                    self.last_error=''
                    self.idle_timer=threading.Timer(self.idle_seconds,self._expire,args=(self.generation,))
                    self.idle_timer.daemon=True;self.idle_timer.start()
                    return data['text'].strip()
                raise NpuUnavailable('NPU speech request timed out')
            except SpeechCancelled:
                self._stop();raise
            except Exception as exc:
                self._stop();self.retry_after=time.monotonic()+60
                self.last_error='NPU speech unavailable; CPU fallback active.'
                if isinstance(exc,NpuUnavailable):raise
                raise NpuUnavailable('NPU speech unavailable') from exc

    def info(self):
        p=self.process
        return {'active':p is not None and p.poll() is None,'engine':'AMD NPU · Whisper v3 Turbo','notice':self.last_error}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Transcribe a WAV file locally using the AMD NPU')
    parser.add_argument('audio',type=Path)
    args=parser.parse_args()
    speech=NpuSpeech()
    try:print(speech.transcribe(args.audio))
    finally:speech.release()
