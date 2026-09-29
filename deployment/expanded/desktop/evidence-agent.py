#!/usr/bin/env python3
"""Desktop-side evidence delivery agent (C03).

Runs as a systemd service on each team desktop. It fetches the controller's
checksum manifest over the local-CA HTTPS endpoint, downloads new files into
root-owned staging, verifies them and atomically publishes read-only files.

Configuration (environment):
  RIDGE_DELIVERY_URL   private controller base URL, e.g. https://controller/evidence
  RIDGE_CA_FILE        local CA bundle; TLS verification is never disabled
  RIDGE_STAGING        root-owned staging directory
  RIDGE_PUBLISHED      read-only published directory (e.g. /evidence/released)
  RIDGE_POLL_SECONDS   poll interval, default 30

LIVE VALIDATION BLOCKED: no desktop or controller endpoint is available on the
wave-1/2 host; this script has not been run against real services.
"""
import json
import os
import ssl
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, '/opt/silent-ridge')
from ridge.desktop_delivery import DesktopAgent, DeliveryError  # noqa: E402


def _fetch(url, ca_file):
    context = ssl.create_default_context(cafile=ca_file)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    with urllib.request.urlopen(url, context=context, timeout=30) as response:
        return response.read()


def transport(base_url, ca_file):
    def download(url, destination):
        data = _fetch(url, ca_file)
        Path(destination).write_bytes(data)
    return download


def main():
    base = os.environ['RIDGE_DELIVERY_URL'].rstrip('/')
    ca_file = os.environ['RIDGE_CA_FILE']
    agent = DesktopAgent(transport=transport(base, ca_file), base_url=base,
                         staging=Path(os.environ['RIDGE_STAGING']),
                         published=Path(os.environ['RIDGE_PUBLISHED']))
    interval = float(os.environ.get('RIDGE_POLL_SECONDS', '30'))
    while True:
        try:
            document = json.loads(_fetch(base + '/manifest.json', ca_file))
            print(json.dumps(agent.sync(document)))
        except (DeliveryError, OSError, ValueError) as error:
            # A disconnected desktop stays unready and catches up on reconnect.
            print(json.dumps({'ready': False, 'error': type(error).__name__}), flush=True)
        time.sleep(interval)


if __name__ == '__main__':
    main()
