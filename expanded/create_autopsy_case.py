"""Prepare a real, searchable Autopsy 4.22 case on Linux from released evidence.

Run as a normal Linux user. Evidence must remain mounted at the same absolute
path on participant desktops. Never point this command at the controller vault.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sqlite3


def configure_ingest(profile):
    """Pin the Linux case profile; unspecified modules default to enabled."""
    settings = Path(profile) / 'config/ModuleConfig/IngestSettings'
    settings.mkdir(parents=True, exist_ok=True)
    (settings / 'CommandLineModeContext.properties').write_text(
        'Enabled_Ingest_Modules=Keyword Search, File Type Identification, Data Source Integrity\n'
        'Disabled_Ingest_Modules=Central Repository, Virtual Machine Extractor, '
        'Extension Mismatch Detector, YARA Analyzer, Hash Lookup, Encryption Detection, '
        'GPX Parser, Android Analyzer (aLEAPP), DJI Drone Analyzer, PhotoRec Carver, '
        'Picture Analyzer, Embedded File Extractor, Recent Activity, Email Parser, '
        'Interesting Files Identifier, iOS Analyzer (iLEAPP), Android Analyzer, '
        'Cyber Triage Malware Scanner, Plaso\n'
        'Last_File_Ingest_Filter=All Files, Directories, and Unallocated Space\n',
        encoding='utf-8')


def build(autopsy, evidence, output):
    if os.name != 'posix' or os.geteuid() == 0:
        raise ValueError('Run as a non-root Linux build user; Solr refuses root')
    evidence, output = Path(evidence).resolve(), Path(output).resolve()
    disk = evidence / 'disk/WS17-fat16.img'
    if not disk.is_file() or (evidence / 'controller').exists():
        raise ValueError('Supply only the released initial evidence directory')
    output.mkdir(parents=True, exist_ok=False)
    temporary = output / 'tmp'
    temporary.mkdir()
    cases = output / 'cases'
    cases.mkdir()
    configure_ingest(output / 'profile')
    common = [str(Path(autopsy).resolve()), '--nogui', '--nosplash',
              '-J-Djava.awt.headless=true', f'-J-Djava.io.tmpdir={temporary}',
              '-J--module-path=/usr/share/openjfx/lib',
              '-J--add-modules=javafx.controls,javafx.swing',
              '--userdir', str(output / 'profile'), '--caseName', 'WS17',
              '--caseBaseDir', str(cases)]
    steps = [
        ['--createCase', '--addDataSource', '--dataSourcePath', str(disk), '--runIngest'],
        ['--addDataSource', '--dataSourcePath', str(evidence), '--runIngest'],
        ['--listAllDataSources'],
    ]
    for number, arguments in enumerate(steps, 1):
        with (output / f'step-{number}.log').open('w', encoding='utf-8') as log:
            subprocess.run(common + arguments, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=1800)
    configs = list(cases.glob('*/WS17.aut'))
    if len(configs) != 1:
        raise ValueError('Expected exactly one completed Autopsy case')
    case = configs[0].parent
    receipts = list((case / 'Command Output').glob('addDataSource*.json'))
    if len(receipts) != 2:
        raise ValueError('Both native disk and logical evidence receipts are required')
    with sqlite3.connect(f'file:{case}/autopsy.db?mode=ro', uri=True) as database:
        if database.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Autopsy case database failed integrity verification')
        completed = database.execute(
            'SELECT count(DISTINCT obj_id) FROM ingest_jobs '
            'WHERE status_id=2 AND end_date_time>start_date_time').fetchone()[0]
        if completed != 2:
            raise ValueError('Both evidence sources must have completed ingest')
        if not database.execute(
                "SELECT 1 FROM tsk_files WHERE name='_OVECACH.TXT' AND size=137").fetchone():
            raise ValueError('Expected deleted cache evidence is missing')
    if not list((case / 'ModuleOutput/keywordsearch').rglob('segments_*')):
        raise ValueError('Saved keyword index is missing')
    (output / 'case-build.json').write_text(json.dumps(dict(
        autopsy='4.22.0', sleuthkit='4.13.0', case=str(case), evidence=str(evidence),
        command_steps=steps, native_windows_memory_included=False,
        note='Disk and synthetic released exports only; native Windows capture remains separate.'
    ), indent=2) + '\n', encoding='utf-8')
    return case


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--autopsy', required=True, type=Path)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(build(args.autopsy, args.evidence, args.output))
