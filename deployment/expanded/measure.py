"""Collect actual central-container observations during a Linux rehearsal."""
import argparse
import datetime
import json
import platform
import subprocess
import time
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--samples',type=int,default=60)
p.add_argument('--interval',type=float,default=5);p.add_argument('--phase',required=True)
p.add_argument('--containers',nargs='+',required=True,help='Only the exercise container IDs/names to sample')
a=p.parse_args()
if a.samples<1 or a.interval<0:raise ValueError('Invalid sampling configuration')
with a.output.open('x',encoding='utf-8') as f:
    for sample in range(a.samples):
        data=subprocess.check_output(['docker','stats','--no-stream','--format','{{json .}}',*a.containers],text=True)
        f.write(json.dumps(dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            phase=a.phase,platform=platform.platform(),containers=[json.loads(line) for line in data.splitlines()]))+'\n')
        f.flush()
        if sample+1<a.samples:time.sleep(a.interval)
