import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from smart_search import cli


ROOT = Path(__file__).resolve().parent.parent
PACKAGED_SKILL = ROOT / "src" / "smart_search" / "assets" / "skills" / "smart-search-cli"


def _run_json(argv, capsys):
    code = cli.main([*argv, "--format", "json"])
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def _current_cli_version(capsys):
    with pytest.raises(SystemExit) as stopped:
        cli.main(["--version"])
    assert stopped.value.code == cli.EXIT_OK
    version = capsys.readouterr().out.strip().rsplit(" ", 1)[-1]
    assert version
    return version


def test_first_ordinary_command_initializes_only_agents_and_syncs(tmp_path, monkeypatch, capsys):
    current_version = _current_cli_version(capsys)
    home = tmp_path / "home"
    legacy = home / ".claude" / "skills" / "smart-search-cli"
    legacy.mkdir(parents=True)
    (legacy / "legacy.txt").write_text("leave me", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: home)

    code, result, stderr = _run_json(["config", "path"], capsys)

    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    agents = os.path.abspath(home / ".agents" / "skills")
    assert code == cli.EXIT_OK
    assert result["ok"] is True
    assert stderr == ""
    assert saved["skills"]["paths"] == [agents]
    assert saved["skills"]["last_synced_cli_version"] == current_version
    assert (Path(agents) / "smart-search-cli" / "SKILL.md").is_file()
    assert (legacy / "legacy.txt").read_text(encoding="utf-8") == "leave me"


@pytest.mark.parametrize("previous", ["0.1.0", "99.0.0", "0.2.3-beta.1"])
def test_exact_version_mismatch_syncs_all_saved_containers(previous, tmp_path, capsys):
    current_version = _current_cli_version(capsys)
    container = tmp_path / "saved"
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "skills": {
                    "schema_version": 1,
                    "paths": [str(container)],
                    "last_synced_cli_version": previous,
                }
            }
        ),
        encoding="utf-8",
    )

    code, result, stderr = _run_json(["config", "list"], capsys)

    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert code == cli.EXIT_OK
    assert result["ok"] is True
    assert stderr == ""
    assert saved["skills"]["last_synced_cli_version"] == current_version
    assert (container / "smart-search-cli" / "SKILL.md").is_file()


def test_exact_version_match_is_noop(tmp_path, capsys):
    current_version = _current_cli_version(capsys)
    container = tmp_path / "saved"
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "XAI_MODEL": "unchanged",
                "skills": {
                    "schema_version": 1,
                    "paths": [str(container)],
                    "last_synced_cli_version": current_version,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    before = config_file.read_bytes()

    code, result, stderr = _run_json(["config", "list"], capsys)

    assert code == cli.EXIT_OK
    assert result["values"]["XAI_MODEL"] == "unchanged"
    assert stderr == ""
    assert config_file.read_bytes() == before
    assert not container.exists()


def test_empty_preference_disables_automatic_sync_after_version_change(tmp_path, capsys):
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "XAI_MODEL": "unchanged",
                "skills": {
                    "schema_version": 1,
                    "paths": [],
                    "last_synced_cli_version": "previous-version",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    before = config_file.read_bytes()

    code, result, stderr = _run_json(["config", "list"], capsys)

    assert code == cli.EXIT_OK
    assert result["values"]["XAI_MODEL"] == "unchanged"
    assert stderr == ""
    assert config_file.read_bytes() == before


def test_background_failure_warns_and_preserves_original_result(tmp_path, capsys):
    container = tmp_path / "blocked"
    container.mkdir()
    (container / "smart-search-cli").write_text("not a directory", encoding="utf-8")
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "XAI_MODEL": "grok-test",
                "skills": {
                    "schema_version": 1,
                    "paths": [str(container)],
                    "last_synced_cli_version": "older",
                },
            }
        ),
        encoding="utf-8",
    )

    code, result, stderr = _run_json(["config", "list"], capsys)

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert code == cli.EXIT_OK
    assert result["ok"] is True
    assert result["values"]["XAI_MODEL"] == "grok-test"
    assert "Automatic Skill Sync" in stderr
    assert "smart-search skills update" in stderr
    assert saved["skills"]["last_synced_cli_version"] == "older"


