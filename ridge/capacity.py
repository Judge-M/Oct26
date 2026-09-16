"""F03 - ten-team capacity scenario and measured-result acceptance.

Defines the repeatable load scenario and evaluates measured results against explicit
targets. Live load generation requires the deployed stack and is BLOCKED here; the
scenario definition and the acceptance evaluator are deterministic and tested. Capacity
is never certified from `docker stats` alone or from a synthetic answer loop.
"""
DEFAULT_TARGETS = dict(app_p95_seconds=2.0, score_delivery_p95_seconds=10.0,
                       capacity_reserve_fraction=0.20)
MEASUREMENT_KEYS = ('app_p95_seconds', 'score_delivery_p95_seconds', 'cpu_percent',
                    'memory_percent', 'swap_used_mib', 'capacity_reserve_fraction',
                    'oom_events', 'desktop_sessions')


def scenario(teams=10, participants=30, desktops=10):
    if teams < 1 or desktops < 1:
        raise ValueError('At least one team and desktop are required')
    return dict(teams=teams, participants=participants, desktops=desktops,
                activities=('case_open', 'keyword_search', 'network_capture', 'static_analysis', 'scoring'),
                authenticated_browser_sessions=participants)


def evaluate(measurements, targets=None):
    targets = dict(DEFAULT_TARGETS, **(targets or {}))
    missing = [key for key in MEASUREMENT_KEYS if key not in measurements]
    if missing:
        raise ValueError('Measurements are incomplete: ' + ', '.join(missing))
    failures = []
    if measurements['app_p95_seconds'] > targets['app_p95_seconds']:
        failures.append('app p95 exceeds target')
    if measurements['score_delivery_p95_seconds'] > targets['score_delivery_p95_seconds']:
        failures.append('score delivery p95 exceeds target')
    if measurements['capacity_reserve_fraction'] < targets['capacity_reserve_fraction']:
        failures.append('capacity reserve below target')
    if measurements['oom_events'] > 0 or measurements['swap_used_mib'] > 0:
        failures.append('memory pressure or swap detected')
    return dict(passed=not failures, failures=failures, targets=targets,
                measurements=dict(measurements), evidence='measured' if measurements.get('measured') else 'reported')


def require_supported_host(host):
    if not isinstance(host, dict) or host.get('supported') is not True:
        raise ValueError('Host profile is unsupported; capacity cannot be certified')
    return host
