"""Cheap NetworkManager hint: skip cloud attempts on a known disconnected link."""
import subprocess,time
_cached=(0,True)
def online():
 global _cached
 now=time.monotonic()
 if now-_cached[0]<2:return _cached[1]
 try:
  p=subprocess.run(['nmcli','-t','-f','CONNECTIVITY','general'],capture_output=True,text=True,timeout=.4)
  ready=p.returncode!=0 or p.stdout.strip() not in ('none','limited','portal')
 except (OSError,subprocess.TimeoutExpired):ready=True
 _cached=(now,ready);return ready
