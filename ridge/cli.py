"""Controller-host CLI. Export before reset; never delete previous work."""
import argparse
import json
import os
from pathlib import Path
from ridge.state import State
from ridge.preflight import check


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--state',type=Path,default=Path('runtime-expanded/state.sqlite'))
    sub=p.add_subparsers(dest='action',required=True)
    init=sub.add_parser('init');init.add_argument('--config',type=Path,default=Path('expanded/config.json'))
    init.add_argument('--content',type=Path,default=Path('expanded/tickets.json'))
    mode=sub.add_parser('mode');mode.add_argument('value',choices=['running','paused']);mode.add_argument('--operator',required=True)
    recovery=sub.add_parser('recover');recovery.add_argument('ticket');recovery.add_argument('--operator',required=True);recovery.add_argument('--reason',required=True)
    recovery.add_argument('--generation',type=int,required=True)
    export=sub.add_parser('export');export.add_argument('destination',type=Path)
    sub.add_parser('status')
    sub.add_parser('diagnostics')
    for name in ('preflight','provision'):
        command=sub.add_parser(name)
        command.add_argument('--config',type=Path,default=Path('expanded/config.json'))
        if name=='provision':
            command.add_argument('--operator',required=True)
    migration=sub.add_parser('migrate')
    migration.add_argument('--content',type=Path,required=True)
    cancellation=sub.add_parser('cancel-export')
    cancellation.add_argument('--token',required=True)
    cancellation.add_argument('--operator',required=True)
    mode.add_argument('--config',type=Path,default=Path('expanded/config.json'))
    announcement=sub.add_parser('announce');announcement.add_argument('--operator',required=True);announcement.add_argument('--text',required=True)
    args=p.parse_args();state=State(args.state)
    if args.action=='init':
        config=json.loads(args.config.read_text(encoding='utf-8'));state.initialize(config['teams'],json.loads(args.content.read_text(encoding='utf-8')))
    elif args.action=='mode':
        if args.value=='running':
            check(state,json.loads(args.config.read_text(encoding='utf-8')))
        state.mode(args.operator,args.value)
    elif args.action=='recover':
        state.release(None,args.ticket,args.generation,recovery_actor=args.operator,reason=args.reason)
    elif args.action in ('preflight','provision'):
        print(json.dumps(check(state,json.loads(args.config.read_text(encoding='utf-8')))))
        if args.action=='provision':
            state.provision(args.operator)
    elif args.action=='migrate':
        content=json.loads(args.content.read_text(encoding='utf-8'))
        from ridge.schema import migrate
        with state.transaction() as con:
            migrate(con)
            state.mutable(con)
            if con.execute('SELECT mode FROM run').fetchone()[0]!='paused':
                raise ValueError('Pause before migration')
            if {t['id'] for t in content} != {r[0] for r in con.execute('SELECT id FROM tickets')}:
                raise ValueError('Migration content must match existing tickets')
            for ticket in content:
                con.execute('UPDATE tickets SET release_files=? WHERE id=?',
                            (json.dumps(ticket['release_files']),ticket['id']))
    elif args.action=='cancel-export':
        state.cancel_export(args.operator,args.token)
    elif args.action=='diagnostics':
        print(json.dumps(state.diagnostics(),indent=2))
    elif args.action=='export':
        state.export(args.destination)
    elif args.action=='announce':
        state.announce(args.operator,args.text)
    else:
        print(json.dumps(state.snapshot(),indent=2))


if __name__=='__main__':
    main()
