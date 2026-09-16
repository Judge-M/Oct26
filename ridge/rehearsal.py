"""F06 - event dress rehearsal and recovery drill record.

Enumerates the phases that must be executed on designated event hardware and refuses to
freeze a candidate release while any phase is missing, failed or blocked. The rehearsal
itself requires the deployed stack and is BLOCKED here; the record and gate logic is
deterministic and tested.
"""
PHASES = ('cold_setup', 'repeat_up', 'participant_sessions', 'dependency_flow',
          'pause_resume', 'reconnect', 'provider_switch', 'export', 'teardown', 'lost_host')


def record(results):
    missing = [phase for phase in PHASES if phase not in results]
    return dict(phases=results, missing=missing, complete=not missing,
                exceptions=[dict(phase=phase, reason=value.get('reason'))
                            for phase, value in sorted(results.items())
                            if value.get('status') == 'blocked'])


def freeze(results):
    document = record(results)
    if document['missing']:
        raise ValueError('Rehearsal is incomplete; missing phases: ' + ', '.join(document['missing']))
    failed = sorted(phase for phase, value in results.items() if value.get('status') != 'pass')
    if failed:
        raise ValueError('Cannot freeze with non-passing phases: ' + ', '.join(failed))
    return dict(frozen=True, phases=sorted(results), rto_seconds=results.get('lost_host', {}).get('rto_seconds'),
                rpo_seconds=results.get('lost_host', {}).get('rpo_seconds'),
                remaining_billable=results.get('teardown', {}).get('remaining_billable', []))
