import asyncio
import json
import multiprocessing
import os
import stat
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from smart_search import cli
from smart_search.file_lock import bounded_file_lock
from smart_search.result_journal import SearchResultJournal


def _terminal_result(secret: str = "configured-secret") -> dict:
    return {
        "ok": True,
        "query": f"中文 query containing {secret}",
        "content": f"完整回答 containing {secret}",
        "sources": [
            {"title": "Primary", "url": "https://primary.example/source"},
            {"title": "Extra", "url": "https://extra.example/source"},
        ],
        "sources_count": 2,
        "primary_sources": [{"title": "Primary", "url": "https://primary.example/source"}],
        "primary_sources_count": 1,
        "extra_sources": [{"title": "Extra", "url": "https://extra.example/source"}],
        "extra_sources_count": 1,
        "source_warning": "ordinary warning",
        "routing_decision": {"capability": "web_search", "vertical_discovery": {"used": True}},
        "providers_used": ["openai-compatible", "anysearch"],
        "provider_attempts": [
            {"provider": "openai-compatible", "status": "ok", "authorization": "Bearer should-redact"}
        ],
        "fallback_used": True,
        "model": "model-1",
        "elapsed_ms": 123.4,
        "nested": {"api_key": "credential-shaped-value", "ordinary_error": "safe error"},
        "camelCaseFields": {"accessToken": "token-value", "clientSecret": "secret-value"},
        "key": "bare-key-value",
        "raw_http_response": {"body": "must not persist"},
        "request_headers": {"x-debug": "must not persist"},
        "internal_tool_trace": [{"step": "must not persist"}],
    }


def _journal_lines(log_dir: Path) -> list[dict]:
    paths = list(log_dir.glob("search_results_*.jsonl"))
    if not paths:
        return []
    assert len(paths) == 1
    raw = paths[0].read_text(encoding="utf-8")
    assert raw.endswith("\n")
    return [json.loads(line) for line in raw.splitlines()]


def test_default_search_invocation_journals_complete_result_without_changing_output(
    monkeypatch, capsys, tmp_path
):
    log_dir = tmp_path / "journal"
    secret = "configured-secret"
    result = _terminal_result(secret)

    async def fake_search(query, **kwargs):
        return result

    monkeypatch.setattr(cli.service, "search", fake_search)
    monkeypatch.setenv("SMART_SEARCH_LOG_DIR", str(log_dir))
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", secret)

    assert cli.main(["search", "disabled"]) == cli.EXIT_OK
    disabled_output = json.loads(capsys.readouterr().out)
    assert disabled_output == result
    assert not log_dir.exists()

    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_ENABLED", "yes")
    output_path = tmp_path / "result.md"
    assert cli.main(["s", "enabled", "--format", "markdown", "--output", str(output_path)]) == cli.EXIT_OK
    rendered = capsys.readouterr()
    assert rendered.err == ""
    assert "完整回答" in rendered.out
    assert secret in rendered.out
    assert output_path.read_text(encoding="utf-8") == rendered.out

    records = _journal_lines(log_dir)
    assert len(records) == 1
    record = records[0]
    assert record["schema_version"] == 1
    assert record["recorded_at"].endswith("Z")
    assert record["result"]["primary_sources"][0]["url"] == "https://primary.example/source"
    assert record["result"]["extra_sources"][0]["url"] == "https://extra.example/source"
    assert record["result"]["routing_decision"]["vertical_discovery"] == {"used": True}
    assert record["result"]["provider_attempts"][0]["authorization"] == "[REDACTED]"
    assert record["result"]["nested"]["api_key"] == "[REDACTED]"
    assert record["result"]["nested"]["ordinary_error"] == "safe error"
    assert record["result"]["camelCaseFields"] == {
        "accessToken": "[REDACTED]",
        "clientSecret": "[REDACTED]",
    }
    assert record["result"]["key"] == "[REDACTED]"
    assert "raw_http_response" not in record["result"]
    assert "request_headers" not in record["result"]
    assert "internal_tool_trace" not in record["result"]
    assert secret not in json.dumps(record, ensure_ascii=False)
    assert result == _terminal_result(secret)


@pytest.mark.parametrize("fmt", ["json", "markdown", "content"])
def test_every_search_terminal_shape_is_journaled_once(monkeypatch, capsys, tmp_path, fmt):
    log_dir = tmp_path / fmt
    monkeypatch.setenv("SMART_SEARCH_LOG_DIR", str(log_dir))
    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_ENABLED", "true")
    failure = {
        "ok": False,
        "error_type": "provider_error",
        "error": "ordinary provider failure",
        "query": "failure",
        "content": "",
        "sources": [],
        "provider_attempts": [{"provider": "xai-responses", "status": "failed"}],
        "elapsed_ms": 9,
    }

    async def fake_search(query, **kwargs):
        return failure

    monkeypatch.setattr(cli.service, "search", fake_search)
    assert cli.main(["search", "failure", "--format", fmt]) == cli.EXIT_NETWORK_ERROR
    capsys.readouterr()
    assert [entry["result"] for entry in _journal_lines(log_dir)] == [failure]


