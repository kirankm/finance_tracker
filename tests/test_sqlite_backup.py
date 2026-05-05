import sqlite3
from pathlib import Path

import pytest

from app.sqlite_backup import backup_database, restore_database


def test_backup_database_copies_sqlite_contents(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    backup_path = tmp_path / "backups" / "source.backup.db"

    with sqlite3.connect(source_path) as connection:
        connection.execute("CREATE TABLE expenses (id INTEGER PRIMARY KEY, amount INTEGER)")
        connection.execute("INSERT INTO expenses (amount) VALUES (480)")

    backup_database(source_path, backup_path)

    with sqlite3.connect(backup_path) as connection:
        rows = connection.execute("SELECT amount FROM expenses").fetchall()

    assert rows == [(480,)]


def test_restore_database_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    backup_path = tmp_path / "backup.db"
    target_path = tmp_path / "target.db"

    with sqlite3.connect(backup_path) as connection:
        connection.execute("CREATE TABLE restored (id INTEGER PRIMARY KEY)")
    target_path.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        restore_database(backup_path, target_path, force=False)


def test_restore_database_replaces_target_when_forced(tmp_path: Path) -> None:
    backup_path = tmp_path / "backup.db"
    target_path = tmp_path / "target.db"

    with sqlite3.connect(backup_path) as connection:
        connection.execute("CREATE TABLE restored (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO restored (id) VALUES (1)")
    target_path.write_text("existing", encoding="utf-8")

    restore_database(backup_path, target_path, force=True)

    with sqlite3.connect(target_path) as connection:
        rows = connection.execute("SELECT id FROM restored").fetchall()

    assert rows == [(1,)]
