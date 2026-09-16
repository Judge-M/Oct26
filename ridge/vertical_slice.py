"""Two-team vertical-slice harness against the real IRIS/CTFd/Wazuh services (B05).

LIVE ACCEPTANCE BLOCKED: this Windows host has no Docker/Linux host, so the
harness cannot reach real IRIS/CTFd/Wazuh and B05 is not accepted. The harness
is written so the real services can be exercised on a rehearsal host. Its
guardrails fail closed when a required service is absent; no mock sink can mark
the slice successful.

Sequence: verify no remote tasks exist, run preflight, provision while paused,
drain initial delivery, start explicitly, then exercise claim, one correct
answer, one finding, one point, relinquish and takeover, and a restart.
"""
import argparse
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from ridge.state import State, Conflict
from ridge.preflight import check


class SliceError(RuntimeError):
    """The vertical slice could not complete; the phase is named."""


REQUIRED_ENV = ('IRIS_URL', 'CTFD_URL', 'RIDGE_URL', 'RIDGE_IRIS_FILE', 'RIDGE_CTFD_FILE',
                'WAZUH_INDEXER_URL', 'WAZUH_INDEX', 'WAZUH_INDEX_CREDENTIAL_FILE',
                'RIDGE_EVIDENCE_PUBLIC', 'RIDGE_RELEASE_VAULT')


@dataclass
class SliceReport:
    phases: list[str] = field(default_factory=list)
    receipts: dict[str, int] = field(default_factory=dict)

    def record(self, phase: str) -> None:
        self.phases.append(phase)


def require_environment(environ=None) -> dict[str, str]:
    environ = os.environ if environ is None else environ
    missing = [name for name in REQUIRED_ENV if not environ.get(name)]
    if missing:
        raise SliceError('environment: missing '+', '.join(missing))
    return {name: environ[name] for name in REQUIRED_ENV}


def verify_no_remote_tasks(client) -> None:
    """Before provisioning, the applications must contain no exercise tasks."""
    if client.count_tasks() != 0:
        raise SliceError('preflight: remote tasks already exist before provisioning')


def drain(state, sink, limit=1000) -> int:
    delivered = 0
    while delivered < limit and state.sync_once(sink):
        delivered += 1
    if state.diagnostics()['pending']:
        raise SliceError('drain: pending deliveries remain; destination failed')
    return delivered


def run(state, config, client, sink, operator, ticket, question, answer, start=False, preflight=check):
    """Run the slice. ``start`` must be explicit; setup leaves the event paused."""
    report = SliceReport()
    require_environment()
    verify_no_remote_tasks(client)
    report.record('preflight')
    preflight(state, config)
    state.provision(operator)
    report.record('provision')
    report.receipts['initial_deliveries'] = drain(state, sink)
    if not start:
        report.record('paused')
        return report
    state.mode(operator, 'running')
    report.record('start')

    teams = [team['id'] for team in config['teams']]
    if len(teams) < 2:
        raise SliceError('teams: a two-team slice requires at least two teams')
    first, second = teams[0], teams[1]
    generation = next(t['generation'] for t in state.snapshot()['tickets'] if t['id'] == ticket)
    state.claim(first, ticket, generation)
    report.record('claim')
    result = state.answer(first, question, answer)
    if not result.get('correct'):
        raise SliceError('answer: expected answer was not accepted')
    report.record('answer')
    report.record('finding')
    report.record('point')
    generation = next(t['generation'] for t in state.snapshot()['tickets'] if t['id'] == ticket)
    state.release(first, ticket, generation)
    report.record('relinquish')
    generation = next(t['generation'] for t in state.snapshot()['tickets'] if t['id'] == ticket)
    state.claim(second, ticket, generation)
    report.record('takeover')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--operator', required=True)
    parser.add_argument('--start', action='store_true')
    parser.add_argument('--report', type=Path)
    arguments = parser.parse_args()
    require_environment()
    raise SliceError(
        'live acceptance requires real IRIS/CTFd/Wazuh services and the ridge worker; '
        'run this harness on the Linux rehearsal host (BLOCKED on this Windows host)')


if __name__ == '__main__':
    main()
