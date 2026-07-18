import json
import os
from pathlib import Path

import pytest

from smart_search import cli


def _run(argv, capsys):
    code = cli.main([*argv, "--format", "json"])
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def test_skills_install_defaults_to_agents_and_preserves_provider_config(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"XAI_MODEL": "grok-test"}), encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: home)

    code, result, stderr = _run(["skills", "install"], capsys)

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    agents = os.path.abspath(home / ".agents" / "skills")
    assert code == cli.EXIT_OK
    assert stderr == ""
    assert result["paths"] == [agents]
    assert result["sync_pending"] is False
    assert result["last_synced_cli_version"] == result["current_cli_version"]
    assert saved["XAI_MODEL"] == "grok-test"
    assert saved["skills"]["schema_version"] == 1
    assert saved["skills"]["paths"] == [agents]
    assert (Path(agents) / "smart-search-cli" / "SKILL.md").is_file()


def test_skills_install_accepts_only_builtins_and_custom_containers(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    relative = Path("relative skills")
    absolute = tmp_path / "custom skills"
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(tmp_path)

    code, result, _ = _run(
        ["skills", "install", "agents", "claude", "hermes", str(relative), str(absolute)],
        capsys,
    )

    expected = [
        os.path.abspath(home / ".agents" / "skills"),
        os.path.abspath(home / ".claude" / "skills"),
        os.path.abspath(home / ".hermes" / "skills"),
        os.path.abspath(relative),
        os.path.abspath(absolute),
    ]
    assert code == cli.EXIT_OK
    assert result["paths"] == expected
    for container in expected:
        assert (Path(container) / "smart-search-cli" / "SKILL.md").is_file()


def test_skills_install_normalizes_deduplicates_and_preserves_symlink_entry(tmp_path, monkeypatch, capsys):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.chdir(tmp_path)

    code, result, _ = _run(
        ["skills", "install", "./linked", "linked/.", "./nested/../linked"],
        capsys,
    )

    assert code == cli.EXIT_OK
    assert result["paths"] == [os.path.abspath(link)]
    assert result["paths"][0] != os.path.realpath(link)
    assert (link / "smart-search-cli" / "SKILL.md").is_file()


def test_skills_install_expands_home_and_allows_explicit_reserved_relative_path(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(tmp_path)

    code, result, _ = _run(["skills", "install", "~/custom skills", "./agents"], capsys)

    assert code == cli.EXIT_OK
    assert result["paths"] == [str(home / "custom skills"), str(tmp_path / "agents")]


@pytest.mark.parametrize("invalid", ["", os.path.abspath(os.sep)])
def test_skills_install_rejects_empty_and_filesystem_root_before_writing(invalid, tmp_path, capsys):
    code, result, _ = _run(["skills", "install", str(tmp_path / "valid"), invalid], capsys)

    assert code == cli.EXIT_PARAMETER_ERROR
    assert result["error_type"] == "parameter_error"
    assert "skills install" in result["error"]
    assert not (tmp_path / "valid" / "smart-search-cli").exists()


def test_skills_install_rejects_existing_non_directory_before_writing(tmp_path, capsys):
    invalid = tmp_path / "file"
    invalid.write_text("not a directory", encoding="utf-8")

    code, result, _ = _run(["skills", "install", str(tmp_path / "valid"), str(invalid)], capsys)

    assert code == cli.EXIT_PARAMETER_ERROR
    assert result["error_type"] == "parameter_error"
    assert not (tmp_path / "valid" / "smart-search-cli").exists()


def test_skills_install_replaces_preference_without_deleting_removed_install(tmp_path, capsys):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _run(["skills", "install", str(first)], capsys)

    code, result, _ = _run(["skills", "install", str(second)], capsys)
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))

    assert code == cli.EXIT_OK
    assert result["paths"] == [str(second)]
    assert saved["skills"]["paths"] == [str(second)]
    assert (first / "smart-search-cli" / "SKILL.md").is_file()


def test_skills_install_partial_failure_saves_complete_intent(tmp_path, capsys):
    working = tmp_path / "working"
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "smart-search-cli").write_text("blocks the skill directory", encoding="utf-8")

    code, result, _ = _run(["skills", "install", str(working), str(blocked)], capsys)
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["skills"]

    assert code == cli.EXIT_RUNTIME_ERROR
    assert result["installed_count"] == 1
    assert result["failed_count"] == 1
    assert result["sync_pending"] is True
    assert saved["paths"] == [str(working), str(blocked)]
    assert saved["last_synced_cli_version"] == ""
    assert (working / "smart-search-cli" / "SKILL.md").is_file()


