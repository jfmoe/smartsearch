"""Provider Credential Pool for allowlisted providers.

Runtime multi-credential round-robin and rate-limit rotation. This is a load-
spreading selection mechanism, not high-availability failover.

The shared seam is resolve → claim (advance under lock) → execute-with-rotation
→ safe status. Allowlisted providers consume it; only wired providers use it
at call sites.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

from .file_lock import bounded_file_lock

# Allowlisted provider id → (KEYS config key, single KEY config key).
# #40 wires Jina only; remaining allowlisted providers attach in follow-on work.
PROVIDER_CREDENTIAL_KEYS: Mapping[str, tuple[str, str]] = {
    "jina": ("JINA_API_KEYS", "JINA_API_KEY"),
}

ROTATABLE_ERROR_TYPES = frozenset({"rate_limited", "quota_exhausted"})

STATE_FILENAME = "credential_pool_state.json"
LOCK_FILENAME = ".credential_pool.lock"
LOCK_TIMEOUT_SECONDS = 2.0


class CredentialPoolError(ValueError):
    """Invalid multi-credential configuration or unsupported pool provider."""


def parse_keys_json(raw: str, *, config_key: str = "API_KEYS") -> list[str]:
    """Parse a JSON string array of credentials; strip empties and dedupe in order.

    Raises CredentialPoolError when JSON is invalid or not an array of strings.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CredentialPoolError(
            f"{config_key} must be a JSON array of strings: {error.msg}"
        ) from error
    if not isinstance(parsed, list):
        raise CredentialPoolError(f"{config_key} must be a JSON array of strings")
    credentials: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, str):
            raise CredentialPoolError(f"{config_key} must be a JSON array of strings")
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        credentials.append(value)
    return credentials


def resolve_credentials(
    *,
    keys_raw: str | None,
    key_raw: str | None,
    keys_config_key: str = "API_KEYS",
) -> list[str]:
    """Resolve the active credential list for one provider.

    Non-empty KEYS (after empty-strip and dedupe) fully replaces KEY.
    Absent/empty KEYS falls back to the single KEY when present.
    """
    if keys_raw is not None and keys_raw.strip():
        keys = parse_keys_json(keys_raw, config_key=keys_config_key)
        if keys:
            return keys
    key = (key_raw or "").strip()
    return [key] if key else []


class ProviderCredentialPool:
    """Shared Provider Credential Pool seam for allowlisted providers."""

    def __init__(self, config: Any, *, state_dir: Path | None = None):
        self._config = config
        self._state_dir = state_dir

    @property
    def state_dir(self) -> Path:
        if self._state_dir is not None:
            return self._state_dir
        return Path(self._config.config_file).parent

    def resolve(self, provider_id: str) -> list[str]:
        keys_name, key_name = self._key_names(provider_id)
        keys_raw = self._config._get_config_value(keys_name)
        key_raw = self._config._get_config_value(key_name)
        return resolve_credentials(
            keys_raw=keys_raw,
            key_raw=key_raw,
            keys_config_key=keys_name,
        )

    def claim_start_index(self, provider_id: str, pool_size: int) -> int:
        """Claim the next round-robin index and advance immediately under a file lock."""
        if pool_size <= 0:
            return 0
        if pool_size == 1:
            return 0

        state_dir = self.state_dir
        state_dir.mkdir(parents=True, exist_ok=True)
        state_path = state_dir / STATE_FILENAME
        lock_path = state_dir / LOCK_FILENAME
        start_index = 0

        with bounded_file_lock(lock_path, LOCK_TIMEOUT_SECONDS) as acquired:
            state = self._read_state(state_path) if acquired or state_path.exists() else {}
            provider_state = state.get(provider_id) if isinstance(state.get(provider_id), dict) else {}
            raw_next = provider_state.get("next_index", 0)
            try:
                next_index = int(raw_next)
            except (TypeError, ValueError):
                next_index = 0
            start_index = next_index % pool_size
            if acquired:
                advanced = (start_index + 1) % pool_size
                state[provider_id] = {"next_index": advanced}
                self._write_state(state_path, state)
        return start_index

    def safe_status(self, provider_id: str) -> dict[str, Any]:
        """Pool enablement, count, and masked tails — never raw credentials."""
        from .config import Config

        try:
            credentials = self.resolve(provider_id)
            error = ""
        except CredentialPoolError as exc:
            credentials = []
            error = str(exc)
        mask = getattr(self._config, "_mask_api_key", None) or Config._mask_api_key
        return {
            "provider": provider_id,
            "configured": bool(credentials) and not error,
            "enabled": len(credentials) > 1,
            "key_count": len(credentials),
            "masked_keys": [mask(item) for item in credentials],
            "error": error,
        }

    async def execute_with_rotation(
        self,
        provider_id: str,
        attempt_fn: Callable[[str, int], Awaitable[dict[str, Any]]],
        *,
        credentials: list[str] | None = None,
    ) -> dict[str, Any]:
        """Try credentials from the claimed start index for one full pass.

        Rotates only on rate_limited / explicit quota exhaustion. Each credential
        is used at most once per call.
        """
        pool = list(credentials) if credentials is not None else self.resolve(provider_id)
        if not pool:
            return {
                "ok": False,
                "provider": provider_id,
                "error_type": "config_error",
                "error": f"No credentials configured for {provider_id}",
            }

        start = self.claim_start_index(provider_id, len(pool))
        last_result: dict[str, Any] | None = None
        rotated = False

        for offset in range(len(pool)):
            index = (start + offset) % len(pool)
            credential = pool[index]
            result = dict(await attempt_fn(credential, index))
            result["key_index"] = index
            if offset > 0:
                rotated = True
            if rotated:
                result["credential_rotated"] = True
            last_result = result
            if result.get("ok"):
                return result
            error_type = str(result.get("error_type") or "")
            if error_type not in ROTATABLE_ERROR_TYPES:
                return result

        assert last_result is not None
        return last_result

    def _key_names(self, provider_id: str) -> tuple[str, str]:
        mapping = PROVIDER_CREDENTIAL_KEYS.get(provider_id)
        if mapping is None:
            raise CredentialPoolError(
                f"Provider {provider_id!r} is not on the Provider Credential Pool allowlist"
            )
        return mapping

    @staticmethod
    def _read_state(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _write_state(path: Path, state: dict[str, Any]) -> None:
        # Indices/metadata only — callers must never put credentials in state.
        safe_state: dict[str, Any] = {}
        for provider_id, value in state.items():
            if not isinstance(value, dict):
                continue
            next_index = value.get("next_index", 0)
            try:
                safe_state[str(provider_id)] = {"next_index": int(next_index)}
            except (TypeError, ValueError):
                safe_state[str(provider_id)] = {"next_index": 0}
        temporary_path: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = _mkstemp_in(path.parent, prefix=f".{path.name}.")
            temporary_path = Path(temporary_name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(safe_state, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass


def _mkstemp_in(directory: Path, *, prefix: str) -> tuple[int, str]:
    import tempfile

    return tempfile.mkstemp(prefix=prefix, dir=str(directory), text=True)
