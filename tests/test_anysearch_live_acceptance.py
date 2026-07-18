import json
import os
from pathlib import Path

import pytest

from smart_search.providers.anysearch import AnySearchProvider, get_verified_domain_manifest


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "anysearch"
CANDIDATES = ("academic.search", "security.vuln", "finance.fundamental", "code.doc")


@pytest.mark.live_acceptance
@pytest.mark.asyncio
@pytest.mark.parametrize("candidate", CANDIDATES)
async def test_anysearch_candidate_live_acceptance_is_opt_in_and_independent(candidate):
    selected = {item.strip() for item in os.environ.get("ANYSEARCH_LIVE_ACCEPTANCE", "").split(",") if item.strip()}
    if "all" not in selected and candidate not in selected:
        pytest.skip(f"set ANYSEARCH_LIVE_ACCEPTANCE={candidate} to run this independent live check")

    fixture = json.loads((FIXTURE_DIR / f"{candidate}.json").read_text(encoding="utf-8"))
    provider = AnySearchProvider(
        os.environ.get("ANYSEARCH_API_URL", "https://api.anysearch.com/mcp"),
        os.environ.get("ANYSEARCH_API_KEY"),
        float(os.environ.get("ANYSEARCH_TIMEOUT_SECONDS", "30")),
    )

    discovery = await provider.discover_domains(fixture["domain"])
    valid = await provider.vertical_search(
        f"live acceptance for {candidate}",
        domain=fixture["domain"],
        sub_domain=fixture["sub_domain"],
        sub_domain_params=fixture["valid_params"],
        max_results=1,
    )
    missing = await provider.vertical_search(
        f"live missing-parameter acceptance for {candidate}",
        domain=fixture["domain"],
        sub_domain=fixture["sub_domain"],
        sub_domain_params={},
        max_results=1,
    )

    assert discovery["ok"] is True
    assert any(item["sub_domain"] == fixture["sub_domain"] for item in discovery["results"])
    assert valid["ok"] is True
    assert missing["ok"] is False
    assert missing["error_type"] == "parameter_error"
    assert get_verified_domain_manifest()["verified_domains"] == []
