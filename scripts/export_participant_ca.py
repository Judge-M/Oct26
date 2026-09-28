"""Export only the public event CA and its DER SHA-256 fingerprint."""

import argparse
import hashlib
import ssl
from pathlib import Path


def export_ca(runtime: Path, output: Path) -> str:
    source = runtime / 'wazuh-certs' / 'root-ca.pem'
    pem = source.read_bytes()
    if pem.count(b'-----BEGIN CERTIFICATE-----') != 1 or b'PRIVATE KEY' in pem:
        raise ValueError(f'{source} must contain exactly one public certificate')
    # Reject an unreadable certificate before making a participant pack.
    ssl.create_default_context(cafile=str(source))
    der = ssl.PEM_cert_to_DER_cert(pem.decode('ascii'))
    fingerprint = hashlib.sha256(der).hexdigest().upper()
    output.mkdir(parents=True, exist_ok=True)
    files = {
        'root-ca.pem': pem,
        'root-ca.cer': der,
        'root-ca-sha256.txt': ('SHA-256 certificate fingerprint: ' + fingerprint + '\n').encode('ascii'),
    }
    for name, contents in files.items():
        target = output / name
        if target.exists() and target.read_bytes() != contents:
            raise ValueError(f'{target} differs; use a fresh output directory')
    for name, contents in files.items():
        (output / name).write_bytes(contents)
    return fingerprint


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(export_ca(args.runtime, args.output))


if __name__ == '__main__':
    main()
