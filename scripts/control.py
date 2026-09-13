"""External controller ledger. Only trusted host operators write; cells read a projection."""
import getpass
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone


def utc(value=None):
    result = datetime.fromisoformat(value) if value else datetime.now(timezone.utc)
    if result.tzinfo is None:
        raise ValueError('UTC timestamps must be timezone aware')
    return result.astimezone(timezone.utc)


def position(events, at):
    elapsed, anchor, paused = 0.0, None, False
    for event in events:
        when = utc(event['actual_utc'])
        kind = event['kind']
        if kind == 'start': anchor = when
        elif kind == 'pause':
            elapsed += (when-anchor).total_seconds(); anchor = None; paused = True
        elif kind == 'resume': anchor = when; paused = False
    if anchor is not None:
        elapsed += (at-anchor).total_seconds()
    return (round(elapsed,3) if any(e['kind']=='start' for e in events) else None), paused


def read(runtime):
    path = runtime/'control/ledger.json'
    if not path.exists():
        raise ValueError('Missing controller ledger; export the old run and initialize a new run')
    events = json.loads(path.read_text())
    if not isinstance(events, list): raise ValueError('Invalid controller ledger')
    started, paused, previous = False, False, None
    for i,event in enumerate(events,1):
        if event.get('id') != f'CTL-{i:04}' or not event.get('operator') or not event.get('host_user'):
            raise ValueError('Invalid ledger identity')
        when = utc(event['actual_utc'])
        if previous and when < previous: raise ValueError('Controller UTC moved backwards')
        expected,_ = position(events[:i-1], when)
        if event['kind']=='start': expected=0.0
        if event.get('elapsed_seconds') != expected: raise ValueError('Invalid ledger clock mapping')
        kind=event['kind']
        if kind == 'start':
            if started: raise ValueError('Clock already started')
            started=True
        elif kind=='pause':
            if not started or paused: raise ValueError('Cannot pause clock')
            paused=True
        elif kind=='resume':
            if not paused: raise ValueError('Clock is not paused')
            paused=False
        elif kind not in ('release','decision','note'):
            raise ValueError('Unknown ledger event')
        previous=when
    return events


def save(runtime, events):
    path=runtime/'control/ledger.json'
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(events,indent=2)+'\n')
    temporary.replace(path)


@contextmanager
def locked(runtime):
    path=runtime/'control.lock'
    try: fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError: raise ValueError('Another controller command is active; inspect any interrupted operation before clearing control.lock')
    try:
        os.close(fd)
        yield
    finally: path.unlink()


def append(runtime, kind, operator=None, details=None, now=None):
    events=read(runtime)
    when=utc(now)
    if events and when < utc(events[-1]['actual_utc']): raise ValueError('Controller UTC moved backwards')
    elapsed,paused=position(events,when)
    if kind=='start' and elapsed is not None: raise ValueError('Clock already started')
    if kind=='pause' and (elapsed is None or paused): raise ValueError('Cannot pause clock')
    if kind=='resume' and not paused: raise ValueError('Clock is not paused')
    if kind=='decision' and elapsed is None: raise ValueError('Start the exercise clock before decisions')
    event=dict(id=f'CTL-{len(events)+1:04}',actual_utc=when.isoformat(),
               elapsed_seconds=0.0 if kind=='start' else elapsed,kind=kind,
               operator=operator or getpass.getuser(),host_user=getpass.getuser(),details=details or {})
    events.append(event); save(runtime,events)
    return event
