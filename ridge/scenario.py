"""Shared incident calendar, release contract, and source-specific clock semantics."""
from datetime import date, datetime, timedelta, timezone

RELEASE_FILES = {
    'T07': ['identity/late-auth.csv'],
    'T09': ['server/version-comparison.csv'],
    'T11': ['hunting/late-inventory.csv'],
    'T19': ['network/dlp-body.txt', 'network/dlp-metadata.json'],
}
DEVICE_OFFSETS = {'WS-17': 120}
TIMELESS_SOURCES = {'hunting/coverage.csv', 'server/catalog.csv', 'server/version-comparison.csv'}

# An Autopsy question's evidence reference is a released source under /evidence; its
# case entrypoint is the writable prepared case on the team desktop. The two must not
# be conflated: /evidence is read-only and never holds the .aut case database.
AUTOPSY_CASE_ENTRYPOINT = '~/Cases/WS17/WS17.aut'
AUTOPSY_CASE_TEMPLATE = '/opt/silent-ridge/prepared-case/WS17'
ORIGINALS_MOUNT = '/originals'


def incident_day(value):
    return date.fromisoformat(value).isoformat()


def timestamp(row, source):
    """Do not invent occurrence times for catalog/coverage facts."""
    for field in ('time', 'observed', 'start_time_utc', 'utc', 'device_time'):
        if field not in row:
            continue
        stamp = datetime.fromisoformat(row[field])
        if stamp.tzinfo is None:
            raise ValueError('Timezone required: '+source)
        if field == 'device_time':
            if row.get('host') not in DEVICE_OFFSETS:
                raise ValueError('Unknown device clock: '+source)
            stamp -= timedelta(seconds=DEVICE_OFFSETS[row['host']])
        return stamp.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    if source in TIMELESS_SOURCES:
        return None
    raise ValueError('Unknown timestamp schema: '+source)


def telemetry_record(row, source):
    stamp = timestamp(row, source)
    result = dict(observation='synthetic historical replay', data=dict(row, source=source))
    if stamp is not None:
        result['timestamp'] = stamp
    else:
        result['timeless'] = True
    return result
