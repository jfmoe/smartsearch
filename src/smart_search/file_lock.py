from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _try_lock(lock_file) -> bool:
    if os.name == "nt":
        import msvcrt

        lock_file.seek(0)
        if lock_file.read(1) == b"":
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    import fcntl

    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _unlock(lock_file) -> None:
    if os.name == "nt":
        import msvcrt

        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def bounded_file_lock(path: Path, timeout: float, *, mode: int = 0o600) -> Iterator[bool]:
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, mode)
    try:
        if os.name != "nt":
            os.chmod(path, mode)
    except Exception:
        os.close(descriptor)
        raise
    with os.fdopen(descriptor, "r+b") as lock_file:
        deadline = time.monotonic() + timeout
        acquired = _try_lock(lock_file)
        while not acquired and time.monotonic() < deadline:
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            acquired = _try_lock(lock_file)
        try:
            yield acquired
        finally:
            if acquired:
                _unlock(lock_file)
