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
from ridge.artifacts import sha256


def export(state,destination):
    destination=Path(destination)
    if destination.exists():raise ValueError('Use a new private export directory')
    from ridge.storage import require_space
    require_space(destination.parent)
    with state.export_barrier() as token:
        destination.mkdir(parents=True)
        state.export(destination/'integration.json')
        with state.transaction(write=False) as con:
            deliveries=[dict(row) for row in con.execute('SELECT id,kind,remote FROM outbox')]
        for application in ('IRIS','CTFD'):
            result=post(os.environ[application+'_URL']+'/silent-ridge/internal',secret('RIDGE_'+application),
                        {'key':'export','kind':'export','payload':{}},header='X-Ridge-Key')
            receipts={r['key']:str(r['award_id' if application=='CTFD' else 'remote'])
                      for r in result['credits' if application=='CTFD' else 'receipts']}
            expected={r['id']:r['remote'] for r in deliveries
                      if (r['kind']=='point') == (application=='CTFD')}
            if any(receipts.get(key)!=remote for key,remote in expected.items()):
                raise ValueError('Remote receipt watermark differs from integration export')
            (destination/(application.lower()+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        manifest={p.name:sha256(p) for p in destination.iterdir() if p.is_file()}
        # Serialize completion with explicit cancellation of an abandoned export.
        with state.transaction() as con:
            if con.execute('SELECT export_token FROM control').fetchone()[0] != token:
                raise ValueError('Export cancelled; output is incomplete')
            temporary=destination/'SHA256SUMS.pending'
            temporary.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
            temporary.replace(destination/'SHA256SUMS.json')
    return destination


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('destination',type=Path)
    a=p.parse_args();print(export(State(a.state),a.destination))
