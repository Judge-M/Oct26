"""Command-line entry point for the H01 portable build pipeline."""
import argparse
import json
from pathlib import Path

from buildpipe import case_package, export, native_records, pipeline


def main():
    parser = argparse.ArgumentParser(prog='buildpipe', description='Silent Ridge portable build pipeline')
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', help='Run the configured pipeline stages')
    run.add_argument('--config', required=True, type=Path)
    run.add_argument('--work', required=True, type=Path)
    native = commands.add_parser('native', help='Reconstruct neutral native records')
    native.add_argument('--source', required=True, type=Path)
    native.add_argument('--destination', required=True, type=Path)
    native.add_argument('--version', default=native_records.DEFAULT_VERSION)
    native.add_argument('--export-evtx', type=Path, metavar='EVTX')
    case = commands.add_parser('case', help='Package a closed Autopsy case')
    case.add_argument('--case', required=True, type=Path)
    case.add_argument('--evidence', required=True, type=Path)
    case.add_argument('--destination', required=True, type=Path)
    case.add_argument('--manifest', required=True, type=Path)
    case.add_argument('--version', default=case_package.DEFAULT_VERSION)
    inventory = commands.add_parser('inventory', help='Write the release output inventory')
    inventory.add_argument('--config', required=True, type=Path)
    inventory.add_argument('--work', required=True, type=Path)
    verify = commands.add_parser('verify-desktop', help='Verify split desktop parts')
    verify.add_argument('--destination', required=True, type=Path)
    verify.add_argument('--version', default='desktop-v2')
    args = parser.parse_args()
    if args.command == 'run':
        result = pipeline.run(json.loads(args.config.read_text(encoding='utf-8')), args.work)
    elif args.command == 'native':
        if args.export_evtx:
            result = str(native_records.export_evtx(args.export_evtx, args.destination))
        else:
            result = native_records.build(args.source, args.destination, args.version)
    elif args.command == 'case':
        result = case_package.package(args.case, args.evidence, args.destination,
                                      args.manifest, args.version)
    elif args.command == 'inventory':
        result = pipeline.write_inventory(args.work, json.loads(args.config.read_text(encoding='utf-8')))
    else:
        result = export.verify_release(args.destination, args.version)
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
