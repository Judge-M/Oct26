"""Verify the published training binary and its recorded source inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(root: Path = REPO, manifest_path: str = 'assets/training-binary.json') -> dict:
    manifest = json.loads((root / manifest_path).read_text(encoding='utf-8'))
    binary = (root / manifest['path']).read_bytes()
    source = (root / manifest['source']).read_bytes()
    checks = {
        'published_binary': (digest(binary), manifest['sha256']),
        'tracked_lf_source': (digest(source), manifest['source_sha256']),
        'recorded_crlf_compiler_input': (
            digest(source.replace(b'\n', b'\r\n')),
            manifest['compiler_input_sha256'],
        ),
    }
    if b'\r\n' in source:
        raise ValueError('tracked source must use LF line endings')
    for name, (actual, expected) in checks.items():
        if actual != expected:
            raise ValueError(f'{name} SHA-256 mismatch: expected {expected}, got {actual}')
    return {name: actual for name, (actual, _) in checks.items()}


if __name__ == '__main__':
    print(json.dumps(verify(), sort_keys=True))
