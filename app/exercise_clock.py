"""Project actual UTC onto the controller's pause-aware elapsed clock."""
from datetime import datetime


def elapsed_at(events, actual_utc):
    at=datetime.fromisoformat(actual_utc)
    total, anchor, started=0.0, None, False
    for event in events:
        when=datetime.fromisoformat(event['actual_utc'])
        if when > at: break
        if event['kind']=='start': started=True; anchor=when
        elif event['kind']=='pause' and anchor is not None:
            total+=(when-anchor).total_seconds(); anchor=None
        elif event['kind']=='resume': anchor=when
    if anchor is not None: total+=(at-anchor).total_seconds()
    return round(total,3) if started else None
