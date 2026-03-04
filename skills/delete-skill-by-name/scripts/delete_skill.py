#!/usr/bin/env python3
"""
delete_skill.py

按名字安全删除（实际为移动）本地 Codex skill 目录：
- 默认从 ~/.codex/skills/<skill-name> 查找 skill 目录；
- 将整个目录移动到 ~/.codex/trash/<skill-name>-YYYYMMDD-HHMMSS；
- 默认在命令行里要求用户再次输入 skill 名字确认，除非显式传入 -y。

注意：在 Codex 自动化场景中，推荐先在对话中向用户确认，再使用 -y 调用本脚本，
避免双重交互阻塞。
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely delete (move) a local Codex skill by name."
    )
    parser.add_argument(
        "skill_name",
        help="The skill folder name under the skills root (e.g. 'pdf', 'frontend-design').",
    )
    parser.add_argument(
        "--skills-root",
        default=os.environ.get("CODEX_SKILLS_ROOT")
        or str(Path.home() / ".codex" / "skills"),
        help="Root directory containing skills folders. "
        "Defaults to $CODEX_SKILLS_ROOT or ~/.codex/skills.",
    )
    parser.add_argument(
        "--trash-root",
        default=str(Path.home() / ".codex" / "trash"),
        help="Trash root directory to move deleted skills into. "
        "Defaults to '~/.codex/trash'.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt and proceed directly.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making any filesystem changes.",
    )
    return parser.parse_args()


def resolve_paths(
    skills_root_str: str, trash_root_str: str, skill_name: str
) -> tuple[Path, Path, Path]:
    skills_root = Path(skills_root_str).expanduser().resolve()
    trash_root = Path(trash_root_str).expanduser()
    if not trash_root.is_absolute():
        trash_root = Path.cwd() / trash_root

    skill_dir = skills_root / skill_name

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest_dir = trash_root / f"{skill_name}-{timestamp}"

    return skills_root, skill_dir, dest_dir


def main() -> int:
    args = parse_args()

    skills_root, skill_dir, dest_dir = resolve_paths(
        args.skills_root, args.trash_root, args.skill_name
    )

    # Basic sanity checks
    if not skills_root.exists():
        print(
            f"[delete-skill] Skills root does not exist: {skills_root}",
            file=sys.stderr,
        )
        return 1
    if not skills_root.is_dir():
        print(
            f"[delete-skill] Skills root is not a directory: {skills_root}",
            file=sys.stderr,
        )
        return 1
    if not skill_dir.exists():
        print(
            f"[delete-skill] Skill directory not found: {skill_dir}",
            file=sys.stderr,
        )
        return 1
    if not skill_dir.is_dir():
        print(
            f"[delete-skill] Skill path exists but is not a directory: {skill_dir}",
            file=sys.stderr,
        )
        return 1

    trash_root = dest_dir.parent

    print("[delete-skill] Planned operation:")
    print(f"  Skills root : {skills_root}")
    print(f"  Source      : {skill_dir}")
    print(f"  Trash root  : {trash_root}")
    print(f"  Destination : {dest_dir}")

    # Interactive confirmation (unless -y)
    if not args.yes:
        try:
            prompt = (
                f"Type the skill name '{args.skill_name}' again to confirm deletion,\n"
                "or anything else to cancel: "
            )
            entered = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[delete-skill] Confirmation cancelled.", file=sys.stderr)
            return 1

        if entered != args.skill_name:
            print("[delete-skill] Skill name mismatch; aborting.", file=sys.stderr)
            return 1

    if args.dry_run:
        print("[delete-skill] Dry-run mode; no filesystem changes made.")
        return 0

    # Ensure trash root exists
    try:
        trash_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            f"[delete-skill] Failed to create trash root {trash_root}: {exc}",
            file=sys.stderr,
        )
        return 1

    # Perform move
    try:
        shutil.move(str(skill_dir), str(dest_dir))
    except Exception as exc:  # noqa: BLE001
        print(
            f"[delete-skill] Failed to move {skill_dir} -> {dest_dir}: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"[delete-skill] Skill '{args.skill_name}' moved to: {dest_dir}")
    print(
        "[delete-skill] To restore, move it back under your skills root, e.g.\n"
        f"  mv '{dest_dir}' '{skills_root / args.skill_name}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
