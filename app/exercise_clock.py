"""Project actual UTC onto the controller's pause-aware elapsed clock.

Single source of truth for the clock mapping: the participant service, the
controller CLI and the facilitator panel all project elapsed time through
``project`` so their values cannot drift apart.
"""
from datetime import datetime


def project(events, actual_utc):
    """Return (elapsed_seconds, paused) for a point on the actual UTC timeline.

    Events are applied in ledger order. ``elapsed_seconds`` is ``None`` until a
    start event has occurred. ``paused`` reports whether the clock is currently
    paused at the requested instant.
    """
    at = datetime.fromisoformat(actual_utc) if isinstance(actual_utc, str) else actual_utc
    total, anchor, started, paused = 0.0, None, False, False
    for event in events:
        when = datetime.fromisoformat(event['actual_utc'])
        if when > at:
            break
        kind = event['kind']
        if kind == 'start':
            started, anchor, paused = True, when, False
        elif kind == 'pause' and anchor is not None:
            total += (when - anchor).total_seconds()
            anchor, paused = None, True
        elif kind == 'resume':
            anchor, paused = when, False
    if anchor is not None:
        total += (at - anchor).total_seconds()
    return (round(total, 3) if started else None), paused


def elapsed_at(events, actual_utc):
    """Elapsed seconds at ``actual_utc``, or ``None`` before the clock starts."""
    return project(events, actual_utc)[0]
