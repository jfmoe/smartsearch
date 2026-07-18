from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import Config
from .file_lock import bounded_file_lock
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
    return synchronize_skill_preference(config, paths, current_version, last_synced_cli_version="")


def synchronize_skill_preference(
    config: Config,
    paths: list[str],
    current_version: str,
    *,
    last_synced_cli_version: str,
) -> dict[str, object]:
    preferences = config.set_skill_preferences(
        paths,
        last_synced_cli_version=last_synced_cli_version,
    )
    result = install_skill_containers(paths)
    if result["ok"]:
        preferences = config.set_skill_preferences(paths, last_synced_cli_version=current_version)
    return {
        **result,
        "current_cli_version": current_version,
        "last_synced_cli_version": preferences["last_synced_cli_version"],
        "sync_pending": bool(paths) and preferences["last_synced_cli_version"] != current_version,
    }


@contextmanager
def skill_preference_lock(config: Config, timeout: float) -> Iterator[bool]:
    lock_path = Path(f"{config.config_file}.skills.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with bounded_file_lock(lock_path, timeout) as acquired:
        yield acquired


def _load_automatic_sync_state(config: Config) -> tuple[dict | None, list[str]]:
    preferences = config.get_skill_preferences()
    if preferences is None:
        return None, []
    return preferences, normalize_skill_containers(preferences["paths"])


def _automatic_sync_noop_reason(
    preferences: dict | None,
    paths: list[str],
    current_version: str,
) -> str | None:
    if preferences is None:
        return None
    if not paths:
        return "disabled"
    if preferences["last_synced_cli_version"] == current_version:
        return "current"
    return None


def automatic_skill_sync(config: Config, current_version: str) -> dict[str, object]:
    try:
        preferences, paths = _load_automatic_sync_state(config)
        noop_reason = _automatic_sync_noop_reason(preferences, paths, current_version)
        if noop_reason is not None:
            return {"ok": True, "sync_needed": False, "reason": noop_reason}

        with skill_preference_lock(config, BACKGROUND_LOCK_TIMEOUT_SECONDS) as acquired:
            if not acquired:
                return {"ok": False, "reason": "lock_timeout"}
            preferences, paths = _load_automatic_sync_state(config)
            if preferences is None:
                paths = normalize_skill_containers(["agents"])
                preferences = config.set_skill_preferences(paths)
            noop_reason = _automatic_sync_noop_reason(preferences, paths, current_version)
            if noop_reason is not None:
                return {"ok": True, "sync_needed": False, "reason": noop_reason}
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
