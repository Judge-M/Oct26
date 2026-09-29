"""Scripted full-content walkthrough for F04 duration evidence.

Drives every ticket/question in dependency order through the real mutation
paths (`State.claim` / `State.answer`) against a live provisioned stack,
recording per-question bot active time and verifying that native effects
(points, findings, ticket closures, prerequisite unlocks) drain through the
integration worker.

This is a bot: timings are an upper-bound sanity signal for broken tasks and
a floor for content volume, NOT human duration evidence (F04 acceptance
requires a beginner rehearsal for that). Results are labeled accordingly.

Usage:
    PYTHONPATH=. python -m expanded.walkthrough \
        --state work/n5-restore/state/state.sqlite \
        --tickets expanded/tickets.json \
        --report work/f04-walkthrough.json
"""
import argparse
import json
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict

from ridge.state import State, Conflict


class WalkthroughError(RuntimeError):
    """A task is broken: the phase and ticket/question name it."""


def topological_order(tickets: list[dict]) -> list[dict]:
    """Dependency order over the authored ticket list (ID order within a level)."""
    by_id = {t['id']: t for t in tickets}
    done, order = set(), []
    remaining = list(tickets)
    while remaining:
        progressed = False
        for t in list(remaining):
            reqs = t.get('requires') or t.get('prerequisites') or []
            if all(r in done for r in reqs):
                order.append(t)
                done.add(t['id'])
                remaining.remove(t)
                progressed = True
        if not progressed:
            raise WalkthroughError('dependency cycle among ' + ','.join(t['id'] for t in remaining))
    return order


def wait_drained(state_path, timeout=120.0, interval=2.0) -> int:
    """Poll the outbox until the integration worker has delivered everything."""
    deadline = time.monotonic() + timeout
    while True:
        con = sqlite3.connect(state_path)
        pending = con.execute('SELECT COUNT(*) FROM outbox WHERE done=0').fetchone()[0]
        con.close()
        if pending == 0:
            return 0
        if time.monotonic() > deadline:
            raise WalkthroughError(f'drain: {pending} deliveries still pending after {timeout}s')
        time.sleep(interval)


@dataclass
class WalkthroughReport:
    bot: bool = True
    note: str = ('Bot walkthrough timings are content-volume/broken-task evidence only; '
                 'human duration requires the beginner rehearsal (F04).')
    started: str = ''
    elapsed_seconds: float = 0.0
    tickets: list = field(default_factory=list)
    questions_answered: int = 0
    questions_previously_solved: int = 0
    wrong_answers: list = field(default_factory=list)
    broken: list = field(default_factory=list)


def run_walkthrough(state: State, tickets_path, report: WalkthroughReport,
                    team='team-01', drain_timeout=120.0) -> WalkthroughReport:
    authored = json.loads(open(tickets_path, encoding='utf-8').read())
    order = topological_order(authored)
    for ticket in order:
        tid = ticket['id']
        t0 = time.monotonic()
        snap = state.snapshot()
        row = next((t for t in snap['tickets'] if t['id'] == tid), None)
        if row is None:
            # Locked tickets do not appear in snapshot(); read status directly.
            con = sqlite3.connect(state.path)
            status = con.execute('SELECT status FROM tickets WHERE id=?', (tid,)).fetchone()[0]
            con.close()
            if status != 'complete':
                raise WalkthroughError(f'{tid}: not unlocked after prerequisites completed (status {status})')
            report.tickets.append({'ticket': tid, 'status': 'already-complete'})
            continue
        if row['status'] == 'complete':
            report.tickets.append({'ticket': tid, 'status': 'already-complete'})
            continue
        if row['status'] != 'available':
            raise WalkthroughError(f"{tid}: expected available, got {row['status']}")
        # Unlock and IRIS task creation are asynchronous: a freshly unlocked
        # ticket is 'available' with iris_id NULL until the worker delivers it.
        # Drain the outbox, then retry the claim while it settles.
        claimed = False
        for _ in range(30):
            try:
                row = next(t for t in state.snapshot()['tickets'] if t['id'] == tid)
                state.claim(team, tid, generation=row['generation'])
                claimed = True
                break
            except Conflict:
                wait_drained(state.path, timeout=drain_timeout)
        if not claimed:
            raise WalkthroughError(f'{tid}: claim never became deliverable in IRIS')
        entry = {'ticket': tid, 'status': 'walked', 'questions': [],
                 'bot_seconds': 0.0}
        for q in ticket['questions']:
            q0 = time.monotonic()
            try:
                result = state.answer(team, q['id'], q['answer'])
            except Conflict:
                entry['questions'].append({'question': q['id'], 'result': 'previously-solved'})
                report.questions_previously_solved += 1
                continue
            dt = time.monotonic() - q0
            if not result.get('correct'):
                report.wrong_answers.append(q['id'])
                entry['questions'].append({'question': q['id'], 'result': 'REJECTED',
                                           'seconds': round(dt, 3)})
                raise WalkthroughError(f"{q['id']}: authored answer was rejected")
            entry['questions'].append({'question': q['id'], 'result': 'correct',
                                       'seconds': round(dt, 3), 'closed': result['closed']})
            report.questions_answered += 1
        entry['bot_seconds'] = round(time.monotonic() - t0, 2)
        # Every ticket must end complete (all four answers accepted across runs).
        wait_drained(state.path, timeout=drain_timeout)
        con = sqlite3.connect(state.path)
        status = con.execute('SELECT status FROM tickets WHERE id=?', (tid,)).fetchone()[0]
        con.close()
        if status != 'complete':
            raise WalkthroughError(f'{tid}: status {status} after answering all questions')
        report.tickets.append(entry)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True)
    parser.add_argument('--tickets', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--team', default='team-01')
    args = parser.parse_args(argv)

    state = State(args.state)
    if state.snapshot()['mode'] != 'running':
        print('exercise is not running; start it first', file=sys.stderr)
        return 2

    report = WalkthroughReport(started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    t0 = time.monotonic()
    try:
        run_walkthrough(state, args.tickets, report, team=args.team)
        wait_drained(args.state)
    except WalkthroughError as exc:
        report.broken.append(str(exc))
        with open(args.report, 'w', encoding='utf-8') as fh:
            json.dump(asdict(report), fh, indent=2)
        print('WALKTHROUGH BROKEN:', exc, file=sys.stderr)
        return 1
    report.elapsed_seconds = round(time.monotonic() - t0, 1)
    with open(args.report, 'w', encoding='utf-8') as fh:
        json.dump(asdict(report), fh, indent=2)
    print(json.dumps({'answered': report.questions_answered,
                      'previously_solved': report.questions_previously_solved,
                      'elapsed_seconds': report.elapsed_seconds,
                      'tickets': len(report.tickets)}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
