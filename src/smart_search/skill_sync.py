from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import Config
from .skill_installer import (
    SkillInstallError,
    install_skill_containers,
    normalize_skill_containers,
    status_skill_containers,
)


BACKGROUND_LOCK_TIMEOUT_SECONDS = 0.5
EXPLICIT_LOCK_TIMEOUT_SECONDS = 10.0


def replace_skill_preference(
    config: Config, requested: list[str], current_version: str
) -> dict[str, object]:
    paths = normalize_skill_containers(requested)
    preferences = config.set_skill_preferences(paths)
    result = install_skill_containers(paths)
    if result["ok"]:
        preferences = config.set_skill_preferences(paths, last_synced_cli_version=current_version)
    return {
        **result,
        "current_cli_version": current_version,
        "last_synced_cli_version": preferences["last_synced_cli_version"],
        "sync_pending": bool(paths) and preferences["last_synced_cli_version"] != current_version,
    }


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
def skill_preference_lock(config: Config, timeout: float) -> Iterator[bool]:
    lock_path = Path(f"{config.config_file}.skills.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
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


def automatic_skill_sync(config: Config, current_version: str) -> dict[str, object]:
    try:
        with skill_preference_lock(config, BACKGROUND_LOCK_TIMEOUT_SECONDS) as acquired:
            if not acquired:
                return {"ok": False, "reason": "lock_timeout"}
            preferences = config.get_skill_preferences()
            if preferences is None:
                paths = normalize_skill_containers(["agents"])
                preferences = config.set_skill_preferences(paths)
            else:
                paths = normalize_skill_containers(preferences["paths"])
            if preferences["last_synced_cli_version"] == current_version:
                return {"ok": True, "sync_needed": False}
            result = install_skill_containers(paths)
            if result["ok"]:
                status = status_skill_containers(paths)
                fully_synchronized = status["ok"] and all(
                    installation["managed_hash_match"] for installation in status["installations"]
                )
                if fully_synchronized:
                    config.set_skill_preferences(paths, last_synced_cli_version=current_version)
                else:
                    result.update(ok=False, reason="verification_failed")
            return {**result, "sync_needed": True}
    except (SkillInstallError, ValueError, OSError) as error:
        return {"ok": False, "reason": "sync_error", "error": str(error)}
