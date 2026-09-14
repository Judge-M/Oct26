"""Controller-host CLI. Export before reset; never delete previous work."""
import argparse
import json
import os
from pathlib import Path
from ridge.state import State


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--state',type=Path,default=Path('runtime-expanded/state.sqlite'))
    sub=p.add_subparsers(dest='action',required=True)
    init=sub.add_parser('init');init.add_argument('--config',type=Path,default=Path('expanded/config.json'))
    init.add_argument('--content',type=Path,default=Path('expanded/tickets.json'))
    mode=sub.add_parser('mode');mode.add_argument('value',choices=['running','paused']);mode.add_argument('--operator',required=True)
    recovery=sub.add_parser('recover');recovery.add_argument('ticket');recovery.add_argument('--operator',required=True);recovery.add_argument('--reason',required=True)
    export=sub.add_parser('export');export.add_argument('destination',type=Path)
    sub.add_parser('status')
    announcement=sub.add_parser('announce');announcement.add_argument('--operator',required=True);announcement.add_argument('--text',required=True)
    args=p.parse_args();state=State(args.state)
    if args.action=='init':
        config=json.loads(args.config.read_text());state.initialize(config['teams'],json.loads(args.content.read_text()))
    elif args.action=='mode':
        state.mode(args.operator,args.value)
    elif args.action=='recover':
        state.release(None,args.ticket,recovery_actor=args.operator,reason=args.reason)
    elif args.action=='export':
        state.export(args.destination)
    elif args.action=='announce':
        state.announce(args.operator,args.text)
    else:
        print(json.dumps(state.snapshot(),indent=2))


if __name__=='__main__':
    main()