def test_malformed_config_warns_without_overwriting_original_command_result(tmp_path, capsys):
    config_file = tmp_path / "config.json"
    malformed = b'{"skills": '
    config_file.write_bytes(malformed)

    code, result, stderr = _run_json(["config", "path"], capsys)

    assert code == cli.EXIT_OK
    assert result["ok"] is True
    assert "Automatic Skill Sync" in stderr
    assert "smart-search skills update" in stderr
    assert config_file.read_bytes() == malformed


def test_partial_background_failure_retries_and_advances_only_after_full_success(tmp_path, capsys):
    working = tmp_path / "working"
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocker = blocked / "smart-search-cli"
    blocker.write_text("not a directory", encoding="utf-8")
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "skills": {
                    "schema_version": 1,
                    "paths": [str(working), str(blocked)],
                    "last_synced_cli_version": "old",
                }
            }
        ),
        encoding="utf-8",
    )

    first_code, first_result, first_stderr = _run_json(["config", "list"], capsys)
    pending = json.loads(config_file.read_text(encoding="utf-8"))["skills"]
    blocker.unlink()
    second_code, second_result, second_stderr = _run_json(["config", "list"], capsys)
    completed = json.loads(config_file.read_text(encoding="utf-8"))["skills"]

    assert first_code == second_code == cli.EXIT_OK
    assert first_result == second_result
    assert "smart-search skills update" in first_stderr
    assert pending["last_synced_cli_version"] == "old"
    assert second_stderr == ""
    assert completed["last_synced_cli_version"] != "old"
    for container in (working, blocked):
        assert (container / "smart-search-cli" / "SKILL.md").is_file()


@pytest.mark.parametrize("argv", [["--help"], ["--version"], ["skills", "--help"]])
def test_help_and_version_do_not_initialize_background_sync(argv, tmp_path, capsys):
    with pytest.raises(SystemExit) as stopped:
        cli.main(argv)
    capsys.readouterr()

    assert stopped.value.code == cli.EXIT_OK
    assert not (tmp_path / "config.json").exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["skills", "status"],
        ["skills", "update"],
        ["setup", "--non-interactive"],
        ["setup", "--non-interactive", "--skip-skills"],
    ],
)
def test_management_and_setup_commands_do_not_initialize_background_sync(argv, tmp_path, capsys):
    code = cli.main([*argv, "--format", "json"])
    capsys.readouterr()

    assert code in {cli.EXIT_OK, cli.EXIT_CONFIG_ERROR}
    if (tmp_path / "config.json").exists():
        saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert "skills" not in saved
    assert not (tmp_path / "home" / ".agents" / "skills" / "smart-search-cli").exists()


