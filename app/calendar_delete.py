"""Bounded Morgen deletion of one verified personal event/occurrence.

Uses exact opaque IDs from live reads, a confirmed snapshot, and an exclusive
per-event attempt journal. No model-generated ID, series deletion or auto-retry.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
import morgen_tools as morgen


def calendars():
    default=morgen.config()
    path=morgen.STATE/'morgen-readable-calendars.json'
    rows=json.loads(path.read_text()) if path.exists() else [default]
    if not isinstance(rows,list) or not rows or len(rows)>20:
        raise ValueError('Calendar selection needs checking.')
    if any(not all(isinstance(c.get(k),str) and c[k] for k in ('id','accountId','name')) for c in rows):
        raise ValueError('Calendar selection needs checking.')
    return rows


def identity(event):
    result={k:event.get(k) for k in ('id','accountId','calendarId')}
    if any(not isinstance(v,str) or not v or len(v)>8000 for v in result.values()):
        raise ValueError('Morgen did not return an exact event identity.')
    return result


def digest(event):
    keys=('id','accountId','calendarId','title','start','duration','timeZone','showWithoutTime',
          'recurrenceId','recurrenceIdTimeZone','masterEventId','recurrenceRules',
          'excludedRecurrenceRules','recurrenceOverrides','participants','replyTo','status',
          'description','locations')
    return hashlib.sha256(json.dumps({k:event.get(k) for k in keys},sort_keys=True).encode()).hexdigest()


def allowed(event):
    ident=identity(event)
    match=next((c for c in calendars() if c['accountId']==ident['accountId'] and c['id']==ident['calendarId']),None)
    if not match:raise ValueError('That event is not in a selected Morgen calendar.')
    # Meeting cancellation can notify others. Keep this first workflow personal.
    participants=event.get('participants') or {}
    own_only=isinstance(participants,dict) and all(isinstance(p,dict) and p.get('accountOwner') is True and p.get('roles')=={'owner':True} for p in participants.values())
    if not own_only or event.get('replyTo'):
        raise ValueError('This meeting has invitation details. Please cancel it in Morgen so you can review who is notified.')
    if event.get('recurrenceRules') and not event.get('recurrenceId'):
        raise ValueError('Choose a specific dated occurrence; I will not delete a whole series.')
    return match


def get(ident):
    event=morgen.api('events',{'id':ident['id']}).get('event')
    if not isinstance(event,dict) or identity(event)!=ident:
        raise ValueError('Morgen returned a different event. Nothing was deleted.')
    return event


def candidates(day):
    rows=calendars();groups={}
    for cal in rows:groups.setdefault(cal['accountId'],[]).append(cal)
    begin=dt.datetime.combine(day,dt.time(),morgen.ZONE);end=begin+dt.timedelta(days=1)
    found=[];seen=set()
    for account,group in groups.items():
        answer=morgen.api('events/list',{'accountId':account,'calendarIds':','.join(c['id'] for c in group),
                       'start':begin.isoformat(),'end':end.isoformat()})
        events=answer.get('events')
        if not isinstance(events,list) or len(events)>100:
            raise ValueError('The event list is incomplete or too large. Choose the event in Morgen.')
        names={c['id']:c['name'] for c in group}
        for event in events:
            ident=identity(event)
            if ident['accountId']!=account or ident['calendarId'] not in names:
                raise ValueError('Morgen returned an event from another calendar.')
            start,finish=morgen.times(event)
            date=start.date() if isinstance(start,dt.datetime) else start
            # Never remove a multiday event merely because it overlaps this day.
            if date!=day:continue
            key=json.dumps(ident,sort_keys=True)
            if key in seen:continue
            seen.add(key)
            found.append({'event':event,'calendar_name':names[ident['calendarId']],
                          'title':str(event.get('title','Untitled'))[:300],
                          'start':start.isoformat(),'end':finish.isoformat(),
                          'all_day':bool(event.get('showWithoutTime'))})
    return sorted(found,key=lambda row:row['start'])


def prepare(candidate):
    original=candidate['event'];event=get(identity(original))
    if digest(original)!=digest(event):
        raise ValueError('That appointment changed while I was checking it. Please ask again for a fresh review.')
    calendar=allowed(event);start,end=morgen.times(event)
    return {'event':event,'fingerprint':digest(event),'calendar_name':calendar['name'],
            'title':str(event.get('title','Untitled'))[:300], 'start':start.isoformat(),
            'end':end.isoformat(),'all_day':bool(event.get('showWithoutTime')),
            'prepared_at':time.time(),'series_mode':'single'}


def description(fields):
    when=dt.date.fromisoformat(fields['start']) if fields.get('all_day') else dt.datetime.fromisoformat(fields['start'])
    stamp=when.strftime('%A %d %B %Y')+(' (all day)' if fields.get('all_day') else when.strftime(' at %H:%M %z'))
    return fields['title']+', '+stamp+', in '+fields['calendar_name']


def summary(fields):
    return 'Delete '+description(fields)+' from Morgen? Only this appointment or occurrence will be removed. Say yes or no.'


def remove(fields,proposal_id):
    if not re.fullmatch('[a-f0-9]{16}',proposal_id) or fields.get('series_mode')!='single':
        raise ValueError('Invalid deletion proposal.')
    if not 0<=time.time()-fields.get('prepared_at',0)<=300:
        raise ValueError('That deletion preview expired. Ask again for a fresh review.')
    event=fields['event'];ident=identity(event)
    if fields.get('fingerprint')!=digest(event):raise ValueError('The deletion preview changed.')
    calendar=allowed(event)
    start,end=morgen.times(event)
    expected={'title':str(event.get('title','Untitled'))[:300], 'start':start.isoformat(),
              'end':end.isoformat(),'all_day':bool(event.get('showWithoutTime'))}
    if any(fields.get(k)!=v for k,v in expected.items()):raise ValueError('The deletion read-back details changed.')
    if calendar['name']!=fields.get('calendar_name'):raise ValueError('Calendar selection changed. Ask for a new review.')
    # Ledger key is the full account/calendar/event triple, never a parsed ID.
    key=hashlib.sha256(json.dumps(ident,sort_keys=True).encode()).hexdigest()
    folder=morgen.STATE/'calendar-deletions';folder.mkdir(mode=0o700,exist_ok=True)
    path=folder/(key+'.json')
    if path.exists():
        saved=json.loads(path.read_text())
        try:get(ident)
        except morgen.MorgenHTTPError as error:
            if error.status==404:
                return ('Deleted and verified: ' if saved.get('state')=='verified' else 'That appointment is now absent from Morgen. The earlier deletion result was uncertain: ')+description(fields)+'.'
            raise
        raise ValueError('An earlier deletion attempt needs checking. I will not repeat it automatically.')
    try:live=get(ident)
    except morgen.MorgenHTTPError as error:
        if error.status==404:return 'That appointment is already absent from Morgen. I did not delete it.'
        raise
    if digest(live)!=fields['fingerprint']:raise ValueError('The appointment changed after the read-back. Ask again to review the current event.')
    allowed(live)
    # Keep a private original-event backup before the only possible POST.
    saved={'identity':ident,'original_event':live,'proposal_id':proposal_id,'state':'attempting','at':time.time()}
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:raise ValueError('A deletion for this event is already in progress.') from None
    with os.fdopen(fd,'w') as stream:
        json.dump(saved,stream);stream.flush();os.fsync(stream.fileno())
    response=morgen.api('events/delete',{'seriesUpdateMode':'single'},body=ident)
    if response.get('http_status')!=204:raise ValueError('Morgen did not confirm deletion. I will not retry it automatically.')
    saved['state']='needs_verification';path.write_text(json.dumps(saved))
    try:get(ident)
    except morgen.MorgenHTTPError as error:
        if error.status!=404:raise
    else:raise ValueError('Morgen accepted the delete, but the event is still readable. Deletion is unverified; I will not repeat it automatically.')
    saved['state']='verified';path.write_text(json.dumps(saved))
    return 'Deleted and verified: '+description(fields)+'.'
