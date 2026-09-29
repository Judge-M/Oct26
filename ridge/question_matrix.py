"""Build and validate the 80-question acceptance matrix (C04).

Each row records the actual evidence path, tool selection/query, expected value,
source record and limitation so every question has a reproducible route on the
installed desktop release. Tool launch, evidence availability and answer
correctness are separate assertions.

LIVE ACCEPTANCE BLOCKED: screenshots/structured evidence for each distinct tool
workflow require the real desktop release, which cannot run on this host. The
matrix, route derivation and the T13/T14/T16 clock/claim guards are deterministic.
"""
import hashlib
import json
from pathlib import Path

EXPECTED_QUESTIONS = 80
NATIVE = Path(__file__).resolve().parents[1] / 'assets/native-windows-v1/manifest.json'


class MatrixError(ValueError):
    """Raised when the question matrix is incomplete or inconsistent."""


def _rows(tickets):
    rows = []
    for ticket in tickets:
        for question in ticket['questions']:
            rows.append({
                'question_id': question['id'],
                'ticket': ticket['id'],
                'title': ticket['title'],
                'tool': question['tool'],
                'evidence_path': question['evidence'],
                'selection': question.get('selection', ''),
                'expected_value': question['answer'],
                'source_record': question.get('source_record', question['evidence'].removeprefix('/evidence/')),
                'limitation': question['finding']['limitation'],
                'finding_text': question['finding']['text'],
                'route': ' > '.join(question['steps']),
            })
    return rows


def validate(rows) -> None:
    if len(rows) != EXPECTED_QUESTIONS:
        raise MatrixError('questions: expected %d rows but found %d' % (EXPECTED_QUESTIONS, len(rows)))
    ids = [row['question_id'] for row in rows]
    if len(set(ids)) != len(ids):
        raise MatrixError('question_id: duplicate question in the matrix')
    for row in rows:
        for field in ('ticket', 'tool', 'evidence_path', 'selection', 'expected_value',
                      'source_record', 'limitation', 'finding_text', 'route'):
            if not str(row.get(field, '')).strip():
                raise MatrixError('%s: %s is empty' % (row['question_id'], field))
        if not row['evidence_path'].startswith('/evidence/'):
            raise MatrixError('%s: evidence_path must be an explicit /evidence path' % row['question_id'])
        if not row['route']:
            raise MatrixError('%s: no reproducible tool route' % row['question_id'])


def _native_manifest():
    return json.loads(NATIVE.read_text(encoding='utf-8'))


def clock_guards(rows, tickets=None) -> dict:
    """T13/T14 use actual acquisition UTC; no historic correction is applied.

    T16 is the acquired live connection snapshot and must never claim a validated
    memory connection.
    """
    from expanded.native import records
    native = records()
    process_time = native['windows-process']['utc'][11:19]
    task_time = native['windows-task']['utc'][11:19]
    by_id = {row['question_id']: row for row in rows}
    t13 = [row for row in rows if row['ticket'] == 'T13']
    t14 = [row for row in rows if row['ticket'] == 'T14']
    if process_time not in {row['expected_value'] for row in t13}:
        raise MatrixError('T13: acquisition UTC answer is missing or shifted')
    if task_time not in {row['expected_value'] for row in t14}:
        raise MatrixError('T14: acquisition UTC answer is missing or shifted')
    if not any('no historic clock correction applies' in row['finding_text'] for row in t13):
        raise MatrixError('T13: finding must state no historic clock correction applies')
    if not any('must not be rewritten' in row['finding_text'] for row in t14):
        raise MatrixError('T14: finding must forbid rewriting acquisition time')
    manifest = _native_manifest()
    if manifest.get('memory_connection_validated') is not False:
        raise MatrixError('T16: memory_connection_validated must remain false')
    if manifest.get('live_connection_snapshot_validated') is not True:
        raise MatrixError('T16: the live connection snapshot must be the validated record')
    t16 = [row for row in rows if row['ticket'] == 'T16']
    if not any('not a validated memory connection' in row['finding_text'] for row in t16):
        raise MatrixError('T16: finding must deny memory-connection validation')
    return {'t13_acquisition_utc': process_time, 't14_acquisition_utc': task_time,
            'memory_connection_validated': False, 'live_connection_snapshot_validated': True,
            't16_rows': len(t16)}


def build(tickets=None) -> list[dict]:
    if tickets is None:
        from expanded.author import build as author
        tickets = author()
    rows = _rows(tickets)
    validate(rows)
    clock_guards(rows)
    return rows


def render_markdown(rows) -> str:
    header = ('| Question | Ticket | Tool | Evidence path | Selection / query | Expected value | '
              'Source record | Limitation |')
    divider = '|---|---|---|---|---|---|---|---|'
    lines = [header, divider]
    for row in rows:
        lines.append('| %s | %s | %s | `%s` | %s | %s | `%s` | %s |' % (
            row['question_id'], row['ticket'], row['tool'], row['evidence_path'], row['selection'],
            row['expected_value'], row['source_record'], row['limitation']))
    return '\n'.join(lines) + '\n'


def guide_inventory(matrix_rows, guides_path) -> dict:
    guides = Path(guides_path)
    if not guides.is_file():
        raise MatrixError('guides: guide file not found at '+str(guides))
    return {'questions': len(matrix_rows), 'guides_sha256': hashlib.sha256(guides.read_bytes()).hexdigest(),
            'matrix_sha256': hashlib.sha256(render_markdown(matrix_rows).encode()).hexdigest()}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    rows = build()
    arguments.out.write_text(render_markdown(rows), encoding='utf-8')
    print(json.dumps(guide_inventory(rows, Path(__file__).resolve().parents[1] / 'expanded/guides.md'), indent=2))