def test_skills_status_and_update_use_only_saved_paths_and_preserve_extras(tmp_path, capsys):
    container = tmp_path / "saved"
    _run(["skills", "install", str(container)], capsys)
    skill = container / "smart-search-cli"
    notes = skill / "MY-NOTES.md"
    notes.write_text("keep", encoding="utf-8")
    (skill / "SKILL.md").write_text("locally edited", encoding="utf-8")

    status_code, stale, _ = _run(["skills", "status"], capsys)
    update_code, updated, _ = _run(["skills", "update"], capsys)
    final_code, final, _ = _run(["skills", "status"], capsys)

    assert status_code == cli.EXIT_OK
    assert stale["installations"][0]["status"] == "stale"
    assert stale["installations"][0]["managed_hash_match"] is False
    assert update_code == cli.EXIT_OK
    assert updated["paths"] == [str(container)]
    assert updated["sync_pending"] is False
    assert notes.read_text(encoding="utf-8") == "keep"
    assert final_code == cli.EXIT_OK
    assert final["installations"][0]["status"] == "extra_files"
    assert final["installations"][0]["managed_hash_match"] is True
    assert final["installations"][0]["hash_match"] is False


def test_skills_clear_saves_valid_empty_preference_without_deleting_files(tmp_path, capsys):
    container = tmp_path / "saved"
    _run(["skills", "install", str(container)], capsys)

    clear_code, cleared, _ = _run(["skills", "clear"], capsys)
    status_code, status, _ = _run(["skills", "status"], capsys)
    update_code, update, _ = _run(["skills", "update"], capsys)

    assert clear_code == cli.EXIT_OK
    assert cleared["paths"] == []
    assert (container / "smart-search-cli" / "SKILL.md").is_file()
    assert status_code == cli.EXIT_OK
    assert status["paths"] == []
    assert status["installations"] == []
    assert status["sync_pending"] is False
    assert update_code == cli.EXIT_OK
    assert update["paths"] == []
    assert update["installed_count"] == 0


def test_non_interactive_provider_setup_leaves_skill_preference_unchanged(tmp_path, capsys):
    container = tmp_path / "saved"
    _run(["skills", "install", str(container)], capsys)
    before = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["skills"]

    code = cli.main(["setup", "--non-interactive", "--xai-model", "grok-test", "--format", "json"])
    capsys.readouterr()
    after = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))

    assert code == cli.EXIT_OK
    assert after["skills"] == before
    assert after["XAI_MODEL"] == "grok-test"


def test_skills_status_rejects_missing_or_malformed_saved_preference(tmp_path, capsys):
    code, missing, _ = _run(["skills", "status"], capsys)
    assert code == cli.EXIT_CONFIG_ERROR
    assert "skills install" in missing["error"]

    (tmp_path / "config.json").write_text(
        json.dumps({"skills": {"schema_version": 999, "paths": []}}), encoding="utf-8"
    )
    code, malformed, _ = _run(["skills", "status"], capsys)
    assert code == cli.EXIT_CONFIG_ERROR
    assert "Unsupported skills schema" in malformed["error"]

    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "skills": {
                    "schema_version": 1,
                    "paths": [os.path.abspath(os.sep)],
                    "last_synced_cli_version": "",
                }
            }
        ),
        encoding="utf-8",
    )
    code, invalid_path, _ = _run(["skills", "status"], capsys)
    assert code == cli.EXIT_CONFIG_ERROR
    assert "Invalid saved Skill Installation Preference" in invalid_path["error"]


@pytest.mark.parametrize(
    "removed",
    ["all", "codex", "cursor", "claude-code", "hermes-agent", "github-copilot"],
)
def test_skills_install_rejects_removed_target_vocabulary(removed, capsys):
    code, result, _ = _run(["skills", "install", removed], capsys)

    assert code == cli.EXIT_PARAMETER_ERROR
    assert "Built-ins are agents, claude, and hermes" in result["error"]
    assert "custom Skill Container" in result["error"]


@pytest.mark.parametrize(
    "argv",
    [
        ["skills", "status", "--targets", "agents"],
        ["skills", "update", "--all"],
        ["skills", "status", "--skills-root", "/tmp"],
        ["setup", "--non-interactive", "--install-skills", "agents"],
        ["setup", "--non-interactive", "--skills-root", "/tmp"],
    ],
)
def test_removed_selection_flags_fail_at_argparse_with_new_workflow_visible(argv, capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(argv)

    captured = capsys.readouterr()
    assert error.value.code == 2
    assert "removed" in captured.err
    assert "smart-search skills install [TARGET_OR_PATH ...]" in captured.err
