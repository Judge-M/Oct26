"""Local process lock; the OS releases ownership when a process exits.

Keep journals on a local filesystem. This is not cross-site fencing.
"""
import os
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def process_lock(path, timeout=30, poll=0.05):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never unlink this inode: another process may already have it open.
    with path.open('a+b') as handle:
        if path.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError('another deployment holds the event lock') from exc
                time.sleep(poll)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
