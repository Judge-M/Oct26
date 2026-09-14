"""Export all exercise records after pausing and draining synchronization.

Freeze native controller writes during this operation. For disaster restoration,
also retain application database dumps and the original offline bundle.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from ridge.state import State
from ridge.transport import post,secret


def export(state,destination):
    destination=Path(destination)
    snapshot=state.snapshot()
    if snapshot['mode']!='paused' or snapshot['pending']:
        raise ValueError('Pause the run and drain all pending updates before coherent export')
    if destination.exists():raise ValueError('Use a new private export directory')
    destination.mkdir(parents=True)
    for application in ('IRIS','CTFD'):
        result=post(os.environ[application+'_URL']+'/silent-ridge/internal',secret('RIDGE_'+application),
                    {'key':'export','kind':'export','payload':{}},header='X-Ridge-Key')
        (destination/(application.lower()+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    state.export(destination/'integration.json')
    if state.snapshot()['mode']!='paused' or state.snapshot()['pending']:
        raise ValueError('State changed during export; export is incomplete')
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.iterdir() if p.is_file()}
    (destination/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return destination


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('destination',type=Path)
    a=p.parse_args();print(export(State(a.state),a.destination))
