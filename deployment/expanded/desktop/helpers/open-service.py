#!/usr/bin/env python3
"""Open a configured organizer service from endpoints.json in Firefox."""
import json
from pathlib import Path
import subprocess
import sys

CONFIG = Path('/etc/silent-ridge/endpoints.json')


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: open-service.py <iris|ctfd|wazuh>')
    if not CONFIG.exists():
        subprocess.run(['zenity', '--error',
                        '--text=The organizer has not configured service addresses yet.'])
        raise SystemExit(1)
    url = json.loads(CONFIG.read_text(encoding='utf-8'))[sys.argv[1]]
    if not isinstance(url, str) or not url.startswith(('https://', 'http://')):
        raise SystemExit('Expected an HTTP or HTTPS service URL')
    subprocess.run(['/usr/local/bin/firefox', url], check=True)


if __name__ == '__main__':
    main()
