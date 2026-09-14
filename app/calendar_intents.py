"""Direct calendar deletion dialogue; no model or calendar write while selecting."""
import datetime as dt
import re
import time
import request_intents
import calendar_delete as deletion

pending=None


def reset():
    global pending
    pending=None


def clean(text):
    text=re.sub(r'^(?:(?:hey|hi)\s+)?(?:jings|jinks)\b[\s,.:]*','',str(text).strip(),flags=re.I)
    text=request_intents.command_text(text)
    return re.sub(r'^(?:actually|just)\s+','',text,flags=re.I)


def parse(text):
    text=clean(text)
    match=re.match(r'^(delete|remove|cancel|reschedule|move|verschiebe|lösche|loesche|entferne)\s+(.+)',text,re.I)
    if not match or not re.search(r'\b(?:appointments?|meetings?|calendar events?|calendar entr(?:y|ies)|termine?|termin|kalendereintrag)\b',match[2],re.I):return None
    return {'operation':'reschedule' if match[1].casefold() in ('reschedule','move','verschiebe') else 'delete', 'text':match[2]}


def day_from(text,now=None):
    today=(now or dt.datetime.now(deletion.morgen.ZONE)).date()
    iso=re.search(r'\b(20\d{2}-\d{2}-\d{2})\b',text)
    if iso:return dt.date.fromisoformat(iso[1])
    text=text.casefold()
    if re.search(r'\bday after tomorrow\b',text):return today+dt.timedelta(days=2)
    if re.search(r'\b(tomorrow|morgen)\b',text):return today+dt.timedelta(days=1)
    if re.search(r'\b(today|heute)\b',text):return today
    for index,name in enumerate(('monday','tuesday','wednesday','thursday','friday','saturday','sunday')):
        if re.search(r'\b'+name+r'\b',text):
            return today+dt.timedelta(days=(index-today.weekday())%7 or 7)
    return None


def title_from(text):
    quoted=re.search(r'["“](.+?)["”]',text)
    if quoted:return quoted[1].strip()
    value=re.sub(r'\b(?:20\d{2}-\d{2}-\d{2}|today|tomorrow|day after tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|morgen|heute)\b','',text,flags=re.I)
    value=re.sub(r'\bat\s+\d{1,2}(?::\d{2})?(?:\s*[ap]m)?\b','',value,flags=re.I)
    value=re.sub(r'\b(?:my|the|an?|all|appointments?|meetings?|calendar|events?|entry|entries|for|on|called|named|please|next|me|termin)\b',' ',value,flags=re.I)
    return ' '.join(value.strip(' .!?').split())


def select(rows,text):
    wanted=title_from(text).casefold()
    clock=re.search(r'\bat\s+(\d{1,2})(?::(\d{2}))?(?:\s*([ap]m))?\b',text,re.I)
    for row in rows:
        if wanted and wanted not in row['title'].casefold():continue
        if clock:
            hour=int(clock[1]);minute=int(clock[2] or 0)
            if clock[3]:hour=hour%12+(12 if clock[3].casefold()=='pm' else 0)
            if hour>23 or minute>59:continue
            if row['all_day']:continue
            start=dt.datetime.fromisoformat(row['start'])
            if (start.hour,start.minute)!=(hour,minute):continue
        yield row


def requested(text):
    global pending
    now=time.monotonic();intent=parse(text);t=clean(text).strip(' .!?')
    if pending and pending['expires']<now:pending=None
    if intent and intent['operation']=='reschedule':
        pending=None
        return {'reply':'I can delete an appointment after confirmation, but moving it is not connected yet. You can move it in Morgen.','_tools':[]}
    if pending and t.casefold() in ('cancel','no','never mind','forget it'):
        pending=None;return {'reply':'Cancelled. Nothing was deleted.','_tools':[]}
    if not intent and not pending:return None
    try:
        if intent:
            pending=None
            if re.search(r'\b(all|every|whole series|entire series|future occurrences)\b',intent['text'],re.I):
                return {'reply':'I can remove one appointment or dated occurrence at a time. Which day and appointment do you mean?','_tools':[]}
            day=day_from(intent['text'])
            if day is None:
                pending={'query':intent['text'],'expires':now+120}
                return {'reply':'Which day is the appointment on? You can say tomorrow or give a date such as 2026-09-18.','_tools':[]}
            query=intent['text']
        elif 'query' in pending:
            day=day_from(t)
            if day is None:
                pending=None;return None
            query=pending['query']+' '+t;pending=None
        else:
            rows=pending['rows']
            index={'1':0,'one':0,'first':0,'the first one':0,'2':1,'two':1,'second':1,'the second one':1,'3':2,'three':2,'third':2,'the third one':2}.get(t.casefold())
            chosen=[rows[index]] if index is not None and index<len(rows) else list(select(rows,t))
            if len(chosen)!=1:
                # Unrelated requests must not be swallowed by stale selection state.
                if re.match(r'^(open|write|play|read|search|show|tell)\b',t,re.I):pending=None;return None
                return {'reply':'Please say the number or exact title of one appointment from that list. Nothing was deleted.','_tools':[]}
            pending=None
            return {'delete_fields':deletion.prepare(chosen[0]),'_tools':['jinx_calendar']}
        rows=list(select(deletion.candidates(day),query))
        if not rows:
            return {'reply':'I found no matching appointment starting on '+day.strftime('%A %d %B')+'. Nothing was deleted.','_tools':['jinx_calendar']}
        if len(rows)==1:return {'delete_fields':deletion.prepare(rows[0]),'_tools':['jinx_calendar']}
        if len(rows)>8:
            return {'reply':'There are several appointments that day. Please ask again with the exact title or time. Nothing was deleted.','_tools':['jinx_calendar']}
        pending={'rows':rows,'expires':now+120}
        labels=[str(i+1)+'. '+deletion.description(row) for i,row in enumerate(rows)]
        return {'reply':'Which appointment should I remove? '+'; '.join(labels)+'. Say its number or title. Nothing has been deleted.','_tools':['jinx_calendar']}
    except (ValueError,OSError,KeyError,TypeError) as error:
        pending=None
        return {'reply':'I could not prepare that deletion: '+str(error)[:250]+' Nothing was deleted.','_tools':['jinx_calendar']}
