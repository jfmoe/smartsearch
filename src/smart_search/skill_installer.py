from __future__ import annotations

import os
import tempfile
from hashlib import sha256
from importlib import resources
from pathlib import Path
from typing import Any


SKILL_NAME = "smart-search-cli"
PACKAGE_ROOT_ENV = "SMART_SEARCH_PACKAGE_ROOT"
BUILTIN_SKILL_CONTAINERS = {
    "agents": ".agents/skills",
    "claude": ".claude/skills",
    "hermes": ".hermes/skills",
}
REMOVED_TARGET_NAMES = {
    "all",
    "codex",
    "cursor",
    "opencode",
    "copilot",
    "gemini",
    "kiro",
    "qoder",
    "codebuddy",
    "droid",
    "pi",
    "kilo",
    "antigravity",
    "windsurf",
    "agentskills",
    "agent-skills",
    "claude-code",
    "github-copilot",
    "gh-copilot",
    "factory",
    "factory-droid",
    "pi-agent",
    "kilo-cli",
    "hermes-agent",
    "nous-hermes",
}


class SkillInstallError(ValueError):
    pass


def normalize_skill_containers(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise SkillInstallError(
                "Skill Container paths cannot be empty. Use `smart-search skills install [TARGET_OR_PATH ...]`."
            )
        if value.lower() in REMOVED_TARGET_NAMES:
            raise SkillInstallError(
                f"Removed Skill target name: {value!r}. Built-ins are agents, claude, and hermes; "
                "pass an explicit custom Skill Container path to `smart-search skills install`."
            )
        if value in BUILTIN_SKILL_CONTAINERS:
            raw_path = str(Path.home() / BUILTIN_SKILL_CONTAINERS[value])
        else:
            raw_path = value
        path = os.path.abspath(os.path.expanduser(raw_path))
        if os.path.dirname(path) == path:
            raise SkillInstallError(
                f"Filesystem roots are not valid Skill Containers: {value!r}. "
                "Use `smart-search skills install` with a container directory."
            )
        if os.path.lexists(path) and not os.path.isdir(path):
            raise SkillInstallError(f"Skill Container exists but is not a directory: {path}")
        dedupe_key = os.path.normcase(os.path.normpath(path))
        if dedupe_key not in seen:
            seen.add(dedupe_key)
            normalized.append(path)
    return normalized


def _resource_skill_root() -> Any:
    try:
        root = resources.files("smart_search").joinpath("assets", "skills", SKILL_NAME)
        if root.is_dir():
            return root
    except (FileNotFoundError, ModuleNotFoundError, AttributeError):
        pass
    return None


def _filesystem_skill_root() -> Path | None:
    candidates: list[Path] = []
    package_root = os.getenv(PACKAGE_ROOT_ENV, "").strip()
    if package_root:
        base = Path(package_root)
        candidates.extend(
            [
                base / "src" / "smart_search" / "assets" / "skills" / SKILL_NAME,
                base / "skills" / SKILL_NAME,
            ]
        )
    repo_root = Path(__file__).resolve().parents[2]
    candidates.extend(
        [
            repo_root / "src" / "smart_search" / "assets" / "skills" / SKILL_NAME,
            repo_root / "skills" / SKILL_NAME,
        ]
    )
    return next((candidate for candidate in candidates if candidate.is_dir()), None)


def _iter_resource_files(root: Any) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []

    def visit(node: Any, prefix: str = "") -> None:
        for child in node.iterdir():
            relative = f"{prefix}/{child.name}" if prefix else child.name
            if child.is_dir():
                visit(child, relative)
            elif child.is_file():
                files.append((relative, child.read_bytes()))

    visit(root)
    return files


def _iter_filesystem_files(root: Path) -> list[tuple[str, bytes]]:
    return [
        (str(path.relative_to(root)).replace("\\", "/"), path.read_bytes())
        for path in root.rglob("*")
        if path.is_file()
    ]


def _load_skill_files(source_root: str | Path | None = None) -> list[tuple[str, bytes]]:
    if source_root is not None:
        source = Path(source_root).expanduser()
        if not source.is_dir():
            raise SkillInstallError(f"Skill source directory not found: {source}")
        return _iter_filesystem_files(source)
    resource_root = _resource_skill_root()
    if resource_root is not None:
        files = _iter_resource_files(resource_root)
        if files:
            return files
    filesystem_root = _filesystem_skill_root()
    if filesystem_root is not None:
        files = _iter_filesystem_files(filesystem_root)
        if files:
            return files
    raise SkillInstallError("Bundled smart-search-cli skill files were not found.")


def _skill_digest(files: list[tuple[str, bytes]]) -> str:
    digest = sha256()
    for relative, content in sorted(files):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def status_skill_containers(
    containers: list[str], *, source_root: str | Path | None = None
) -> dict[str, Any]:
    files = _load_skill_files(source_root)
    source_by_path = dict(files)
    bundled_hash = _skill_digest(files)
    installations: list[dict[str, Any]] = []
    for container in containers:
        destination = Path(container) / SKILL_NAME
        item: dict[str, Any] = {
            "container": container,
            "path": str(destination),
            "status": "missing",
            "files": len(files),
            "installed_files": 0,
            "bundled_hash": bundled_hash,
            "installed_hash": "",
            "hash_match": False,
            "managed_hash_match": False,
            "extra_files": [],
            "missing_files": sorted(source_by_path),
            "stale_files": [],
        }
        try:
            if not destination.exists():
                installations.append(item)
                continue
            if not destination.is_dir():
                item.update(status="error", error="Installed skill path exists but is not a directory.")
                installations.append(item)
                continue
            installed_files = _iter_filesystem_files(destination)
            installed_by_path = dict(installed_files)
            extra_files = sorted(set(installed_by_path) - set(source_by_path))
            missing_files = sorted(set(source_by_path) - set(installed_by_path))
            stale_files = sorted(
                relative
                for relative, content in source_by_path.items()
                if relative in installed_by_path and installed_by_path[relative] != content
            )
            managed_match = not missing_files and not stale_files
            exact_match = managed_match and not extra_files
            item.update(
                installed_files=len(installed_files),
                installed_hash=_skill_digest(installed_files) if installed_files else "",
                hash_match=exact_match,
                managed_hash_match=managed_match,
                extra_files=extra_files,
                missing_files=missing_files,
                stale_files=stale_files,
                status=("stale" if missing_files or stale_files else "extra_files" if extra_files else "up_to_date"),
            )
        except OSError as error:
            item.update(status="error", error=str(error))
        installations.append(item)
    status_counts: dict[str, int] = {}
    for item in installations:
        status = str(item["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "ok": not any(item["status"] == "error" for item in installations),
        "paths": list(containers),
        "skill": SKILL_NAME,
        "bundled_files": len(files),
        "bundled_hash": bundled_hash,
        "installations": installations,
        "status_counts": status_counts,
    }


def install_skill_containers(
    containers: list[str], *, source_root: str | Path | None = None
) -> dict[str, Any]:
    files = _load_skill_files(source_root)
    installed: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for container in containers:
        destination = Path(container) / SKILL_NAME
        try:
            for relative, content in files:
                file_path = destination / relative
                file_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=file_path.parent,
                        prefix=f".{file_path.name}.",
                        delete=False,
                    ) as temporary:
                        temporary_path = Path(temporary.name)
                        temporary.write(content)
                        temporary.flush()
                        os.fsync(temporary.fileno())
                    os.replace(temporary_path, file_path)
                except OSError:
                    if temporary_path is not None:
                        try:
                            temporary_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                    raise
            installed.append({"container": container, "path": str(destination), "files": len(files)})
        except OSError as error:
            failed.append({"container": container, "path": str(destination), "error": str(error)})
    return {
        "ok": not failed,
        "paths": list(containers),
        "installed": installed,
        "failed": failed,
        "installed_count": len(installed),
        "failed_count": len(failed),
    }
