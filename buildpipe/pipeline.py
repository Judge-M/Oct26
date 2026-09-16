"""H01e - orchestrate the build stages with resumable receipts and an inventory.

One configuration links the child stages. Each stage records a receipt keyed by a
digest of its declared inputs, so an interrupted build resumes without repeating a
completed stage. Runtime secrets and the optional downloadable dependency closure live
outside the release root and are never baked into a release.
"""
import argparse
import json
import time
from pathlib import Path

from buildpipe import BuildEnvironmentError, __version__
from buildpipe import case_package, desktop, export, native_records
from ridge.artifacts import sha256

STAGES = ('native', 'case', 'desktop', 'export')
SECRET_MARKERS = ('build-key', 'vnc-password', 'endpoints.json', 'id_ed25519', 'authorized_keys')


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError('Build configuration must be an object')
    for key in ('version', 'release_root'):
        if not config.get(key):
            raise ValueError('Build configuration requires ' + key)
    if not _configured_stages(config):
        raise ValueError('Build configuration declares no stage inputs')
    return config


def _configured_stages(config):
    return [stage for stage in STAGES
            if (stage == 'native' and config.get('native_source')) or (stage != 'native' and stage in config)]


def _stage_config(stage, config):
    return config['native_source'] if stage == 'native' else config[stage]


def _validate_layout(release_root, secrets_dir, dependencies_dir):
    paths = {'release root': release_root, 'secrets': secrets_dir, 'dependencies': dependencies_dir}
    items = list(paths.items())
    for index, (name, path) in enumerate(items):
        for other_name, other in items[index + 1:]:
            if path == other or path.is_relative_to(other) or other.is_relative_to(path):
                raise ValueError(f'{name} and {other_name} must be separate directories')


def _stage_inputs(stage, config):
    hashes = {}
    if stage == 'native':
        source = Path(config['native_source'])
        for name in ('native-provenance.json', 'Security.evtx.records.json',
                     'TaskScheduler.evtx.records.json', 'observed-connections.json',
                     'memory-sha256.json'):
            path = source / name
            if path.is_file():
                hashes[name] = sha256(path)
    elif stage == 'case':
        database = Path(config['case']['case']) / 'autopsy.db'
        if database.is_file():
            hashes['autopsy.db'] = sha256(database)
    elif stage == 'export':
        image = Path(config['export']['image'])
        if image.is_file():
            hashes['image'] = sha256(image)
    return hashes


def _stage_digest(stage, config):
    payload = dict(stage=stage, version=config['version'], stage_config=_stage_config(stage, config),
                   inputs=_stage_inputs(stage, config))
    return sha256_from_text(json.dumps(payload, sort_keys=True))


def sha256_from_text(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def _outputs(paths):
    result = {}
    for path in paths:
        path = Path(path)
        if path.is_file():
            result[str(path)] = sha256(path)
    return result


def _execute(stage, config, release_root):
    version = config['version']
    if stage == 'native':
        destination = release_root / f'native-{version}'
        manifest = native_records.build(config['native_source'], destination, version,
                                        config.get('source_hashes'), config.get('connection_port', 443))
        return 'done', destination, manifest
    if stage == 'case':
        destination = release_root / f'{version}-case.tar.gz'
        manifest_path = release_root / f'case-{version}.json'
        manifest = case_package.package(config['case']['case'], config['case']['evidence'],
                                        destination, manifest_path, version)
        return 'done', destination, manifest
    if stage == 'desktop':
        build_root = Path(config['desktop']['build_root'])
        desktop.require_linux('desktop build guest')
        desktop.verify_inputs(build_root, config['desktop'].get('inputs', {}))
        desktop.copy_inputs(build_root, config['desktop'].get('copy', {}))
        desktop.start_guest(build_root, config['desktop'].get('memory_mib', 8192),
                            config['desktop'].get('vcpus', 4), config['desktop'].get('ssh_port', 2222))
        return 'done', build_root, {}
    if stage == 'export':
        image = Path(config['export']['image'])
        desktop.require_linux('desktop export')
        export.compact(image, image.with_name(image.stem + '-compact.qcow2'))
        destination = release_root / f'desktop-{version}'
        manifest = export.split_and_hash(image.with_name(image.stem + '-compact.qcow2'),
                                         destination, version)
        return 'done', destination, manifest
    raise ValueError('Unknown stage: ' + stage)


def run_stage(stage, config, work):
    validate_config(config)
    work = Path(work)
    release_root = Path(config['release_root'])
    receipts_dir = work / 'receipts'
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipts_dir / f'{stage}.json'
    digest = _stage_digest(stage, config)
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if receipt.get('digest') == digest and receipt.get('status') in ('done', 'blocked'):
            return dict(receipt, skipped=True)
    try:
        status, destination, manifest = _execute(stage, config, release_root)
        outputs = _outputs([destination]) if Path(destination).is_file() else {}
    except BuildEnvironmentError as error:
        status, manifest, outputs, destination = 'blocked', {}, {}, ''
        detail = str(error)
    else:
        detail = ''
    receipt = dict(schema=1, pipeline=__version__, stage=stage, status=status, digest=digest,
                   destination=str(destination), outputs=outputs, manifest=manifest,
                   detail=detail, recorded=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return receipt


def run(config, work):
    validate_config(config)
    work = Path(work)
    release_root = Path(config['release_root'])
    secrets_dir = work / 'secrets'
    dependencies_dir = work / 'dependencies'
    _validate_layout(release_root, secrets_dir, dependencies_dir)
    results = {}
    for stage in _configured_stages(config):
        results[stage] = run_stage(stage, config, work)
    assert_no_secrets(release_root)
    results['inventory'] = write_inventory(work, config)
    return results


def assert_no_secrets(release_root):
    release_root = Path(release_root)
    if not release_root.exists():
        return
    for path in release_root.rglob('*'):
        if path.name in SECRET_MARKERS:
            raise ValueError('Build secret must never enter a release: ' + str(path))


def write_inventory(work, config):
    work = Path(work)
    release_root = Path(config['release_root'])
    stages = {}
    for stage in STAGES:
        receipt_path = work / 'receipts' / f'{stage}.json'
        if not receipt_path.exists():
            continue
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        stages[stage] = dict(status=receipt['status'], digest=receipt['digest'],
                             outputs=receipt.get('outputs', {}))
    files = {path.relative_to(release_root).as_posix(): sha256(path)
             for path in sorted(release_root.rglob('*')) if path.is_file()} if release_root.exists() else {}
    document = dict(schema=1, pipeline=__version__, version=config['version'],
                    stages=stages, files=files)
    inventory_path = work / 'inventory.json'
    if inventory_path.exists():
        previous = json.loads(inventory_path.read_text(encoding='utf-8'))
        if previous.get('version') == document['version'] and previous.get('files') != files:
            raise ValueError('Published outputs are immutable; freeze a new version instead')
    inventory_path.write_text(json.dumps(document, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    print(json.dumps(run(config, args.work), indent=2))


if __name__ == '__main__':
    main()
