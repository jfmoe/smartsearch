from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from smart_search.intent_catalog import render_skill_capability_reference


ROOT = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = ROOT / "scripts" / "sync-skill.py"
PUBLIC_SKILL_PATH = Path("skills/smart-search-cli")
PACKAGED_SKILL_PATH = Path(
    "src/smart_search/assets/skills/smart-search-cli"
)
VALID_SKILL_DOCUMENT = (
    "---\nname: smart-search-cli\ndescription: Test skill.\n---\n"
    "Read `references/guide.md`.\n"
)


def _project_fixture(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    (project_root / "scripts").mkdir(parents=True)
    shutil.copy2(SYNC_SCRIPT, project_root / "scripts" / SYNC_SCRIPT.name)
    return project_root


def _skill_files(skill_root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(skill_root).as_posix(): path.read_bytes()
        for path in sorted(skill_root.rglob("*"))
        if path.is_file()
    }


def _run_sync(project_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/sync-skill.py", *args],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sync_creates_a_repeatable_strict_mirror(tmp_path: Path) -> None:
    project_root = _project_fixture(tmp_path)
    public_skill = project_root / PUBLIC_SKILL_PATH
    packaged_skill = project_root / PACKAGED_SKILL_PATH
    (public_skill / "references").mkdir(parents=True)
    (public_skill / "SKILL.md").write_text(
        VALID_SKILL_DOCUMENT,
        encoding="utf-8",
    )
    (public_skill / "references" / "guide.md").write_bytes(b"guide\n")
    (packaged_skill / "references").mkdir(parents=True)
    (packaged_skill / "references" / "stale.md").write_bytes(b"stale\n")

    first = _run_sync(project_root)
    first_files = _skill_files(packaged_skill)
    second = _run_sync(project_root)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first_files == _skill_files(public_skill)
    assert _skill_files(packaged_skill) == first_files
    assert not (packaged_skill / "references" / "stale.md").exists()


def test_check_reports_every_kind_of_mirror_drift(tmp_path: Path) -> None:
    project_root = _project_fixture(tmp_path)
    public_skill = project_root / PUBLIC_SKILL_PATH
    packaged_skill = project_root / PACKAGED_SKILL_PATH
    (public_skill / "references").mkdir(parents=True)
    (public_skill / "SKILL.md").write_text(
        VALID_SKILL_DOCUMENT,
        encoding="utf-8",
    )
    (public_skill / "references" / "guide.md").write_text(
        "guide\n", encoding="utf-8"
    )
    assert _run_sync(project_root).returncode == 0
    assert _run_sync(project_root, "--check").returncode == 0

    (public_skill / "references" / "new.md").write_text("new\n", encoding="utf-8")
    (packaged_skill / "references" / "guide.md").unlink()
    (packaged_skill / "SKILL.md").write_text("drifted\n", encoding="utf-8")
    (packaged_skill / "references" / "stale.md").write_text(
        "stale\n", encoding="utf-8"
    )

    result = _run_sync(project_root, "--check")

    assert result.returncode == 1
    assert "missing from package: references/guide.md" in result.stderr
    assert "missing from package: references/new.md" in result.stderr
    assert "unexpected in package: references/stale.md" in result.stderr
    assert "content differs: SKILL.md" in result.stderr


@pytest.mark.parametrize(
    ("skill_text", "expected_error"),
    [
        (None, "required file is missing: SKILL.md"),
        (
            "# No frontmatter\n",
            "SKILL.md must begin and end with YAML frontmatter",
        ),
        (
            "---\ndescription: Test skill.\n---\n",
            "frontmatter field is required: name",
        ),
        (
            "---\nname: smart-search-cli\n---\n",
            "frontmatter field is required: description",
        ),
    ],
)
def test_check_rejects_invalid_main_skill_document(
    tmp_path: Path,
    skill_text: str | None,
    expected_error: str,
) -> None:
    project_root = _project_fixture(tmp_path)
    public_skill = project_root / PUBLIC_SKILL_PATH
    public_skill.mkdir(parents=True)
    if skill_text is not None:
        (public_skill / "SKILL.md").write_text(skill_text, encoding="utf-8")

    result = _run_sync(project_root, "--check")

    assert result.returncode == 1
    assert expected_error in result.stderr


def test_check_rejects_a_missing_context_pointer_target(tmp_path: Path) -> None:
    project_root = _project_fixture(tmp_path)
    public_skill = project_root / PUBLIC_SKILL_PATH
    public_skill.mkdir(parents=True)
    (public_skill / "SKILL.md").write_text(
        "---\nname: smart-search-cli\ndescription: Test skill.\n---\n"
        "Read `references/missing.md`.\n",
        encoding="utf-8",
    )

    result = _run_sync(project_root, "--check")

    assert result.returncode == 1
    assert (
        "context pointer target is missing: references/missing.md"
        in result.stderr
    )


def test_generated_capability_reference_and_package_mirror_have_no_drift() -> None:
    expected = render_skill_capability_reference()
    relative_path = Path("references/intent-routing-capabilities.md")

    assert (ROOT / PUBLIC_SKILL_PATH / relative_path).read_text(encoding="utf-8") == expected
    assert (ROOT / PACKAGED_SKILL_PATH / relative_path).read_text(encoding="utf-8") == expected
    result = _run_sync(ROOT, "--check")
    assert result.returncode == 0, result.stderr


def test_agent_search_contract_declares_capabilities_without_route_preflight() -> None:
    for skill_root in (PUBLIC_SKILL_PATH, PACKAGED_SKILL_PATH):
        skill = (ROOT / skill_root / "SKILL.md").read_text(encoding="utf-8")
        patterns = (ROOT / skill_root / "references/command-patterns.md").read_text(encoding="utf-8")
        deep = (ROOT / skill_root / "references/deep-research-mode.md").read_text(encoding="utf-8")

        assert "references/intent-routing-capabilities.md" in skill
        assert "--capabilities none" in patterns
        assert "--capabilities docs_search,web_search" in patterns
        research_branch = skill.split("### 1. Research or retrieval", 1)[1].split("### 2.", 1)[0]
        assert "ordinary search begins with `search`" in research_branch
        assert "only for an explicit routing diagnostic" in research_branch
        assert '"command": "smart-search search \\"query\\" --capabilities none' in deep
        assert "`smart-search research` keeps its separate" in deep
