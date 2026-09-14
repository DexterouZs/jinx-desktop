#!/usr/bin/env python3
"""Small SQLite-consistent daily snapshots; never starts the assistant or models."""
from pathlib import Path
import datetime,json,os,shutil,sqlite3,tempfile

def backup(state,personality,destination,today=None):
 os.umask(0o077)
 today=today or datetime.date.today()
 state=Path(state);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True,mode=0o700)
 final=destination/today.isoformat()
 # One verified snapshot per day. Never replace an existing backup in place.
 if final.exists():
  manifest=json.loads((final/'manifest.json').read_text())
  if manifest.get('format')!='jinx-memory-snapshot-v1':raise RuntimeError('Unrecognised existing backup directory')
  for name in ('memory.sqlite3','knowledge.sqlite3'):
   if name not in manifest['files']:continue
   with sqlite3.connect('file:'+str(final/name)+'?mode=ro',uri=True) as db:
    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Existing memory backup is damaged')
  return final
 with tempfile.TemporaryDirectory(prefix='.creating-',dir=destination) as temp:
  root=Path(temp);names=[]
  for name in ('memory.sqlite3','knowledge.sqlite3'):
   source=state/name
   if not source.is_file():continue
   with sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True) as src,sqlite3.connect(root/name) as dst:
    src.backup(dst)
    if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Memory snapshot integrity check failed')
   names.append(name)
  if not names:raise RuntimeError('No memory databases found')
  if Path(personality).is_file():shutil.copyfile(personality,root/'PERSONALITY.md');names.append('PERSONALITY.md')
  (root/'manifest.json').write_text(json.dumps({'format':'jinx-memory-snapshot-v1','date':today.isoformat(),'files':names}))
  root.rename(final)
 for path in destination.iterdir():
  if not path.is_dir():continue
  try:day=datetime.date.fromisoformat(path.name)
  except ValueError:continue
  if (today-day).days<14:continue
  try:manifest=json.loads((path/'manifest.json').read_text())
  except (OSError,ValueError):continue
  if manifest.get('format')=='jinx-memory-snapshot-v1':shutil.rmtree(path)
 return final

if __name__=='__main__':
 home=Path.home()
 result=backup(home/'.local/state/jinx',home/'Jinx/PERSONALITY.md',home/'.local/share/jinx/memory-backups')
 print('Memory backup ready:',result.name)
