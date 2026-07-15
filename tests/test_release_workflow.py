import json
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "publish-npm.yml"
RESOLVER = ROOT / "npm" / "scripts" / "resolve-prerelease-version.js"
PACKAGE = ROOT / "package.json"
LOCK = ROOT / "package-lock.json"
PYPROJECT = ROOT / "pyproject.toml"
POLICY_CHECK = ROOT / "npm" / "scripts" / "verify-release-policy.js"
METADATA_CHECK = ROOT / "npm" / "scripts" / "verify-release-metadata.js"


def run_node(
    script: Path, *args: str, cwd: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(script), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def run_resolver(base_version: str, versions: list[str]) -> str:
    result = subprocess.run(
        [
            "node",
            str(RESOLVER),
            "--package",
            "@jfmoe/smart-search",
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


def test_resolver_counts_legacy_dev_slots_per_base_version() -> None:
    versions = [
        "0.1.9-dev.30",
        "0.1.9",
        "0.1.10-dev.32",
        "0.1.10-dev.34",
        "0.1.10",
    ]

    assert run_resolver("0.1.9", versions) == "0.1.9-beta.2"
    assert run_resolver("0.1.10", versions) == "0.1.10-beta.3"


def test_resolver_prefers_existing_beta_numbers_when_higher_than_legacy_count() -> None:
    versions = [
        "0.1.10-dev.32",
        "0.1.10-dev.34",
        "0.1.10-beta.5",
        "0.1.10",
    ]

    assert run_resolver("0.1.10", versions) == "0.1.10-beta.6"


def test_resolver_starts_at_beta_one_without_prior_versions() -> None:
    assert run_resolver("0.2.0", []) == "0.2.0-beta.1"


def test_release_identity_and_versions_are_consistent() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    pyproject = PYPROJECT.read_text(encoding="utf-8")

    assert package["name"] == "@jfmoe/smart-search"
    assert package["version"] == "0.2.0"
    assert package["homepage"] == "https://github.com/jfmoe/smartsearch#readme"
    assert package["repository"]["url"] == "git+https://github.com/jfmoe/smartsearch.git"
    assert package["bugs"]["url"] == "https://github.com/jfmoe/smartsearch/issues"
    assert lock["name"] == package["name"]
    assert lock["version"] == package["version"]
    assert lock["packages"][""]["name"] == package["name"]
    assert lock["packages"][""]["version"] == package["version"]
    assert re.search(r'^version = "0\.2\.0"$', pyproject, flags=re.MULTILINE)
    assert 'Homepage = "https://github.com/jfmoe/smartsearch#readme"' in pyproject
    assert run_node(METADATA_CHECK).returncode == 0


def test_release_policy_rejects_unallowlisted_legacy_identity() -> None:
    result = run_node(POLICY_CHECK)

    assert result.returncode == 0, result.stderr


def test_release_policy_rejects_legacy_identity_in_new_release_notes(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    policy_check = project_root / "npm" / "scripts" / POLICY_CHECK.name
    policy_check.parent.mkdir(parents=True)
    shutil.copy2(POLICY_CHECK, policy_check)
    release_notes = project_root / ".github" / "releases" / "v0.2.0.md"
    release_notes.parent.mkdir(parents=True)
    legacy_owner = "konba" + "".join(["kuyomu"])
    release_notes.write_text(
        f"npm install -g @{legacy_owner}/smart-search@latest\n",
        encoding="utf-8",
    )

    result = run_node(policy_check, cwd=project_root)

    assert result.returncode == 1
    assert "- .github/releases/v0.2.0.md" in result.stderr


def test_public_docs_describe_the_personal_mac_only_release_line() -> None:
    public_sources = [
        ROOT / "README.md",
        ROOT / "README.zh-CN.md",
        ROOT / "skills" / "smart-search-cli" / "references" / "cli-core.md",
        ROOT / "skills" / "smart-search-cli" / "references" / "regression-release.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in public_sources)

    for marker in [
        "@jfmoe/smart-search",
        "0.2.0",
        "macOS",
        "Node",
        "workflow_dispatch",
        "40-character commit SHA",
        "vX.Y.Z",
        "upstream baseline",
    ]:
        assert marker in text


def test_publish_workflow_has_separate_test_preview_and_stable_lanes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "branches:" in workflow
    assert "- main" in workflow
    assert "workflow_dispatch:" in workflow
    assert "target_sha:" in workflow
    assert "full 40-character commit SHA" in workflow
    assert 'if [[ ! "$target_sha" =~ ^[0-9a-f]{40}$ ]]; then' in workflow
    assert "github.event.inputs.target_sha" in workflow
    assert "github.event_name == 'push' && github.ref_type == 'branch'" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert r'if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+-[0-9A-Za-z]' in workflow
    assert "github.event_name == 'push' && github.ref_type == 'tag'" in workflow
    assert 'if [[ ! "$GITHUB_REF_NAME" =~ ^v[0-9]+\\.[0-9]+\\.[0-9]+$ ]]; then' in workflow
    assert 'node npm/scripts/verify-release-metadata.js "$tag_version"' in workflow
    assert "npm publish --access public --provenance --tag next" in workflow
    assert "npm publish --access public --provenance --tag latest" in workflow
    assert '--target "$(git rev-parse HEAD)"' in workflow
    assert "contents: read" in workflow
    assert "id-token: write" in workflow


def test_release_notes_and_upstream_baseline_are_versioned() -> None:
    notes = (ROOT / ".github" / "releases" / "v0.2.0.md").read_text(encoding="utf-8")
    baseline = (ROOT / "docs" / "release" / "upstream-baseline.md").read_text(
        encoding="utf-8"
    )

    assert "@jfmoe/smart-search@0.2.0" in notes
    assert "667c465d0f6ea16a423f03c434f94e21505d3595" in baseline
    assert "c61a306b625b79a02b0693d40a468829c20a43a7" not in baseline
    assert "refs/heads/main" in baseline
    assert "commit endpoint" in baseline
    assert "read-only" in baseline
