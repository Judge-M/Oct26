"""Fetch the pinned upstream Wazuh single-node config into an asset tree.

The repo vendors only its own overlay in deployment/expanded/wazuh. The upstream
single-node config that compose.wazuh.yaml mounts must be materialized separately
(ridge/deploy/local.py preflight requires wazuh_indexer/wazuh.indexer.yml,
wazuh_indexer/internal_users.yml and wazuh_cluster/wazuh_manager.conf under the
wazuh_config asset).

Pinned to the exact commit recorded in deployment/expanded/wazuh/manifest.json.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMIT = json.loads((ROOT / 'deployment/expanded/wazuh/manifest.json').read_text())['source']['commit']
BASE = 'https://raw.githubusercontent.com/wazuh/wazuh-docker/%s/single-node/config/' % COMMIT
FILES = [
    'wazuh_indexer/wazuh.indexer.yml',
    'wazuh_indexer/internal_users.yml',
    'wazuh_cluster/wazuh_manager.conf',
    'wazuh_dashboard/opensearch_dashboards.yml',
]

dest = Path(sys.argv[1] if len(sys.argv) > 1 else 'work/assets/wazuh-config')
dest.mkdir(parents=True, exist_ok=True)
print('commit', COMMIT)
for rel in FILES:
    url = BASE + rel
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    target = dest / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print('%-46s %6d bytes  sha256=%s' % (rel, len(data), hashlib.sha256(data).hexdigest()[:16]))
print('written to', dest.resolve())
