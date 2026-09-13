"""Validate planning configuration and derive one schedule; never retime evidence."""
import json
from datetime import datetime, timedelta
from pathlib import Path

CELLS = ['network', 'endpoint', 'identity', 'server', 'hunting']
PROFILES = {
    180: dict(brief_end=10, initial_report=25, inject_minutes=[35, 75, 115],
              response_minutes=[10, 10, 15], cell_handover=140, joint_report=150,
              investigation_end=150, aar_start=150, aar_end=175),
    120: dict(brief_end=10, initial_report=20, inject_minutes=[25, 50, 75],
              response_minutes=[10, 10, 15], cell_handover=90, joint_report=95,
              investigation_end=100, aar_start=100, aar_end=120),
}


def validate(config):
    if not isinstance(config, dict):
        raise ValueError('Configuration must be an object')
    required={'exercise_date','duration_minutes','participants','cells'}
    if required-set(config):
        raise ValueError('Missing configuration keys: '+', '.join(sorted(required-set(config))))
    allowed = {'exercise_date', 'duration_minutes', 'participants', 'cells', 'timing', 'note'}
    if set(config) - allowed:
        raise ValueError('Unknown configuration keys: ' + ', '.join(sorted(set(config)-allowed)))
    if not isinstance(config['exercise_date'],str):
        raise ValueError('exercise_date must use YYYY-MM-DD')
    datetime.strptime(config['exercise_date'], '%Y-%m-%d')
    duration = config['duration_minutes']
    if type(duration) is not int or not 60 <= duration <= 480:
        raise ValueError('duration_minutes must be an integer from 60 to 480')
    if type(config['participants']) is not int or config['participants'] < 5:
        raise ValueError('participants must be an integer of at least five')
    if config['cells'] != CELLS:
        raise ValueError('The five specialist cells must be preserved')
    supplied = config.get('timing', {})
    if not isinstance(supplied, dict) or set(supplied) - set(PROFILES[180]):
        raise ValueError('Invalid timing fields')
    timing = dict(PROFILES.get(duration, {}))
    timing.update(supplied)
    if set(timing) != set(PROFILES[180]):
        raise ValueError('Nonstandard durations require all timing fields')
    for key, value in timing.items():
        values = value if key in ('inject_minutes', 'response_minutes') else [value]
        if not isinstance(values, list) or (key in ('inject_minutes', 'response_minutes') and len(values) != 3):
            raise ValueError(f'{key} requires three integers')
        if any(type(v) is not int or not 0 <= v <= duration for v in values):
            raise ValueError(f'Invalid minutes in {key}')
    releases, windows = timing['inject_minutes'], timing['response_minutes']
    deadlines = [a+b for a,b in zip(releases, windows)]
    if any(v < minimum for v,minimum in zip(windows,[10,10,15])):
        raise ValueError('Response windows require at least 10, 10, 15 minutes')
    if not (0 < timing['brief_end'] < timing['initial_report'] < releases[0]
            < deadlines[0] < releases[1] < deadlines[1] < releases[2] < deadlines[2]
            <= timing['cell_handover'] < timing['joint_report'] <= timing['investigation_end']
            <= timing['aar_start'] < timing['aar_end'] <= duration):
        raise ValueError('Deadlines must be ordered and fit inside the event')
    return {**config, 'timing': timing}, {**timing, 'inject_deadlines': deadlines,
                                        'duration_minutes': duration}


def clock(minute):
    return (datetime(2000,1,1,9,30)+timedelta(minutes=minute)).strftime('%H:%MZ')


def markdown(schedule):
    rows = [(0, 'Incoming shift / controller starts clock'),
            (schedule['brief_end'], 'Independent investigation begins'),
            (schedule['initial_report'], 'Each cell posts initial report')]
    for i, (release, deadline) in enumerate(zip(schedule['inject_minutes'], schedule['inject_deadlines']),1):
        rows += [(release, f'Inject {i} planned release'), (deadline, f'Command response {i} due')]
    rows += [(schedule['cell_handover'], 'Five cell contributions due on ticket 5'),
             (schedule['joint_report'], 'Hunting reporter posts JOINT ASSESSMENT on ticket 5'),
             (schedule['investigation_end'], 'Investigation closes'),
             (schedule['aar_start'], 'AAR begins'), (schedule['aar_end'], 'AAR ends'),
             (schedule['duration_minutes'], 'Export / event close')]
    return '# Run schedule\n\nElapsed minutes exclude recorded pauses. Historical evidence times never change.\n' + \
           'Releases are manual; actual times and any revised deadlines are recorded in the control ledger.\n\n' + \
           '| Elapsed minute | Scenario clock | Action |\n|---|---|---|\n' + ''.join(
               f'| {minute} | {clock(minute)} | {action} |\n' for minute,action in rows)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=Path(__file__).resolve().parents[1]/'config.json')
    args=parser.parse_args()
    print(markdown(validate(json.loads(args.config.read_text()))[1]))
