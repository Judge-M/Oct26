"""Host-side worker for dynamic team registration.

This process is launched by ``ridge.deploy start`` for a dynamic profile. It
has Docker access because it runs on the event host, never inside the public
CTFd or IRIS containers. Participant requests are just SQLite rows; the host
worker claims and provisions them one at a time.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ridge.deploy.local import LocalStack
from ridge.docker_provider import SubprocessRunner


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
        stack.registration_loop()


if __name__ == '__main__':
    main()
