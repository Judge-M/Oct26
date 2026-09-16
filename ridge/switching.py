"""F02 - automate local<->AWS switching with rollback.

Composes destination preparation, source pause/drain, a coherent backup, source
fencing, restore, readiness, endpoint switch and controlled resume. Both directions use
the same step contract. A failure rolls the completed steps back and leaves both sites
paused. A source-unreachable move uses the last completed backup and reports possible
lost work instead of claiming full continuity.
"""
from datetime import datetime, timezone

SWITCH_STEPS = ('verify_destination', 'pause_drain', 'backup', 'fence_source',
                'restore', 'readiness', 'switch_endpoint', 'resume')


class SwitchError(RuntimeError):
    """A switch step failed; the run is left safely paused."""


def _now():
    return datetime.now(timezone.utc).isoformat()


class Switch:
    def __init__(self, steps):
        missing = [name for name in SWITCH_STEPS if name not in steps]
        if missing:
            raise ValueError('Switch is missing steps: ' + ', '.join(missing))
        self.steps = steps

    def execute(self, direction, source_unreachable=False):
        completed = []
        record = dict(direction=direction, source_unreachable=source_unreachable,
                      started=_now(), lost_work=source_unreachable)
        try:
            for name in SWITCH_STEPS:
                if source_unreachable and name in ('pause_drain', 'backup'):
                    self._last_backup()
                    record['backup_source'] = 'last-completed'
                    continue
                self.steps[name]()
                completed.append(name)
        except SwitchError:
            self._rollback(completed)
            raise
        record['completed'] = completed
        record['recovery_point'] = self._recovery_point()
        record['finished'] = _now()
        return record

    def _last_backup(self):
        backup = self.steps.get('last_backup')
        if not backup:
            raise SwitchError('Source is unreachable and no completed backup exists')
        return backup()

    def _recovery_point(self):
        point = self.steps.get('recovery_point')
        return point() if point else None

    def _rollback(self, completed):
        for name in reversed(completed):
            rollback = self.steps.get('rollback_' + name)
            if rollback:
                rollback()


def plan_directions(current, target):
    if current not in ('local', 'aws') or target not in ('local', 'aws'):
        raise ValueError('Only local and aws directions are supported')
    if current == target:
        raise ValueError('Source and destination must differ')
    return dict(direction=f'{current}->{target}', source=current, destination=target)
