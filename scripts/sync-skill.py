#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path


SKILL_NAME = "smart-search-cli"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_SKILL = PROJECT_ROOT / "skills" / SKILL_NAME
PACKAGED_SKILL = (
    PROJECT_ROOT
    / "src"
    / "smart_search"
    / "assets"
    / "skills"
    / SKILL_NAME
)
REQUIRED_FRONTMATTER_FIELDS = ("name", "description")
INLINE_CONTEXT_POINTER = re.compile(
    r"`(references/[A-Za-z0-9._/-]+\.md)(?:#[^`]*)?`"
)
MARKDOWN_CONTEXT_POINTER = re.compile(
    r"\]\((references/[A-Za-z0-9._/-]+\.md)(?:#[^)]*)?\)"
)


def skill_file_map(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def validate_public_skill() -> None:
    main_document = PUBLIC_SKILL / "SKILL.md"
    if not main_document.is_file():
        raise ValueError("required file is missing: SKILL.md")

    text = main_document.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md must begin and end with YAML frontmatter")
    try:
        closing_delimiter = lines.index("---", 1)
    except ValueError as error:
        raise ValueError(
            "SKILL.md must begin and end with YAML frontmatter"
        ) from error

    frontmatter: dict[str, str] = {}
    for line in lines[1:closing_delimiter]:
        key, separator, value = line.partition(":")
        if separator:
            frontmatter[key.strip()] = value.strip().strip("'\"")
    for field in REQUIRED_FRONTMATTER_FIELDS:
        if not frontmatter.get(field):
            raise ValueError(f"frontmatter field is required: {field}")

    pointers = set(INLINE_CONTEXT_POINTER.findall(text))
    pointers.update(MARKDOWN_CONTEXT_POINTER.findall(text))
    source_root = PUBLIC_SKILL.resolve()
    for pointer in sorted(pointers):
        target = (PUBLIC_SKILL / pointer).resolve()
        if not target.is_relative_to(source_root) or not target.is_file():
            raise ValueError(f"context pointer target is missing: {pointer}")


def sync_skill() -> int:
    validate_public_skill()

    PACKAGED_SKILL.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{SKILL_NAME}-",
            dir=PACKAGED_SKILL.parent,
        )
    )
    try:
        files = skill_file_map(PUBLIC_SKILL)
        for relative_path, content in files.items():
            destination = staging / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)

        if PACKAGED_SKILL.exists():
            shutil.rmtree(PACKAGED_SKILL)
        staging.replace(PACKAGED_SKILL)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    print(f"Synchronized {len(files)} Skill files.")
    return 0


def check_skill() -> int:
    validate_public_skill()
    public_files = skill_file_map(PUBLIC_SKILL)
    packaged_files = skill_file_map(PACKAGED_SKILL)
    missing = sorted(public_files.keys() - packaged_files.keys())
    unexpected = sorted(packaged_files.keys() - public_files.keys())
    different = sorted(
        relative_path
        for relative_path in public_files.keys() & packaged_files.keys()
        if public_files[relative_path] != packaged_files[relative_path]
    )

    for relative_path in missing:
        print(f"missing from package: {relative_path}", file=sys.stderr)
    for relative_path in unexpected:
        print(f"unexpected in package: {relative_path}", file=sys.stderr)
    for relative_path in different:
        print(f"content differs: {relative_path}", file=sys.stderr)

    if missing or unexpected or different:
        return 1
    print(f"Skill mirror is up to date ({len(public_files)} files).")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize the public Smart Search Skill into package assets."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check the package mirror without changing files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return check_skill() if args.check else sync_skill()
    except (OSError, ValueError) as error:
        print(f"Skill synchronization failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
