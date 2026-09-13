"""Read-only verification of the deployed container access boundaries."""
import json
import subprocess


def docker(*args):
    return subprocess.check_output(['docker',*args],text=True).strip()


app_id=docker('compose','ps','-q','exercise')
gateway_id=docker('compose','ps','-q','gateway')
assert app_id and gateway_id
app=json.loads(docker('inspect',app_id))[0]
gateway=json.loads(docker('inspect',gateway_id))[0]
assert app['Config']['User']=='10001:10001'
assert app['HostConfig']['ReadonlyRootfs']
assert not app['HostConfig']['PortBindings']
assert set(m['Destination'] for m in app['Mounts'])=={'/public','/state','/control','/run/secrets/credentials'}
assert all(not m['RW'] for m in app['Mounts'] if m['Destination']!='/state')
networks=app['NetworkSettings']['Networks']
assert len(networks)==1
assert json.loads(docker('network','inspect',next(iter(networks))))[0]['Internal']
assert len(gateway['NetworkSettings']['Networks'])==2
assert set(m['Destination'] for m in gateway['Mounts'])=={'/etc/nginx/nginx.conf'}
docker('compose','exec','-T','exercise','python','-c',
       "from pathlib import Path; assert not any(Path(p).exists() for p in ['/app/facilitator','/app/scripts','/app/.git','/vault']); assert Path('/app/server.py').exists()")
print('Container boundaries passed: internal app network, read-only public/secret, no root/vault/image leakage, gateway-only published port.')
