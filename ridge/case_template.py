"""Verify the published closed case and extract a desktop template."""
import argparse
import json
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

from ridge.artifacts import safe, sha256


def prepare(root, destination):
    root, destination = Path(root), Path(destination)
    manifest = json.loads((root / 'assets/autopsy-case-v2.json').read_text())
    archive = safe(root, manifest['artifact'])
    if archive.stat().st_size != manifest['bytes'] or sha256(archive) != manifest['sha256']:
        raise ValueError('Fetch the published case with git lfs pull --include="assets/large/autopsy/**"')
    if destination.exists():
        raise ValueError('Use a new template directory; existing case data is never replaced')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as work:
        work = Path(work)
        with tarfile.open(archive) as tar:
            tar.extractall(work, filter='data')
        case = safe(work, manifest['case_path']).parent
        files = {p.relative_to(case).as_posix(): sha256(p) for p in case.rglob('*') if p.is_file()}
        (case / '.template.json').write_text(json.dumps({'archive': manifest['sha256'], 'files': files}))
        case.rename(destination)
    return {'case': str(destination), 'archive': manifest['sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(Path(__file__).resolve().parents[1], args.destination)))
