"""Read only checkbox tasks from David's connected local vault; never execute notes."""
import datetime as dt,re
from pathlib import Path
VAULT=Path.home()/'Documents/Obsidian Vault'
def read(args):
 day=dt.date.fromisoformat(args.get('date') or dt.date.today().isoformat());days=args.get('days',7)
 if type(days) is not int or not 1<=days<=31:raise ValueError('Choose 1 to 31 days')
 end=day+dt.timedelta(days=days);tasks=[];count=0;truncated=False
 if not VAULT.is_dir():return {'error':'The Obsidian vault is not available.'}
 for p in sorted(VAULT.rglob('*.md')):
  relative=p.relative_to(VAULT)
  if any(part.startswith('.') for part in relative.parts) or not p.resolve().is_relative_to(VAULT.resolve()):continue
  count+=1
  if count>200:truncated=True;break
  if p.stat().st_size>1024*1024:truncated=True;continue
  fence=None
  for number,line in enumerate(p.read_text(errors='replace').splitlines(),1):
   marker=re.match(r'^\s*(`{3,}|~{3,})',line)
   if marker:
    if fence is None:fence=marker[1][0]
    elif fence==marker[1][0]:fence=None
    continue
   if fence:continue
   m=re.match(r'^\s*[-*+] \[ \] (.+)$',line)
   if not m:continue
   title=m[1];due=re.search(r'📅\s*(\d{4}-\d{2}-\d{2})',title)
   if due and due[1]>=end.isoformat():continue
   tasks.append({'text':title[:500],'note':str(relative),'line':number,'due':due[1] if due else None})
   if len(tasks)>=100:return {'source':'Obsidian desktop vault','tasks':tasks,'truncated':True}
 return {'source':'Obsidian desktop vault','tasks':tasks,'truncated':truncated,'note':'Unfinished checkboxes; undated tasks are not appointments. Calendar scheduling is reported separately.'}
