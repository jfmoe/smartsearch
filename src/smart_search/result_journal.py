from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .file_lock import bounded_file_lock


LOCK_TIMEOUT_SECONDS = 0.5
REDACTED = "[REDACTED]"
_DAILY_FILE = re.compile(r"^search_results_(\d{8})\.jsonl$")
_CREDENTIAL_KEY_PARTS = {
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
    "credentials",
    "key",
    "password",
    "secret",
    "token",
}
_EXCLUDED_TRANSPORT_KEYS = {
    "internal_tool_trace",
    "internal_tool_traces",
    "intermediate_payload",
    "intermediate_payloads",
    "raw_http_body",
    "raw_http_headers",
    "raw_http_response",
    "raw_provider_response",
    "request_headers",
    "tool_trace",
    "tool_traces",
}


@dataclass(frozen=True)
class JournalOutcome:
    written: bool
    warning: str = ""


class SearchResultJournal:
    """Owns sanitization, retention, locking, and persistence for terminal search results."""

    def __init__(self, config: Any):
        self._config = config

    def write(self, result: dict[str, Any]) -> JournalOutcome:
        try:
            if not self._config.result_journal_enabled:
                return JournalOutcome(written=False)
            retention_days = self._config.result_journal_retention_days
            line = self._serialize(result)
            partition_date = date.today()
            log_dir = Path(self._config.log_dir)
            self._prepare_directory(log_dir)
            lock_path = log_dir / ".search_results.lock"
            with bounded_file_lock(lock_path, LOCK_TIMEOUT_SECONDS) as acquired:
                if not acquired:
                    raise TimeoutError("timed out after 0.5 seconds waiting for the journal lock")
                self._cleanup(log_dir, retention_days, partition_date)
                journal_path = log_dir / f"search_results_{partition_date:%Y%m%d}.jsonl"
                self._append(journal_path, line)
            return JournalOutcome(written=True)
        except Exception as error:
            return JournalOutcome(written=False, warning=self._warning_text(error))

    def status(self) -> dict[str, Any]:
        log_dir = Path(self._config.log_dir)
        enabled = False
        retention_days = 30
        valid = True
        try:
            enabled = self._config.result_journal_enabled
            retention_days = self._config.result_journal_retention_days
        except ValueError:
            valid = False
        writable = self._directory_writable_without_creation(log_dir)
        return {
            "enabled": enabled,
            "retention_days": retention_days,
            "resolved_directory": str(log_dir),
            "writable": writable,
            "ready": valid and writable,
        }

    def _serialize(self, result: dict[str, Any]) -> bytes:
        sanitized = self._sanitize(result, tuple(self._config.configured_credentials))
        envelope = {
            "schema_version": 1,
            "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "result": sanitized,
        }
        return (json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

    @classmethod
    def _sanitize(cls, value: Any, credentials: tuple[str, ...], *, credential_value: bool = False) -> Any:
        if credential_value:
            return REDACTED
        if isinstance(value, dict):
            return {
                key: cls._sanitize(
                    nested,
                    credentials,
                    credential_value=cls._credential_key(key),
                )
                for key, nested in value.items()
                if not cls._excluded_transport_key(key)
            }
        if isinstance(value, list):
            return [cls._sanitize(item, credentials) for item in value]
        if isinstance(value, tuple):
            return [cls._sanitize(item, credentials) for item in value]
        if isinstance(value, str):
            sanitized = value
            for credential in credentials:
                if credential:
                    sanitized = sanitized.replace(credential, REDACTED)
            return sanitized
        return value

    @staticmethod
    def _credential_key(key: Any) -> bool:
        if not isinstance(key, str):
            return False
        normalized = SearchResultJournal._normalized_key(key)
        return normalized in _CREDENTIAL_KEY_PARTS or any(
            normalized.endswith(f"_{part}") for part in _CREDENTIAL_KEY_PARTS
        )

    @staticmethod
    def _excluded_transport_key(key: Any) -> bool:
        if not isinstance(key, str):
            return False
        normalized = SearchResultJournal._normalized_key(key)
        return normalized in _EXCLUDED_TRANSPORT_KEYS or (
            normalized.startswith("raw_")
            and any(part in normalized.split("_") for part in ("body", "headers", "response"))
        )

    @staticmethod
    def _normalized_key(key: str) -> str:
        snake_case = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
        return re.sub(r"[^a-z0-9]+", "_", snake_case.lower()).strip("_")

    @staticmethod
    def _prepare_directory(log_dir: Path) -> None:
        log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not log_dir.is_dir():
            raise NotADirectoryError(str(log_dir))
        if os.name != "nt":
            os.chmod(log_dir, 0o700)

    @staticmethod
    def _append(path: Path, line: bytes) -> None:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            if os.name != "nt":
                os.chmod(path, 0o600)
        except Exception:
            os.close(descriptor)
            raise
        with os.fdopen(descriptor, "r+b") as stream:
            stream.seek(0, os.SEEK_END)
            start = stream.tell()
            try:
                written = stream.write(line)
                if written != len(line):
                    raise OSError("short journal append")
                stream.flush()
            except Exception:
                stream.seek(start)
                stream.truncate()
                stream.flush()
                raise

    @staticmethod
    def _cleanup(log_dir: Path, retention_days: int, partition_date: date) -> None:
        if retention_days == 0:
            return
        cutoff = (
            date.min
            if retention_days >= partition_date.toordinal()
            else partition_date - timedelta(days=retention_days - 1)
        )
        for candidate in log_dir.iterdir():
            match = _DAILY_FILE.fullmatch(candidate.name)
            if match is None or not candidate.is_file():
                continue
            try:
                partition_date = datetime.strptime(match.group(1), "%Y%m%d").date()
            except ValueError:
                continue
            if partition_date < cutoff:
                candidate.unlink()

    @staticmethod
    def _directory_writable_without_creation(log_dir: Path) -> bool:
        try:
            if log_dir.exists():
                return log_dir.is_dir() and os.access(log_dir, os.W_OK)
            parent = log_dir.parent
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            return parent.is_dir() and os.access(parent, os.W_OK)
        except OSError:
            return False

    @staticmethod
    def _warning_text(error: Exception) -> str:
        detail = " ".join(str(error).split()) or error.__class__.__name__
        return detail[:240]
