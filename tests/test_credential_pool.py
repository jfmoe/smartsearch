"""Provider Credential Pool — resolve, claim-advance, rate-limit rotation, masking."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from smart_search.config import Config
from smart_search.credential_pool import (
    CredentialPoolError,
    ProviderCredentialPool,
    resolve_credentials,
)


def _pool(tmp_path: Path, config: Config | None = None) -> ProviderCredentialPool:
    return ProviderCredentialPool(config or Config(), state_dir=tmp_path)


# --- resolve ---


def test_resolve_keys_only_after_strip_and_dedupe():
    credentials = resolve_credentials(
        keys_raw=json.dumps([" alpha ", "", "beta", "alpha", "beta "]),
        key_raw="ignored-single",
    )
    assert credentials == ["alpha", "beta"]


def test_resolve_single_key_when_keys_absent_or_empty():
    assert resolve_credentials(keys_raw=None, key_raw=" solo ") == ["solo"]
    assert resolve_credentials(keys_raw="", key_raw="solo") == ["solo"]
    assert resolve_credentials(keys_raw="[]", key_raw="solo") == ["solo"]
    assert resolve_credentials(keys_raw='["", "  "]', key_raw="solo") == ["solo"]


def test_resolve_empty_when_neither_configured():
    assert resolve_credentials(keys_raw=None, key_raw=None) == []
    assert resolve_credentials(keys_raw="[]", key_raw="") == []


def test_resolve_invalid_keys_json_is_configuration_error():
    with pytest.raises(CredentialPoolError, match="JINA_API_KEYS|JSON|array"):
        resolve_credentials(keys_raw="not-json", key_raw="solo")
    with pytest.raises(CredentialPoolError):
        resolve_credentials(keys_raw='{"k":1}', key_raw="solo")
    with pytest.raises(CredentialPoolError):
        resolve_credentials(keys_raw='[1, 2]', key_raw="solo")


def test_pool_resolve_jina_from_config(monkeypatch, tmp_path):
    config = Config()
    monkeypatch.setenv("JINA_API_KEYS", json.dumps(["k1", "k2"]))
    monkeypatch.setenv("JINA_API_KEY", "single")
    pool = _pool(tmp_path, config)
    assert pool.resolve("jina") == ["k1", "k2"]


def test_pool_resolve_jina_falls_back_to_single_key(monkeypatch, tmp_path):
    config = Config()
    monkeypatch.setenv("JINA_API_KEY", "only-one")
    pool = _pool(tmp_path, config)
    assert pool.resolve("jina") == ["only-one"]


def test_pool_resolve_rejects_non_allowlisted_provider(tmp_path):
    pool = _pool(tmp_path)
    with pytest.raises(CredentialPoolError, match="allowlist|not supported"):
        pool.resolve("xai-responses")


# --- claim / advance ---


def test_claim_advances_cursor_modulo_pool_size(tmp_path):
    pool = _pool(tmp_path)
    assert pool.claim_start_index("jina", 3) == 0
    assert pool.claim_start_index("jina", 3) == 1
    assert pool.claim_start_index("jina", 3) == 2
    assert pool.claim_start_index("jina", 3) == 0


def test_claim_state_file_stores_indices_only(tmp_path):
    pool = _pool(tmp_path)
    pool.claim_start_index("jina", 2)
    state_path = tmp_path / "credential_pool_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(state.keys()) == {"jina"}
    assert set(state["jina"].keys()) == {"next_index"}
    assert state["jina"]["next_index"] == 1
    assert isinstance(state["jina"]["next_index"], int)


# --- execute with rotation ---


@pytest.mark.asyncio
async def test_rotation_succeeds_on_first_credential(tmp_path):
    pool = _pool(tmp_path)
    calls: list[tuple[str, int]] = []

    async def attempt(credential: str, index: int) -> dict:
        calls.append((credential, index))
        return {"ok": True, "content": f"from-{credential}"}

    result = await pool.execute_with_rotation(
        "jina",
        attempt,
        credentials=["a", "b", "c"],
    )
    assert result["ok"] is True
    assert result["content"] == "from-a"
    assert result["key_index"] == 0
    assert result.get("credential_rotated") is not True
    assert calls == [("a", 0)]


@pytest.mark.asyncio
async def test_rotation_on_rate_limited_then_success(tmp_path):
    pool = _pool(tmp_path)
    # Consume first claim so start index is 0 still after reset via fresh pool dir.

    async def attempt(credential: str, index: int) -> dict:
        if credential == "first":
            return {"ok": False, "error_type": "rate_limited", "error": "429"}
        return {"ok": True, "content": "ok-second"}

    result = await pool.execute_with_rotation(
        "jina",
        attempt,
        credentials=["first", "second"],
    )
    assert result["ok"] is True
    assert result["content"] == "ok-second"
    assert result["key_index"] == 1
    assert result["credential_rotated"] is True


@pytest.mark.asyncio
async def test_rotation_stops_on_auth_error_without_burning_pool(tmp_path):
    pool = _pool(tmp_path)
    calls: list[str] = []

    async def attempt(credential: str, index: int) -> dict:
        calls.append(credential)
        return {"ok": False, "error_type": "auth_error", "error": "401"}

    result = await pool.execute_with_rotation(
        "jina",
        attempt,
        credentials=["bad", "good"],
    )
    assert result["error_type"] == "auth_error"
    assert calls == ["bad"]


@pytest.mark.asyncio
async def test_rotation_all_rate_limited_one_full_pass(tmp_path):
    pool = _pool(tmp_path)
    calls: list[str] = []

    async def attempt(credential: str, index: int) -> dict:
        calls.append(credential)
        return {"ok": False, "error_type": "rate_limited", "error": "429"}

    result = await pool.execute_with_rotation(
        "jina",
        attempt,
        credentials=["a", "b", "c"],
    )
    assert result["error_type"] == "rate_limited"
    assert calls == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_rotation_each_credential_at_most_once(tmp_path):
    pool = _pool(tmp_path)
    # Pre-advance so start index is 1.
    pool.claim_start_index("jina", 3)
    calls: list[int] = []

    async def attempt(credential: str, index: int) -> dict:
        calls.append(index)
        return {"ok": False, "error_type": "rate_limited", "error": "429"}

    await pool.execute_with_rotation(
        "jina",
        attempt,
        credentials=["a", "b", "c"],
    )
    assert calls == [1, 2, 0]
    assert len(calls) == len(set(calls))


# --- safe status / masking ---


def test_safe_status_reports_enablement_count_and_masks(monkeypatch, tmp_path):
    monkeypatch.setenv("JINA_API_KEYS", json.dumps(["jina-secret-key-one", "jina-secret-key-two"]))
    pool = _pool(tmp_path)
    status = pool.safe_status("jina")
    assert status["configured"] is True
    assert status["enabled"] is True
    assert status["key_count"] == 2
    text = json.dumps(status)
    assert "jina-secret-key-one" not in text
    assert "jina-secret-key-two" not in text
    assert status["masked_keys"][0] != "jina-secret-key-one"


def test_config_masks_jina_api_keys_array(monkeypatch, tmp_path):
    config = Config()
    secret_a = "jina-aaaa1111bbbb"
    secret_b = "jina-cccc2222dddd"
    config.set_config_value("JINA_API_KEYS", json.dumps([secret_a, secret_b]))
    saved = config.get_saved_config(masked=True)
    assert secret_a not in saved["JINA_API_KEYS"]
    assert secret_b not in saved["JINA_API_KEYS"]
    info = config.get_config_info()
    assert secret_a not in json.dumps(info)
    assert secret_b not in json.dumps(info)
    assert info["JINA_API_KEYS"] != "未配置"
    assert info.get("jina_credential_pool", {}).get("key_count") == 2


def test_jina_keys_only_counts_as_configured(monkeypatch, tmp_path):
    from smart_search import service

    monkeypatch.setenv("JINA_API_KEYS", json.dumps(["pool-only-key-aaaa"]))
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    assert service._provider_configured("jina") is True
    status = service.get_capability_status()
    assert "jina" in status["web_fetch"]["configured"]


# --- Jina wiring with HTTP mocks ---


class FakeJinaClient:
    responses: list[httpx.Response | Exception] = []
    calls: list[dict] = []

    def __init__(self, timeout, follow_redirects=True):
        self.timeout = timeout
        self.follow_redirects = follow_redirects

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, headers):
        self.__class__.calls.append({"url": url, "headers": headers})
        item = self.__class__.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.asyncio
async def test_jina_call_rotates_on_429_with_pool(monkeypatch, tmp_path):
    from smart_search import service

    FakeJinaClient.calls = []
    FakeJinaClient.responses = [
        httpx.Response(
            429,
            text="rate limited",
            request=httpx.Request("GET", "https://r.jina.ai/https://example.com"),
        ),
        httpx.Response(
            200,
            text="Title: OK\n\nBody from second key.",
            request=httpx.Request("GET", "https://r.jina.ai/https://example.com"),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.jina.httpx.AsyncClient", FakeJinaClient)
    monkeypatch.setenv("JINA_API_KEYS", json.dumps(["key-first-zzzz", "key-second-yyyy"]))
    # Isolate pool state under tmp config dir already set by conftest.

    data = await service.call_jina_reader("https://example.com")
    assert data["ok"] is True
    assert "Body from second key" in data["content"]
    assert data.get("credential_rotated") is True
    assert data.get("key_index") == 1
    assert len(FakeJinaClient.calls) == 2
    assert FakeJinaClient.calls[0]["headers"]["Authorization"] == "Bearer key-first-zzzz"
    assert FakeJinaClient.calls[1]["headers"]["Authorization"] == "Bearer key-second-yyyy"
    # Secrets must not appear in error-free result JSON beyond intentional absence.
    dumped = json.dumps(data)
    assert "key-first-zzzz" not in dumped
    assert "key-second-yyyy" not in dumped


@pytest.mark.asyncio
async def test_jina_call_single_key_unchanged(monkeypatch):
    from smart_search import service

    FakeJinaClient.calls = []
    FakeJinaClient.responses = [
        httpx.Response(
            200,
            text="single key content",
            request=httpx.Request("GET", "https://r.jina.ai/https://example.com"),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.jina.httpx.AsyncClient", FakeJinaClient)
    monkeypatch.setenv("JINA_API_KEY", "solo-key-wwww")

    data = await service.call_jina_reader("https://example.com")
    assert data["ok"] is True
    assert FakeJinaClient.calls[0]["headers"]["Authorization"] == "Bearer solo-key-wwww"
    assert data.get("credential_rotated") is not True


@pytest.mark.asyncio
async def test_jina_invalid_keys_json_fail_closed_does_not_use_single_key(monkeypatch):
    from smart_search import service

    FakeJinaClient.calls = []
    FakeJinaClient.responses = [
        httpx.Response(
            200,
            text="should not be reached",
            request=httpx.Request("GET", "https://r.jina.ai/https://example.com"),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.jina.httpx.AsyncClient", FakeJinaClient)
    monkeypatch.setenv("JINA_API_KEYS", "not-a-json-array")
    monkeypatch.setenv("JINA_API_KEY", "solo-should-not-be-used")

    data = await service.call_jina_reader("https://example.com")
    assert data["ok"] is False
    assert data["error_type"] == "config_error"
    assert "JINA_API_KEYS" in data["error"] or "JSON" in data["error"]
    assert FakeJinaClient.calls == []
    assert "solo-should-not-be-used" not in json.dumps(data)
