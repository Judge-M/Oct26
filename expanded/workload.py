"""Ten-team workload inventory and rehearsal worksheet.

Reads the authored tickets and emits a deterministic inventory plus a blank
rehearsal worksheet. Every figure here is planning arithmetic derived from the
authored ``estimate_minutes``; none of it is a measurement. The worksheet exists to
replace those estimates with observed active/idle time, help use and tool failures.

Run from the repository root::

    python expanded/workload.py --teams 10 --target-minutes 240 \
        --output docs/workload.md --worksheet docs/rehearsal-worksheet.md
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from expanded.author import build

DEFAULT_TEAMS = 10
DEFAULT_TARGET_MINUTES = 240
YES_NO = {'yes', 'no'}


def inventory(tickets):
    """One deterministic row per authored ticket."""
    rows = []
    for ticket in sorted(tickets, key=lambda t: t['id']):
        questions = ticket['questions']
        walkthroughs = sum(
            1 for question in questions
            if any(str(hint).startswith('Walkthrough:') for hint in question.get('hints', [])))
        rows.append({
            'id': ticket['id'],
            'requires': list(ticket.get('requires', [])),
            'tool': ticket['subject'],
            'questions': len(questions),
            'release_files': list(ticket.get('release_files', [])),
            'minutes': int(ticket.get('estimate_minutes', 0)),
            'free_walkthroughs': walkthroughs,
        })
    return rows


def repeated_answers(tickets):
    """Questions whose answer text is also the answer to another question."""
    seen = {}
    repeats = []
    for ticket in sorted(tickets, key=lambda t: t['id']):
        for question in ticket['questions']:
            key = question['answer'].strip().casefold()
            if key in seen:
                repeats.append({'answer': question['answer'], 'question': question['id'],
                                'also': seen[key]})
            else:
                seen[key] = question['id']
    return repeats


def yes_no_questions(tickets):
    """Questions whose entire answer is yes/no, which can be guessed."""
    return [question['id'] for ticket in sorted(tickets, key=lambda t: t['id'])
            for question in ticket['questions']
            if question['answer'].strip().casefold() in YES_NO]


def critical_path(tickets):
    """Longest dependency chain by estimated minutes, and the tickets on it."""
    by_id = {t['id']: t for t in tickets}
    best = {}

    def longest(ticket_id):
        if ticket_id in best:
            return best[ticket_id]
        ticket = by_id[ticket_id]
        predecessor = None
        for required in ticket.get('requires', []):
            candidate = longest(required)
            if predecessor is None or candidate[0] > predecessor[0]:
                predecessor = candidate
        minutes = int(ticket.get('estimate_minutes', 0))
        if predecessor is None:
            best[ticket_id] = (minutes, [ticket_id])
        else:
            best[ticket_id] = (minutes + predecessor[0], predecessor[1] + [ticket_id])
        return best[ticket_id]

    if not by_id:
        return 0, []
    return max((longest(ticket_id) for ticket_id in by_id), key=lambda entry: entry[0])


def schedule(tickets, teams=DEFAULT_TEAMS):
    """Deterministic list schedule: one globally owned ticket per team at a time.

    Available tickets are claimed in ID order by the lowest-numbered idle team.
    Returns the makespan, the per-team assignment and the completion timeline.
    """
    if teams < 1:
        raise ValueError('teams must be positive')
    by_id = {t['id']: t for t in tickets}
    remaining = set(by_id)
    completed = set()
    free = list(range(teams))
    active = {}
    timeline = []
    now = 0
    while remaining or active:
        available = sorted(ticket_id for ticket_id in remaining
                           if set(by_id[ticket_id].get('requires', [])) <= completed)
        while available and free:
            ticket_id = available.pop(0)
            team = free.pop(0)
            duration = int(by_id[ticket_id].get('estimate_minutes', 0))
            active[team] = (ticket_id, now + duration)
            remaining.discard(ticket_id)
        if not active:
            raise ValueError('Cyclic or unsatisfiable ticket dependencies')
        now = min(end for _, end in active.values())
        for team, (ticket_id, end) in list(active.items()):
            if end == now:
                completed.add(ticket_id)
                free.append(team)
                del active[team]
                timeline.append({'minute': now, 'team': team, 'ticket': ticket_id})
        free.sort()
    per_team = {}
    for event in timeline:
        entry = per_team.setdefault(event['team'], {'tickets': [], 'minutes': 0})
        entry['tickets'].append(event['ticket'])
        entry['minutes'] += int(by_id[event['ticket']].get('estimate_minutes', 0))
    return {'teams': teams, 'makespan': now, 'timeline': timeline, 'per_team': per_team}


def summary(tickets, teams=DEFAULT_TEAMS, target_minutes=DEFAULT_TARGET_MINUTES):
    rows = inventory(tickets)
    total_minutes = sum(row['minutes'] for row in rows)
    path_minutes, path_tickets = critical_path(tickets)
    simulation = schedule(tickets, teams)
    return {
        'teams': teams,
        'target_minutes': target_minutes,
        'tickets': len(rows),
        'questions': sum(row['questions'] for row in rows),
        'estimated_team_minutes': total_minutes,
        'average_team_minutes': round(total_minutes / teams, 1),
        'critical_path_minutes': path_minutes,
        'critical_path_tickets': path_tickets,
        'makespan_minutes': simulation['makespan'],
        'per_team': simulation['per_team'],
        'free_walkthroughs': sum(row['free_walkthroughs'] for row in rows),
        'repeated_answers': repeated_answers(tickets),
        'yes_no_questions': yes_no_questions(tickets),
        'rows': rows,
    }


def render_inventory(tickets, teams=DEFAULT_TEAMS, target_minutes=DEFAULT_TARGET_MINUTES):
    data = summary(tickets, teams, target_minutes)
    lines = [
        '# Ten-team workload inventory',
        '',
        'Generated by `expanded/workload.py` from `expanded/author.py`. Every figure '
        'below is planning arithmetic, not a measurement; use the rehearsal worksheet '
        'to replace it with observed data.',
        '',
        '## Ticket inventory',
        '',
        '| Ticket | Prerequisites | Tool | Questions | Release files | Estimated minutes |',
        '|---|---|---|---|---|---|',
    ]
    for row in data['rows']:
        lines.append('| {id} | {requires} | {tool} | {questions} | {releases} | {minutes} |'.format(
            id=row['id'], requires=', '.join(row['requires']) or '-', tool=row['tool'],
            questions=row['questions'], releases=', '.join(row['release_files']) or '-',
            minutes=row['minutes']))
    lines += [
        '',
        '## Aggregate',
        '',
        '- Tickets: {tickets}'.format(**data),
        '- Questions: {questions}'.format(**data),
        '- Estimated team-minutes: {estimated_team_minutes}'.format(**data),
        '- Ten-team arithmetic average: {average_team_minutes} minutes/team'.format(**data),
        '- Longest dependency chain (critical path): {critical_path_minutes} minutes ({path})'.format(
            path=' -> '.join(data['critical_path_tickets']), **data),
        '- Simulated makespan with {teams} teams: {makespan_minutes} minutes'.format(**data),
        '- Configurable duration target: {target_minutes} minutes'.format(**data),
        '',
        'The ten-team average of {average_team_minutes} minutes/team is a quotient, not a '
        'plan. The dependency chain and the limited number of initially available tickets '
        'push the simulated makespan to {makespan_minutes} minutes, and free walkthroughs '
        'reduce the unaided work below the estimate. Neither number demonstrates four hours '
        'of meaningful activity per team; only a beginner rehearsal can.'.format(**data),
        '',
        '## Per-team participation (simulated)',
        '',
        '| Team | Tickets | Estimated minutes |',
        '|---|---|---|',
    ]
    for team in range(teams):
        entry = data['per_team'].get(team, {'tickets': [], 'minutes': 0})
        lines.append('| team-{number:02} | {tickets} | {minutes} |'.format(
            number=team + 1, tickets=', '.join(entry['tickets']) or '-', minutes=entry['minutes']))
    lines += [
        '',
        '## Free walkthroughs and duplicate or superficial questions',
        '',
        '- Walkthrough hints containing the answer: {free_walkthroughs} of {questions}. '
        'Free hints and walkthroughs support coached practice and reduce unaided active time.'.format(**data),
        '- Repeated answers (same value asked by more than one question): {count}.'.format(
            count=len(data['repeated_answers'])),
        '- Yes/no questions that can be guessed: {count}.'.format(count=len(data['yes_no_questions'])),
        '',
        '### Repeated answers',
        '',
        '| Answer | Question | Also asked by |',
        '|---|---|---|',
    ]
    for repeat in data['repeated_answers']:
        lines.append('| {answer} | {question} | {also} |'.format(**repeat))
    if not data['repeated_answers']:
        lines.append('| - | - | - |')
    lines += [
        '',
        '### Yes/no questions',
        '',
        ', '.join(data['yes_no_questions']) if data['yes_no_questions'] else 'None.',
        '',
        '## Scheduling assumptions',
        '',
        '- One global owner per ticket; a team works one claimed ticket at a time.',
        '- Tickets unlock only when every prerequisite ticket is complete.',
        '- Tickets are claimed in ID order by the lowest-numbered idle team; no preemption.',
        '- Estimates use the authored 65-minute allowance and exclude orientation, breaks, '
        'help-seeking and the after-action review.',
        '- Ten teams / thirty participants; one shared desktop per team.',
        '',
    ]
    return '\n'.join(lines)


def render_worksheet(tickets, teams=DEFAULT_TEAMS, target_minutes=DEFAULT_TARGET_MINUTES):
    data = summary(tickets, teams, target_minutes)
    lines = [
        '# Ten-team rehearsal worksheet',
        '',
        'Record observations here during a beginner rehearsal. Estimated columns come from '
        '`docs/workload.md` and are arithmetic; the measured columns are the evidence.',
        '',
        'Duration target: {target_minutes} minutes. Estimated makespan: {makespan_minutes} minutes. '
        'Estimated team-minutes: {estimated_team_minutes} ({average_team_minutes}/team).'.format(**data),
        '',
        '## Per-team summary',
        '',
        '| Team | Estimated tickets | Estimated minutes | Active minutes | Idle minutes | Help used | Tool failures | Notes |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for team in range(teams):
        entry = data['per_team'].get(team, {'tickets': [], 'minutes': 0})
        lines.append('| team-{number:02} | {tickets} | {minutes} | | | | | |'.format(
            number=team + 1, tickets=', '.join(entry['tickets']) or '-', minutes=entry['minutes']))
    lines += [
        '',
        '## Per-ticket observations',
        '',
        '| Ticket | Tool | Prerequisites | Estimated minutes | Team | Start | End | Active | Idle | Help used | Tool failures | Blocked by |',
        '|---|---|---|---|---|---|---|---|---|---|---|---|',
    ]
    for row in data['rows']:
        lines.append('| {id} | {tool} | {requires} | {minutes} | | | | | | | | |'.format(
            id=row['id'], tool=row['tool'], requires=', '.join(row['requires']) or '-',
            minutes=row['minutes']))
    lines += [
        '',
        '## Rehearsal questions',
        '',
        '- Did measured active time per team reach the duration target?',
        '- Which dependencies stalled teams, and for how long?',
        '- Which questions were answered from a free walkthrough without investigation?',
        '- Which duplicate or yes/no questions should be replaced or deepened?',
        '- Which tool instructions failed, and what is the observable fix?',
        '',
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--teams', type=int, default=DEFAULT_TEAMS)
    parser.add_argument('--target-minutes', type=int, default=DEFAULT_TARGET_MINUTES)
    parser.add_argument('--output', type=Path, default=Path('docs/workload.md'))
    parser.add_argument('--worksheet', type=Path, default=Path('docs/rehearsal-worksheet.md'))
    parser.add_argument('--config', type=Path, default=Path('expanded/config.json'))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8')) if args.config.exists() else None
    tickets = build(config)
    args.output.write_text(render_inventory(tickets, args.teams, args.target_minutes), encoding='utf-8')
    args.worksheet.write_text(render_worksheet(tickets, args.teams, args.target_minutes), encoding='utf-8')
    data = summary(tickets, args.teams, args.target_minutes)
    print(json.dumps({key: data[key] for key in
                      ('tickets', 'questions', 'estimated_team_minutes', 'average_team_minutes',
                       'critical_path_minutes', 'makespan_minutes', 'target_minutes')}, indent=2))


if __name__ == '__main__':
    main()
