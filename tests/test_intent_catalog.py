from smart_search.intent_catalog import (
    CAPABILITY_IDS,
    INTENT_ROUTING_CATALOG,
    calibration_cases,
    classifier_prompt_material,
    ordered_capabilities,
    render_skill_capability_reference,
    rule_terms,
    semantic_examples,
)
from smart_search import intent_router, service


def test_catalog_is_the_complete_ordered_capability_source() -> None:
    assert CAPABILITY_IDS == (
        "docs_search",
        "web_search",
        "web_fetch",
        "vertical_search",
    )
    assert tuple(INTENT_ROUTING_CATALOG) == CAPABILITY_IDS
    assert ordered_capabilities({"vertical_search", "docs_search"}) == [
        "docs_search",
        "vertical_search",
    ]

    for capability in INTENT_ROUTING_CATALOG.values():
        assert capability.description
        assert capability.select_when
        assert capability.do_not_select_when
        assert capability.rule_terms
        assert capability.semantic_examples
        assert capability.calibration_examples


def test_catalog_public_consumers_return_catalog_owned_material() -> None:
    assert "api" in rule_terms("docs_search")
    assert "接口" in rule_terms("docs_search", localized_only=True)
    assert "今天" in rule_terms("web_search", localized_only=True)
    assert "game walkthrough" in rule_terms("vertical_search")
    assert semantic_examples("web_fetch")[0].startswith("verify the claim")

    cases = calibration_cases()
    assert any(case.expected_capabilities == () for case in cases)
    assert any(case.expected_capabilities == ("vertical_search",) for case in cases)

    material = classifier_prompt_material()
    assert material["allowed_capabilities"] == list(CAPABILITY_IDS)
    assert [item["id"] for item in material["capability_definitions"]] == list(CAPABILITY_IDS)
    assert all(item["select_when"] and item["do_not_select_when"] for item in material["capability_definitions"])


def test_generated_skill_reference_is_concise_and_catalog_derived() -> None:
    reference = render_skill_capability_reference()

    assert reference.startswith("# Intent Routing Capabilities\n")
    for capability_id in CAPABILITY_IDS:
        assert f"## `{capability_id}`" in reference
    assert "Select when:" in reference
    assert "Do not select when:" in reference
    assert "provider" in reference.lower()
    assert "INTENT_EMBEDDING_THRESHOLD" not in reference


def test_rules_embeddings_and_calibration_consume_catalog_interfaces() -> None:
    assert intent_router.DOCS_INTENT_KEYWORDS == rule_terms("docs_search")
    assert intent_router.CURRENT_INTENT_KEYWORDS == rule_terms("web_search")
    assert intent_router.ZH_CURRENT_INTENT_KEYWORDS == rule_terms("web_search", localized_only=True)
    assert intent_router.FETCH_INTENT_KEYWORDS == rule_terms("web_fetch")
    assert intent_router.VERTICAL_INTENT_KEYWORDS == rule_terms("vertical_search")
    assert intent_router.CAPABILITY_UTTERANCES == {
        capability_id: semantic_examples(capability_id)
        for capability_id in CAPABILITY_IDS
    }

    expected = [
        {
            "id": case.id,
            "query": case.query,
            "expected_capabilities": list(case.expected_capabilities),
            "expected_label": case.expected_capabilities[0] if case.expected_capabilities else "none",
        }
        for case in calibration_cases()
    ]
    assert service._route_calibration_dataset() == expected


def test_classifier_prompt_contract_uses_catalog_and_preserves_schema() -> None:
    prompt = intent_router.build_classifier_prompt(
        "latest SDK docs",
        {"required_capabilities": ["docs_search"]},
        {"top_capability": "web_search"},
    )

    assert prompt["allowed_capabilities"] == list(CAPABILITY_IDS)
    assert prompt["capability_definitions"] == classifier_prompt_material()["capability_definitions"]
    instruction = prompt["instruction"]
    assert "complete capability set" in instruction
    assert "multiple capabilities" in instruction
    assert "empty set" in instruction
    assert "non-authoritative evidence" in instruction
    assert "JSON only" in instruction
    for field in ("required_capabilities", "intent_signals", "confidence", "reasons"):
        assert field in instruction
    assert "provider" in instruction.lower()