def test_timeout_and_journal_failure_preserve_cli_result(monkeypatch, capsys, tmp_path):
    log_dir = tmp_path / "timeout"
    monkeypatch.setenv("SMART_SEARCH_LOG_DIR", str(log_dir))
    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_ENABLED", "1")

    async def slow_search(query, **kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(cli.service, "search", slow_search)
    assert cli.main(["search", "slow", "--timeout", "0.01"]) == cli.EXIT_NETWORK_ERROR
    timeout_io = capsys.readouterr()
    timeout_result = json.loads(timeout_io.out)
    assert timeout_io.err == ""
    assert timeout_result["error"].startswith("Search timed out")
    assert [entry["result"] for entry in _journal_lines(log_dir)] == [timeout_result]

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("existing", encoding="utf-8")
    monkeypatch.setenv("SMART_SEARCH_LOG_DIR", str(blocker))

    successful = _terminal_result()

    async def successful_search(query, **kwargs):
        return successful

    monkeypatch.setattr(cli.service, "search", successful_search)
    assert cli.main(["search", "still succeeds"]) == cli.EXIT_OK
    failed_io = capsys.readouterr()
    assert json.loads(failed_io.out) == successful
    assert failed_io.err.count("Search Result Journal warning:") == 1
    assert blocker.read_text(encoding="utf-8") == "existing"


def test_doctor_reports_journal_state_without_creating_artifacts(monkeypatch, capsys, tmp_path):
    log_dir = tmp_path / "doctor-journal"
    monkeypatch.setenv("SMART_SEARCH_LOG_DIR", str(log_dir))
    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_ENABLED", "true")
    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS", "7")

    async def fake_doctor():
        return cli.service.config.get_config_info() | {
            "ok": True,
            "minimum_profile_ok": True,
            "capability_status": {},
            "intent_router_status": {},
        }

    monkeypatch.setattr(cli.service, "doctor", fake_doctor)
    assert cli.main(["doctor", "--format", "json"]) == cli.EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["result_journal"] == {
        "enabled": True,
        "retention_days": 7,
        "resolved_directory": str(log_dir),
        "writable": True,
        "ready": True,
    }
    assert not log_dir.exists()

    assert cli.main(["doctor", "--format", "markdown"]) == cli.EXIT_OK
    markdown = capsys.readouterr().out
    assert "Search Result Journal enabled: YES" in markdown
    assert "Search Result Journal retention: 7 days" in markdown
    assert not log_dir.exists()

    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS", "-1")
    invalid = cli.service.config.get_config_info()
    assert any("SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS" in error for error in invalid["config_parameter_errors"])


def test_journal_config_uses_environment_over_file_and_rejects_invalid_retention(monkeypatch):
    config = cli.service.config
    config.set_config_value("SMART_SEARCH_RESULT_JOURNAL_ENABLED", "yes")
    config.set_config_value("SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS", "12")
    assert config.result_journal_enabled is True
    assert config.result_journal_retention_days == 12
    assert config.get_config_source("SMART_SEARCH_RESULT_JOURNAL_ENABLED") == "config_file"

    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_ENABLED", "false")
    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS", "0")
    assert config.result_journal_enabled is False
    assert config.result_journal_retention_days == 0
    assert config.get_config_source("SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS") == "environment"

    result = cli.service.config_set("SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS", "1.5")
    assert result["ok"] is False
    assert result["error_type"] == "parameter_error"


def test_invalid_retention_fails_search_as_configuration_error(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("SMART_SEARCH_LOG_DIR", str(tmp_path / "invalid"))
    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_ENABLED", "true")
    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS", "-1")

    async def should_not_search(query, **kwargs):
        raise AssertionError("invalid Journal policy must fail before provider search")

    monkeypatch.setattr(cli.service, "search", should_not_search)
    assert cli.main(["search", "query"]) == cli.EXIT_CONFIG_ERROR
    output = capsys.readouterr()
    data = json.loads(output.out)
    assert data["error_type"] == "config_error"
    assert "SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS" in data["error"]
    assert output.err.count("Search Result Journal warning:") == 1
    assert not (tmp_path / "invalid").exists()

    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_ENABLED", "false")
    assert cli.main(["search", "query"]) == cli.EXIT_CONFIG_ERROR
    disabled_output = capsys.readouterr()
    assert json.loads(disabled_output.out)["error_type"] == "config_error"
    assert disabled_output.err == ""
    assert not (tmp_path / "invalid").exists()


def test_unserializable_result_warns_once_without_partial_line(monkeypatch, capsys, tmp_path):
    log_dir = tmp_path / "serialization"
    monkeypatch.setenv("SMART_SEARCH_LOG_DIR", str(log_dir))
    monkeypatch.setenv("SMART_SEARCH_RESULT_JOURNAL_ENABLED", "true")

    async def fake_search(query, **kwargs):
        return {"ok": True, "content": "still rendered", "sources": [], "unserializable": {1, 2}}

    monkeypatch.setattr(cli.service, "search", fake_search)
    assert cli.main(["search", "query", "--format", "content"]) == cli.EXIT_OK
    output = capsys.readouterr()
    assert output.out == "still rendered\n"
    assert output.err.count("Search Result Journal warning:") == 1
    assert not list(log_dir.glob("search_results_*.jsonl"))


def _concurrent_writer(log_dir: str, index: int) -> None:
    config = SimpleNamespace(
        result_journal_enabled=True,
        result_journal_retention_days=0,
        log_dir=Path(log_dir),
        configured_credentials=[],
    )
    outcome = SearchResultJournal(config).write({"ok": True, "index": index, "content": "x" * 10000})
    if not outcome.written:
        raise RuntimeError(outcome.warning)


def _hold_journal_lock(log_dir: str, ready, release) -> None:
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    with bounded_file_lock(path / ".search_results.lock", 0.5) as acquired:
        if not acquired:
            raise RuntimeError("could not acquire lock")
        ready.set()
        release.wait(5)


def test_storage_contract_serializes_processes_and_enforces_permissions(tmp_path):
    log_dir = tmp_path / "concurrent"
    log_dir.mkdir(mode=0o755)
    lock_path = log_dir / ".search_results.lock"
    lock_path.touch(mode=0o644)
    if os.name != "nt":
        os.chmod(log_dir, 0o755)
        os.chmod(lock_path, 0o644)
    processes = [multiprocessing.Process(target=_concurrent_writer, args=(str(log_dir), index)) for index in range(12)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0

    entries = _journal_lines(log_dir)
    assert sorted(entry["result"]["index"] for entry in entries) == list(range(12))
    if os.name != "nt":
        journal_path = next(log_dir.glob("search_results_*.jsonl"))
        assert stat.S_IMODE(log_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(journal_path.stat().st_mode) == 0o600
        assert stat.S_IMODE((log_dir / ".search_results.lock").stat().st_mode) == 0o600


def test_storage_contract_retention_only_deletes_expired_regular_journals(tmp_path):
    today = date.today()
    log_dir = tmp_path / "retention"
    log_dir.mkdir()
    keep_boundary = log_dir / f"search_results_{(today - timedelta(days=29)):%Y%m%d}.jsonl"
    expired = log_dir / f"search_results_{(today - timedelta(days=30)):%Y%m%d}.jsonl"
    unrelated = log_dir / "smart_search_20000101.log"
    malformed = log_dir / "search_results_20261340.jsonl"
    directory = log_dir / "search_results_20000101.jsonl"
    for path in (keep_boundary, expired, unrelated, malformed):
        path.write_text("keep", encoding="utf-8")
    directory.mkdir()

    config = SimpleNamespace(
        result_journal_enabled=True,
        result_journal_retention_days=30,
        log_dir=log_dir,
        configured_credentials=[],
    )
    outcome = SearchResultJournal(config).write({"ok": True})

    assert outcome.written is True
    assert keep_boundary.exists()
    assert not expired.exists()
    assert unrelated.exists()
    assert malformed.exists()
    assert directory.is_dir()

    permanent = log_dir / "search_results_19990101.jsonl"
    permanent.write_text("keep", encoding="utf-8")
    config.result_journal_retention_days = 0
    assert SearchResultJournal(config).write({"ok": True}).written is True
    assert permanent.exists()

    config.result_journal_retention_days = 10**12
    assert SearchResultJournal(config).write({"ok": True}).written is True
    assert permanent.exists()


def test_storage_contract_lock_wait_is_bounded_and_non_destructive(tmp_path):
    log_dir = tmp_path / "locked"
    ready = multiprocessing.Event()
    release = multiprocessing.Event()
    holder = multiprocessing.Process(target=_hold_journal_lock, args=(str(log_dir), ready, release))
    holder.start()
    assert ready.wait(5)
    config = SimpleNamespace(
        result_journal_enabled=True,
        result_journal_retention_days=30,
        log_dir=log_dir,
        configured_credentials=[],
    )
    outcome = SearchResultJournal(config).write({"ok": True})
    release.set()
    holder.join(5)

    assert holder.exitcode == 0
    assert outcome.written is False
    assert "0.5 seconds" in outcome.warning
    assert not list(log_dir.glob("search_results_*.jsonl"))
