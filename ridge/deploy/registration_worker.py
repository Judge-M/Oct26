"""Host-side worker for dynamic team registration.

This process is launched by ``ridge.deploy start`` for a dynamic profile. It
has Docker access because it runs on the event host, never inside the public
CTFd or IRIS containers. Participant requests are just SQLite rows; the host
worker claims and provisions them one at a time.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import threading
import time

from ridge.deploy.local import LocalStack
from ridge.docker_provider import SubprocessRunner


SHARED_HEARTBEAT_NAME = 'registration-worker-heartbeat.json'


def _publish_shared_heartbeat(runtime, *, now=None):
    """Atomically publish readiness where the CTFd container can read it."""
    registration_dir = Path(runtime) / 'registration'
    registration_dir.mkdir(parents=True, exist_ok=True)
    target = registration_dir / SHARED_HEARTBEAT_NAME
    temporary = target.with_name(target.name + '.tmp')
    payload = {
        'ready': True,
        'pid': os.getpid(),
        'updated': time.time() if now is None else float(now),
    }
    temporary.write_text(json.dumps(payload, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(temporary, target)
    return target


def _run_with_shared_heartbeat(stack, runtime, *, interval=5.0):
    """Keep a participant-visible readiness signal fresh while the worker runs."""
    stopped = threading.Event()

    def beat():
        while not stopped.wait(interval):
            _publish_shared_heartbeat(runtime)

    _publish_shared_heartbeat(runtime)
    heartbeat = threading.Thread(target=beat, daemon=True,
                                 name='registration-shared-heartbeat')
    heartbeat.start()
    try:
        stack.registration_loop()
    finally:
        stopped.set()
        heartbeat.join(timeout=interval + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--once', action='store_true',
                        help='claim and provision at most one request, then exit')
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    stack = LocalStack(profile, args.runtime, SubprocessRunner(), operator='registration-worker')
    if args.once:
        print(json.dumps(stack.register_once(), indent=2))
    else:
        _run_with_shared_heartbeat(stack, args.runtime)


if __name__ == '__main__':
    main()
