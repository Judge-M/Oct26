#!/usr/bin/env python3
"""Open a configured organizer service from endpoints.json in Firefox."""
import json
from pathlib import Path
import subprocess
import sys

CONFIG = Path('/etc/silent-ridge/endpoints.json')
WAZUH_DISCOVER_PATH = (
    "/app/data-explorer/discover#?"
    "_a=(discover:(columns:!(_source),isDirty:!f,sort:!()),"
    "metadata:(indexPattern:silent-ridge-timed,view:discover))&"
    "_g=(filters:!(),refreshInterval:(pause:!t,value:0),"
    "time:(from:'2026-10-15T08:00:00.000Z',to:'2026-10-15T10:30:00.000Z'))&"
    "_q=(filters:!(),query:(language:kuery,query:''))"
)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: open-service.py <iris|ctfd|wazuh>')
    if not CONFIG.exists():
        subprocess.run(['zenity', '--error',
                        '--text=The organizer has not configured service addresses yet.'])
        raise SystemExit(1)
    service = sys.argv[1]
    url = json.loads(CONFIG.read_text(encoding='utf-8'))[service]
    if not isinstance(url, str) or not url.startswith(('https://', 'http://')):
        raise SystemExit('Expected an HTTP or HTTPS service URL')
    if service in ('iris', 'ctfd') and not url.rstrip('/').endswith('/silent-ridge'):
        url = url.rstrip('/') + '/silent-ridge'
    elif service == 'wazuh' and '/app/data-explorer/discover' not in url:
        url = url.rstrip('/') + WAZUH_DISCOVER_PATH
    subprocess.run(['/usr/local/bin/firefox', url], check=True)


if __name__ == '__main__':
    main()
