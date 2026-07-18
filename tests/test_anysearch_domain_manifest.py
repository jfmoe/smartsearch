import json
import hashlib
from pathlib import Path

import httpx
import pytest

from smart_search import service
from smart_search.providers.anysearch import AnySearchProvider, get_verified_domain_manifest


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "anysearch"
CANDIDATES = ("academic.search", "security.vuln", "finance.fundamental", "code.doc")


def _fixture(candidate: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{candidate}.json").read_text(encoding="utf-8"))


def _transport_for(fixture: dict, response_kind: str = "valid_result") -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        arguments = payload["params"]["arguments"]
        if payload["params"]["name"] == "get_sub_domains":
            result = {
                "structuredContent": {
                    "sub_domains": [
                        {
                            "sub_domain": fixture["sub_domain"],
                            "parameters": fixture["parameter_schema"],
                        }
                    ]
                },
                "content": [],
            }
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})
        if "domain" not in arguments:
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": fixture["valid_result"]},
            )
        assert arguments["domain"] == fixture["domain"]
        assert arguments["sub_domain"] == fixture["sub_domain"]
        if response_kind == "missing_required_error":
            required = fixture["parameter_schema"]["required"]
            assert arguments["sub_domain_params"] == {}
            assert all(key not in arguments["sub_domain_params"] for key in required)
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "error": fixture["missing_required_error"]},
            )
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": fixture[response_kind]},
        )

    return httpx.MockTransport(handler)


def _patch_transport(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr("smart_search.providers.anysearch.httpx.AsyncClient", client_factory)


def test_verified_domain_manifest_is_runtime_readable_and_initially_empty(monkeypatch):
    monkeypatch.setenv("ANYSEARCH_API_KEY", "configured-key")

    manifest = get_verified_domain_manifest()
    status = service.get_capability_status()["vertical_search"]

    assert manifest["schema_version"] == 1
    assert manifest["verified_domains"] == []
    assert [item["id"] for item in manifest["candidate_assessments"]] == list(CANDIDATES)
    assert {item["status"] for item in manifest["candidate_assessments"]} == {"discovered_unverified"}
    assert status["configured"] == ["anysearch"]
    assert status["automatic_vertical_discovery"] is True
    assert status["experimental"] is True
    assert status["operation_live"] == {
        "discover_domains": {"status": "not_checked"},
        "vertical_discovery": {"status": "not_checked"},
        "vertical_search": {"status": "not_checked"},
        "batch_discovery": {"status": "not_checked"},
        "anysearch_extraction": {"status": "not_checked"},
    }
    assert status["verified_domains"] == []
    assert status["verified_domain_count"] == 0
    assert status["domain_search_ready"] is False
    assert [item["id"] for item in status["domain_assessments"]] == list(CANDIDATES)


def test_candidate_schema_fingerprints_match_versioned_sanitized_fixtures():
    manifest = get_verified_domain_manifest()

    for assessment in manifest["candidate_assessments"]:
        fixture = _fixture(assessment["id"])
        canonical = json.dumps(fixture["parameter_schema"], sort_keys=True, separators=(",", ":"))
        fingerprint = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
        assert assessment["schema_fingerprint"] == fingerprint
        assert fixture["provenance"] == "synthetic_mock"
        assert assessment["acceptance_date"] is None
        assert assessment["gaps"]

    assert "security.cve" not in {item["id"] for item in manifest["candidate_assessments"]}


@pytest.mark.asyncio
@pytest.mark.parametrize("candidate", CANDIDATES)
async def test_candidate_discovery_and_valid_search_cross_real_transport(monkeypatch, candidate):
    fixture = _fixture(candidate)
    _patch_transport(monkeypatch, _transport_for(fixture))
    provider = AnySearchProvider("https://mock.anysearch.invalid/mcp", "test-key")

    discovery = await provider.discover_domains(fixture["domain"])
    result = await service.anysearch_search(
        f"accept {candidate}",
        domain=fixture["domain"],
        sub_domain=fixture["sub_domain"],
        sub_domain_params=fixture["valid_params"],
    )

    assert discovery["results"][0]["parameter_schema"] == fixture["parameter_schema"]
    assert result["ok"] is True
    assert result["domain_status"] == "discovered_unverified"
    assert result["schema_validation"]["status"] == "unavailable"
    if candidate in {"academic.search", "code.doc"}:
        assert result["results"][0]["url"].startswith("https://")
    else:
        assert result["results"][0]["url"] == ""
        assert result["results"][0]["evidence_type"] == "structured"


@pytest.mark.asyncio
@pytest.mark.parametrize("candidate", CANDIDATES)
async def test_candidate_missing_required_params_is_stable_provider_parameter_error(monkeypatch, candidate):
    fixture = _fixture(candidate)
    _patch_transport(monkeypatch, _transport_for(fixture, "missing_required_error"))

    result = await service.anysearch_search(
        f"missing params for {candidate}",
        domain=fixture["domain"],
        sub_domain=fixture["sub_domain"],
        sub_domain_params={},
    )

    assert result["ok"] is False
    assert result["error_type"] == "parameter_error"
    assert result["domain_status"] == "discovered_unverified"


@pytest.mark.asyncio
@pytest.mark.parametrize("candidate", CANDIDATES)
async def test_candidate_provider_error_has_stable_classification(monkeypatch, candidate):
    fixture = _fixture(candidate)
    _patch_transport(monkeypatch, _transport_for(fixture, "provider_error"))

    result = await service.anysearch_search(
        f"provider error for {candidate}",
        domain=fixture["domain"],
        sub_domain=fixture["sub_domain"],
        sub_domain_params=fixture["valid_params"],
    )

    assert result["ok"] is False
    assert result["error_type"] == "provider_error"
    assert result["domain_status"] == "discovered_unverified"


@pytest.mark.asyncio
async def test_live_discovery_and_domainless_search_cannot_promote_or_infer_a_domain(monkeypatch):
    fixture = _fixture("security.vuln")
    _patch_transport(monkeypatch, _transport_for(fixture))
    provider = AnySearchProvider("https://mock.anysearch.invalid/mcp")

    await provider.discover_domains("security")
    domainless = await provider.vertical_search("find a vulnerability")

    assert get_verified_domain_manifest()["verified_domains"] == []
    assert domainless["operation"] == "vertical_discovery"
    assert "domain" not in domainless
    assert "sub_domain" not in domainless
    assert "domain_status" not in domainless
