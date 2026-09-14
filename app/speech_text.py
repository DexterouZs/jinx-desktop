"""Pronounce compact technical notation without changing the written answer or saved pace."""
import re
SMALL='zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS=['','','twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety']
LETTERS=dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',['ay','bee','see','dee','ee','eff','gee','aitch','eye','jay','kay','ell','em','en','oh','pee','cue','ar','ess','tee','you','vee','double you','ex','why','zed']))
ACRONYMS={x:' '.join(LETTERS[c] for c in x.upper()) for x in ['AMD','CPU','GPU','KDE','BIOS','SSD','USB','HDMI','VRAM','NVMe','UEFI','API','LLM','ROG','AI','HFP']}
ACRONYMS.update({'RAM':'ram','A2DP':'ay two dee pee','MAX':'Max','CachyOS':'Cachy O S'})
UNITS={'GB':'gigabytes','GiB':'gibibytes','Gi':'gibibytes','MB':'megabytes','MiB':'mebibytes','Mi':'mebibytes','TB':'terabytes','KB':'kilobytes','kB':'kilobytes','GHz':'gigahertz','MHz':'megahertz','Hz':'hertz','W':'watts','mW':'milliwatts','Wh':'watt hours','mAh':'milliamp hours','RPM':'ar pee em','°C':'degrees Celsius','%':'percent'}

def integer(value):
 if len(value)>1 and value[0]=='0':return ' '.join(SMALL[int(c)] for c in value)
 n=int(value)
 if n<20:return SMALL[n]
 if n<100:return TENS[n//10]+(' '+SMALL[n%10] if n%10 else '')
 if n<1000:return SMALL[n//100]+' hundred'+(' and '+integer(str(n%100)) if n%100 else '')
 if n<1000000:return integer(str(n//1000))+' thousand'+(' '+integer(str(n%1000)) if n%1000 else '')
 return ' '.join(SMALL[int(c)] for c in value)

def number(value):
 if '.' in value:
  chunks=value.split('.')
  if len(chunks)>2:return ' point '.join(' '.join(SMALL[int(c)] for c in x) for x in chunks)
  return integer(chunks[0])+' point '+' '.join(SMALL[int(c)] for c in chunks[1])
 return integer(value)

def token(value):
 # Keep punctuation outside the pronounced value, including parenthesised
 # specifications such as "(GPU)" or "(16 GB)".
 leading=re.match(r"^[\(\[\{\"'“‘]*",value)[0]
 value=value[len(leading):]
 trailing=re.search(r"[\)\]\}\"'”’.,;:!?]*$",value)[0]
 core=value[:-len(trailing)] if trailing else value
 return leading+_token(core)+trailing

def _token(value):
 # URLs and paths are left intact; they are not arithmetic or device models.
 if '://' in value or value.startswith(('/', '~')):return value
 # MAC addresses are identifiers: preserve every hex digit, rather than saying
 # paired decimal numbers. No actual address is embedded in this module.
 if re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}[.,;]?',value):
  pairs=value.rstrip('.,;').split(':')
  return ', '.join(' '.join(SMALL[int(c)] if c.isdigit() else LETTERS[c.upper()] for c in pair) for pair in pairs)
 suffix=''
 while value and value[-1] in ',;!?':suffix=value[-1]+suffix;value=value[:-1]
 if value.endswith('.') and not re.search(r'\d\.\d',value):suffix='.'+suffix;value=value[:-1]
 units=re.fullmatch(r'([+-]?)(\d+(?:\.\d+)?)('+('|'.join(re.escape(u) for u in sorted(UNITS,key=len,reverse=True)))+')',value)
 if units:return ('minus ' if units[1]=='-' else 'plus ' if units[1]=='+' else '')+number(units[2])+' '+UNITS[units[3]]+suffix
 signed=re.fullmatch(r'([+-])(\d+(?:\.\d+)?)',value)
 if signed:return ('minus ' if signed[1]=='-' else 'plus ')+number(signed[2])+suffix
 if value in ACRONYMS:return ACRONYMS[value]+suffix
 if value in UNITS:return UNITS[value]+suffix
 if not re.search(r'\d',value):return value+suffix
 # Only compact numbers / versions / letter-number identifiers are expanded.
 parts=re.findall(r'\d+(?:\.\d+)*|[A-Za-z]+|[^A-Za-z0-9]',value)
 mixed=bool(re.search(r'[A-Za-z]',value)) and not any(u in value for u in UNITS if len(u)>1)
 out=[]
 for part in parts:
  if part[0].isdigit():
   if mixed and len(part)>1 and '.' not in part:out.append(' '.join(SMALL[int(c)] for c in part))
   else:out.append(number(part))
  elif part in UNITS:out.append(UNITS[part])
  elif part in ACRONYMS:out.append(ACRONYMS[part])
  elif part.isalpha() and mixed and len(part)<=2:out.append(' '.join(LETTERS[c.upper()] for c in part))
  elif part=='+':out.append('plus')
  elif part=='-':out.append('dash')
  elif part=='/':out.append('slash')
  elif part=='%':out.append('percent')
  elif part=='°':out.append('degrees')
  else:out.append(part)
 return ' '.join(out)+suffix

def technical(text):
 return any(re.search(r'(?<![A-Za-z])'+re.escape(a)+r'(?![A-Za-z])',text) for a in ACRONYMS) or bool(re.search(r'\d+(?:\.\d+){2,}|\b[A-Z]{1,3}\d+|\b\d+[A-Z]\b|\d\s*(?:'+('|'.join(re.escape(u) for u in UNITS))+')(?![A-Za-z])',text))

def spoken(text):
 # Ordinary conversation keeps its existing pronunciation and pacing.
 if not technical(str(text)):return str(text)
 return re.sub(r'\S+',lambda m:token(m[0]),str(text))

def word_weights(text):
 # Subtitle pacing follows the pronunciation length, so "16GB" is not treated
 # as one tiny spoken word. These are approximate timings, not forced alignment.
 expand=technical(str(text))
 return [max(1,len(re.sub(r'[^A-Za-z0-9]','',token(w) if expand else w))) for w in str(text).split()]
