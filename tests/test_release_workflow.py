import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOLVER = ROOT / "npm" / "scripts" / "resolve-prerelease-version.js"
WORKFLOW = ROOT / ".github" / "workflows" / "publish-npm.yml"


def read_reference_tree(skill_dir: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((skill_dir / "references").rglob("*"))
        if p.is_file() and p.suffix == ".md"
    )


def run_resolver(base_version: str, versions: list[str]) -> str:
    result = subprocess.run(
        [
            "node",
            str(RESOLVER),
            "--package",
            "@konbakuyomu/smart-search",
            "--base",
            base_version,
            "--id",
            "beta",
            "--versions-json",
            json.dumps(versions),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def test_resolver_counts_legacy_dev_slots_per_base_version():
    versions = [
        "0.1.9-dev.30",
        "0.1.9",
        "0.1.10-dev.32",
        "0.1.10-dev.34",
        "0.1.10",
    ]

    assert run_resolver("0.1.9", versions) == "0.1.9-beta.2"
    assert run_resolver("0.1.10", versions) == "0.1.10-beta.3"


def test_resolver_prefers_existing_beta_numbers_when_higher_than_legacy_count():
    versions = [
        "0.1.10-dev.32",
        "0.1.10-dev.34",
        "0.1.10-beta.5",
        "0.1.10",
    ]

    assert run_resolver("0.1.10", versions) == "0.1.10-beta.6"


def test_resolver_starts_at_beta_one_without_prior_versions():
    assert run_resolver("0.2.0", []) == "0.2.0-beta.1"


def test_publish_workflow_separates_main_tests_from_explicit_release_lanes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    main_job = workflow.split("\n  main-test:\n", 1)[1].split(
        "\n  preview-publish:\n", 1
    )[0]
    preview_job = workflow.split("\n  preview-publish:\n", 1)[1].split(
        "\n  stable-publish:\n", 1
    )[0]
    stable_job = workflow.split("\n  stable-publish:\n", 1)[1]

    assert "branches:" in workflow
    assert "- main" in workflow
    assert "workflow_dispatch:" in workflow
    assert "target_sha:" in workflow
    assert "full 40-character commit SHA" in workflow
    assert 'if [[ ! "$target_sha" =~ ^[0-9a-f]{40}$ ]]; then' in workflow
    assert "github.event.inputs.target_sha" in workflow
    assert "github.event.inputs.version" in workflow
    assert "github.event_name == 'push' && github.ref_type == 'branch'" in main_job
    assert "npm test" in main_job
    assert "npm publish" not in main_job
    assert "id-token: write" not in main_job
    assert "contents: write" not in main_job
    assert "github.event_name == 'workflow_dispatch'" in preview_job
    assert "TARGET_SHA: ${{ github.event.inputs.target_sha }}" in preview_job
    assert "PREVIEW_VERSION: ${{ github.event.inputs.version }}" in preview_job
    assert 'target_sha="${{ github.event.inputs.target_sha }}"' not in preview_job
    assert 'version="${{ github.event.inputs.version }}"' not in preview_job
    assert "npm publish --access public --provenance --tag next" in preview_job
    assert "github.event_name == 'push' && github.ref_type == 'tag'" in stable_job
    assert (
        'if [[ ! "$GITHUB_REF_NAME" =~ ^v[0-9]+\\.[0-9]+\\.[0-9]+$ ]]; then'
        in stable_job
    )
    assert "npm publish --access public --provenance --tag latest" in stable_job
    assert "permissions: {}" in workflow
    assert "contents: read" in main_job
    assert "id-token: write" in preview_job
    assert "id-token: write" in stable_job
    assert "gh release create" in stable_job


def test_release_docs_explain_beta_lane_and_npm_immutability():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    public_contract = read_reference_tree(ROOT / "skills" / "smart-search-cli")
    packaged_contract = read_reference_tree(
        ROOT / "src" / "smart_search" / "assets" / "skills" / "smart-search-cli"
    )

    required_markers = [
        "Release lanes",
        "<package.json version>-beta.N",
        "dist-tag `next`",
        "0.1.10-beta.3",
        "chore(release): bump version to X.Y.Z",
        ".github/releases/vX.Y.Z.md",
        "vX.Y.Z",
        "workflow_dispatch",
        "target_ref",
        "npm versions are immutable",
        "cannot be renamed in place",
        "Release closeout checklist",
        "create_github_release=false",
        "gh release create vX.Y.Z-beta.N",
        "npm `E409`",
        "machine-readable gap check",
        "mise use -g",
        "non-ASCII JSON",
        "ConvertFrom-Json",
    ]
    for marker in required_markers:
        assert marker in readme
    zh_required_markers = [
        "发布通道",
        "<package.json version>-beta.N",
        "npm `next`",
        "0.1.10-beta.3",
        ".github/releases/vX.Y.Z.md",
        "npm 版本不可变",
        "gh release list",
        "npm `E409`",
        "smart-search regression",
        "smart-search smoke --mock --format json",
        "ConvertFrom-Json",
    ]
    for marker in zh_required_markers:
        assert marker in readme_zh
    contract_markers = [
        "Release Lanes",
        "<package.json version>-beta.N",
        "chore(release): bump version to X.Y.Z",
        ".github/releases/vX.Y.Z.md",
        "npm versions are immutable",
        "Release Closeout Lessons",
        "GitHub release creation fails",
        "npm `E409`",
        "diff-style gap check",
        "smart-search smoke --mock --format json",
        "Windows npm/mise wrapper is emitting UTF-8 JSON",
    ]
    for marker in contract_markers:
        assert marker in public_contract
        assert marker in packaged_contract


def test_current_stable_release_notes_describe_user_visible_changes():
    notes = (ROOT / ".github" / "releases" / "v0.1.14.md").read_text(encoding="utf-8")

    required_markers = [
        "GitHub issue #7",
        "smart-search skills status",
        "smart-search skills update",
        "smart-search diagnose openai-compatible",
        "Context7",
        "Exa",
        "Validation",
    ]
    for marker in required_markers:
        assert marker in notes