def test_interactive_setup_defaults_skill_preference_to_agents(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    answers = iter(["skip", "skip", "skip", "n", "n", "n", ""])
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    code, result, _ = _run_json(["setup", "--lang", "en"], capsys)

    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    agents = os.path.abspath(home / ".agents" / "skills")
    assert code == cli.EXIT_OK
    assert result["skills"]["paths"] == [agents]
    assert saved["skills"]["paths"] == [agents]
    assert (Path(agents) / "smart-search-cli" / "SKILL.md").is_file()


def test_interactive_setup_accepts_builtins_and_custom_skill_containers(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    custom = tmp_path / "custom skills"
    answers = iter(["skip", "skip", "skip", "n", "n", "n", f"claude,hermes,{custom}"])
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    code, result, _ = _run_json(["setup", "--lang", "en"], capsys)

    expected = [
        os.path.abspath(home / ".claude" / "skills"),
        os.path.abspath(home / ".hermes" / "skills"),
        str(custom),
    ]
    assert code == cli.EXIT_OK
    assert result["skills"]["paths"] == expected
    for container in expected:
        assert (Path(container) / "smart-search-cli" / "SKILL.md").is_file()


def test_interactive_setup_skip_preserves_existing_skill_preference(tmp_path, monkeypatch, capsys):
    container = tmp_path / "existing"
    _run_json(["skills", "install", str(container)], capsys)
    before = (tmp_path / "config.json").read_bytes()
    answers = iter(["skip", "skip", "skip", "n", "n", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    code, _, _ = _run_json(["setup", "--skip-skills", "--lang", "en"], capsys)

    assert code == cli.EXIT_OK
    assert (tmp_path / "config.json").read_bytes() == before


def test_concurrent_first_use_keeps_config_and_managed_files_complete(tmp_path):
    config_dir = tmp_path / "active config"
    container = tmp_path / "shared container"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "SMART_SEARCH_MINIMUM_PROFILE": "off",
                "skills": {
                    "schema_version": 1,
                    "paths": [str(container)],
                    "last_synced_cli_version": "previous-channel",
                },
            }
        ),
        encoding="utf-8",
    )
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "SMART_SEARCH_CONFIG_DIR": str(config_dir),
            "SMART_SEARCH_MINIMUM_PROFILE": "off",
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(ROOT / "src"), env.get("PYTHONPATH", "")])
            ),
        }
    )
    command = [sys.executable, "-m", "smart_search.cli", "config", "list", "--format", "json"]

    processes = [
        subprocess.Popen(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(2)
    ]
    results = [process.communicate(timeout=10) for process in processes]

    for process, (stdout, stderr) in zip(processes, results):
        assert process.returncode == cli.EXIT_OK
        assert json.loads(stdout)["ok"] is True
        assert stderr == ""
    saved = json.loads((config_dir / "config.json").read_text(encoding="utf-8"))
    assert saved["skills"]["paths"] == [str(container)]
    assert saved["skills"]["last_synced_cli_version"] != "previous-channel"
    installed = container / "smart-search-cli"
    for source in PACKAGED_SKILL.rglob("*"):
        if source.is_file():
            relative = source.relative_to(PACKAGED_SKILL)
            assert (installed / relative).read_bytes() == source.read_bytes()


def test_background_lock_timeout_warns_and_does_not_block_original_command(tmp_path):
    config_dir = tmp_path / "active"
    home = tmp_path / "home"
    config_dir.mkdir()
    home.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "SMART_SEARCH_CONFIG_DIR": str(config_dir),
            "SMART_SEARCH_MINIMUM_PROFILE": "off",
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(ROOT / "src"), env.get("PYTHONPATH", "")])
            ),
        }
    )
    containers = [tmp_path / "many" / str(index) for index in range(800)]
    install_command = [
        sys.executable,
        "-m",
        "smart_search.cli",
        "skills",
        "install",
        *(str(container) for container in containers),
        "--format",
        "json",
    ]
    installer = subprocess.Popen(
        install_command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 10
    first_managed_file = containers[0] / "smart-search-cli" / "SKILL.md"
    while not first_managed_file.exists() and installer.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert first_managed_file.is_file()

    started = time.monotonic()
    ordinary = subprocess.run(
        [sys.executable, "-m", "smart_search.cli", "config", "path", "--format", "json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )
    elapsed = time.monotonic() - started
    install_stdout, install_stderr = installer.communicate(timeout=30)

    assert ordinary.returncode == cli.EXIT_OK
    assert json.loads(ordinary.stdout)["ok"] is True
    assert "Automatic Skill Sync skipped" in ordinary.stderr
    assert elapsed < 3
    assert installer.returncode == cli.EXIT_OK
    assert json.loads(install_stdout)["ok"] is True
    assert install_stderr == ""
