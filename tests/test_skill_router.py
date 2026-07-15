from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAIN_SKILL = ROOT / "skills" / "smart-search-cli" / "SKILL.md"
REFERENCE_DIR = MAIN_SKILL.parent / "references"


def _main_skill_text() -> str:
    return MAIN_SKILL.read_text(encoding="utf-8")


def _branch(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n### ", start + len(heading))
    if end == -1:
        end = len(text)
    return text[start:end]


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    if end == -1:
        end = len(text)
    return text[start:end]


def test_ordinary_research_branch_routes_by_capability() -> None:
    branch = _branch(_main_skill_text(), "### 1. Research or retrieval")

    assert "Choose this branch when" in branch
    assert "capability" in branch
    assert "`references/provider-routing.md`" in branch
    assert "`references/command-patterns.md`" in branch
    assert "`references/deep-research-mode.md`" in branch
    assert "Completion criterion:" in branch
    assert "requested output" in branch


def test_diagnosis_branch_recovers_or_reports_an_explicit_failure() -> None:
    branch = _branch(_main_skill_text(), "### 2. Diagnose or configure")

    assert "Choose this branch when" in branch
    assert "smart-search doctor --format json" in branch
    assert "smart-search setup" in branch
    assert "`references/setup-config.md`" in branch
    assert "Completion criterion:" in branch
    assert "explicitly report" in branch


def test_skill_update_branch_requires_request_and_observed_staleness() -> None:
    branch = _branch(_main_skill_text(), "### 3. Update an installed Skill")

    assert "Choose this branch when" in branch
    assert "explicitly asks" in branch
    assert "`stale`" in branch
    assert "smart-search skills status" in branch
    assert "smart-search skills update" in branch
    assert "`references/setup-config.md`" in branch
    assert "Completion criterion:" in branch
    assert "`up_to_date`" in branch


def test_architecture_change_branch_requires_distributable_validation() -> None:
    branch = _branch(_main_skill_text(), "### 4. Validate architecture changes")

    assert "Choose this branch when" in branch
    assert "CLI or provider architecture" in branch
    assert "scripts/sync-skill.py --check" in branch
    assert "smart-search regression" in branch
    assert "smart-search smoke --mock --format json" in branch
    assert "`references/provider-routing.md`" in branch
    assert "`references/regression-release.md`" in branch
    assert "Completion criterion:" in branch
    assert "exit successfully" in branch


def test_top_level_keeps_exactly_four_cross_branch_invariants() -> None:
    text = _main_skill_text()
    section = _section(text, "## Cross-branch invariants")
    invariants = [line for line in section.splitlines() if line.startswith("- ")]

    assert len(invariants) == 4
    assert "CLI-first" in section
    assert "same capability" in section
    assert "high-risk or time-sensitive" in section
    assert "fetch" in section
    assert "API keys" in section
    assert "explicitly report" in section
    assert "## Routing" not in text
    assert "## Key Boundaries" not in text


def test_public_skill_exposes_exactly_six_functional_references() -> None:
    expected_references = {
        "cli-core.md",
        "command-patterns.md",
        "deep-research-mode.md",
        "provider-routing.md",
        "regression-release.md",
        "setup-config.md",
    }
    actual_references = {path.name for path in REFERENCE_DIR.glob("*.md")}
    text = _main_skill_text()

    assert actual_references == expected_references
    for reference in expected_references:
        assert f"`references/{reference}`" in text
    assert "cli-contract.md" not in text
