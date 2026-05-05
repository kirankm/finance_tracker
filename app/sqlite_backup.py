from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def backup_database(source_path: Path, backup_path: Path) -> None:
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    backup_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(source_path) as source:
        with sqlite3.connect(backup_path) as backup:
            source.backup(backup)


def restore_database(backup_path: Path, target_path: Path, *, force: bool) -> None:
    if not backup_path.exists():
        raise FileNotFoundError(backup_path)
    if target_path.exists() and not force:
        raise FileExistsError(
            f"{target_path} already exists; rerun with --force to replace it"
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()

    with sqlite3.connect(backup_path) as backup:
        with sqlite3.connect(target_path) as target:
            backup.backup(target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backup or restore a SQLite database.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    backup_parser = subcommands.add_parser("backup")
    backup_parser.add_argument("source", type=Path)
    backup_parser.add_argument("destination", type=Path)

    restore_parser = subcommands.add_parser("restore")
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("target", type=Path)
    restore_parser.add_argument("--force", action="store_true")

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "backup":
        backup_database(args.source, args.destination)
        return

    restore_database(args.backup, args.target, force=args.force)


if __name__ == "__main__":
    main()
