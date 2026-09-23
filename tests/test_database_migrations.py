from pathlib import Path

import pytest
from builder_cup.database import DatabaseMigrationError, discover_migrations


def test_repository_migrations_are_ordered_unique_and_versioned():
    migrations = discover_migrations()
    assert [migration.version for migration in migrations] == ["001", "002", "003"]
    assert [migration.name for migration in migrations] == [
        "initial_records",
        "workflow_history",
        "workflow_scenario",
    ]
    assert all(len(migration.checksum) == 64 for migration in migrations)


@pytest.mark.parametrize("name", ["1_bad.sql", "004-bad.sql", "notes.sql"])
def test_invalid_migration_filename_is_rejected(tmp_path: Path, name: str):
    (tmp_path / name).write_text("SELECT 1;")
    with pytest.raises(DatabaseMigrationError, match="Invalid migration filename"):
        discover_migrations(tmp_path)


def test_duplicate_migration_version_is_rejected(tmp_path: Path):
    (tmp_path / "001_first.sql").write_text("SELECT 1;")
    (tmp_path / "001_second.sql").write_text("SELECT 2;")
    with pytest.raises(DatabaseMigrationError, match="unique"):
        discover_migrations(tmp_path)


def test_empty_migration_directory_is_rejected(tmp_path: Path):
    with pytest.raises(DatabaseMigrationError, match="present"):
        discover_migrations(tmp_path)
