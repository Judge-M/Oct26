"""F04 - duration and beginner-usability scheduling model.

Converts the ticket workload into per-team active time and checks it against the agreed
required duration. Human learning validation cannot be replaced by an autonomous agent,
so a rehearsal must record human active/idle observations before any duration claim.
Live rehearsal is BLOCKED here.
"""
DEFAULT_REQUIRED_ACTIVE_MINUTES = 240


def model(config):
    teams = int(config['teams'])
    tickets = int(config['tickets'])
    estimate = int(config['estimate_minutes'])
    required = int(config.get('required_active_minutes', DEFAULT_REQUIRED_ACTIVE_MINUTES))
    if teams < 1 or tickets < 1 or estimate < 1:
        raise ValueError('Teams, tickets and estimate must be positive')
    total = tickets * estimate
    per_team = total / teams
    return dict(total_team_minutes=total, per_team_available=per_team,
                required_per_team=required, gap=max(0.0, required - per_team),
                meets=per_team >= required,
                basis='arithmetic estimate; requires human rehearsal',
                cooperative=True)


def record_observations(observations):
    if not isinstance(observations, dict) or observations.get('human_rehearsal') is not True:
        raise ValueError('A human rehearsal is required; autonomous agents cannot certify learning')
    teams = observations.get('teams')
    if not isinstance(teams, list) or not teams:
        raise ValueError('Per-team active/idle observations are required')
    active = sum(entry['active_minutes'] for entry in teams)
    idle = sum(entry['idle_minutes'] for entry in teams)
    return dict(active_team_minutes=active, idle_team_minutes=idle,
                meets=active >= observations.get('required_team_minutes', DEFAULT_REQUIRED_ACTIVE_MINUTES * len(teams)),
                aar_minutes=observations.get('aar_minutes', 0), breaks_minutes=observations.get('breaks_minutes', 0))
