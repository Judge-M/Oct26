"""H01b - package a closed Autopsy case and its released evidence.

Accepts an already-closed case plus an evidence directory, verifies database
integrity, complete ingest and a saved keyword index, then emits a versioned archive
and manifest. Active/unclean cases and existing destinations are refused.
"""
import argparse
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from contextlib import closing
from pathlib import Path

from ridge.artifacts import sha256

ACTIVE_SUFFIXES = ('-journal', '-wal', '-shm')
INGEST_COMPLETE = 2
DEFAULT_VERSION = 'WS17-prepared-case-v3'


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def inspect_case(case_dir):
    case_dir = Path(case_dir)
    if not case_dir.is_dir():
        raise ValueError('Case directory not found: ' + str(case_dir))
    auts = list(case_dir.glob('*.aut'))
    if len(auts) != 1:
        raise ValueError('Expected exactly one .aut case file')
    database = case_dir / 'autopsy.db'
    if not database.is_file():
        raise ValueError('Case is missing autopsy.db')
    for suffix in ACTIVE_SUFFIXES:
        if (case_dir / ('autopsy.db' + suffix)).exists():
            raise ValueError('Case is active or unclean; close it before packaging')
    try:
        connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
    except sqlite3.Error as error:
        raise ValueError('Cannot open case database read-only') from error
    with closing(connection):
        try:
            if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('Case database failed integrity verification')
            jobs = connection.execute('SELECT status_id FROM ingest_jobs').fetchall()
            if not jobs or any(row[0] != INGEST_COMPLETE for row in jobs):
                raise ValueError('Both evidence sources must have completed ingest')
            records = connection.execute('SELECT count(*) FROM tsk_files').fetchone()[0]
        except sqlite3.DatabaseError as error:
            raise ValueError('Case database is unreadable or corrupt') from error
    if records < 1:
        raise ValueError('Case has no indexed files')
    if not list((case_dir / 'ModuleOutput/keywordsearch').rglob('segments_*')):
        raise ValueError('Saved keyword index is missing')
    return dict(case_name=case_dir.name, case_file=auts[0].name, database=database,
                data_sources=len(jobs), case_file_records=records)


def _evidence_inventory(evidence):
    evidence = Path(evidence)
    if not evidence.is_dir():
        raise ValueError('Evidence directory not found: ' + str(evidence))
    if (evidence / 'controller').exists():
        raise ValueError('Supply only the released initial evidence directory')
    return [dict(path=path.relative_to(evidence).as_posix(), bytes=path.stat().st_size,
                 sha256=sha256(path)) for path in sorted(evidence.rglob('*')) if path.is_file()]


def package(case_dir, evidence_dir, destination, manifest_path, version=DEFAULT_VERSION,
            autopsy='4.22.0', sleuthkit='4.13.0'):
    destination, manifest_path = Path(destination), Path(manifest_path)
    if destination.exists():
        raise ValueError('Choose a new case archive; existing releases are never overwritten')
    if manifest_path.exists():
        raise ValueError('Choose a new case manifest; existing manifests are never overwritten')
    case = inspect_case(case_dir)
    files = _evidence_inventory(evidence_dir)
    evidence = Path(evidence_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.case-', suffix='.tar.gz', dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        with tarfile.open(temporary, 'w:gz') as archive:
            archive.add(Path(case_dir), arcname='cases/' + case['case_name'])
            archive.add(evidence, arcname='evidence')
        manifest = dict(schema=1, version=version, artifact=destination.name,
                        bytes=temporary.stat().st_size, sha256=sha256(temporary),
                        autopsy=autopsy, sleuthkit=sleuthkit,
                        case_path=f"cases/{case['case_name']}/{case['case_file']}",
                        evidence_mount='/evidence', data_sources=case['data_sources'],
                        case_file_records=case['case_file_records'], database_integrity='ok',
                        ingest_complete=True, saved_keyword_index=True,
                        logical_evidence=True,
                        native_disk_included=any(f['path'].startswith('disk/') for f in files),
                        native_windows_records_included=(evidence / 'prepared/memory-processes.json').is_file(),
                        native_windows_memory_included=False, event_ready=False, evidence_files=files)
        os.replace(temporary, destination)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return manifest


def verify(destination, manifest_path):
    destination, manifest_path = Path(destination), Path(manifest_path)
    manifest = _read_json(manifest_path)
    if manifest.get('schema') != 1 or not manifest.get('version'):
        raise ValueError('Versioned case manifest required')
    if not destination.is_file() or destination.stat().st_size != manifest['bytes'] \
            or sha256(destination) != manifest['sha256']:
        raise ValueError('Case archive is missing or corrupt')
    if manifest.get('database_integrity') != 'ok' or manifest.get('ingest_complete') is not True:
        raise ValueError('Case manifest does not assert verified integrity and ingest')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, type=Path)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--version', default=DEFAULT_VERSION)
    args = parser.parse_args()
    print(json.dumps(package(args.case, args.evidence, args.destination, args.manifest,
                             args.version), indent=2))


if __name__ == '__main__':
    main()
