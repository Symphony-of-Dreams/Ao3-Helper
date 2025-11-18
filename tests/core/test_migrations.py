import sqlite3

import pytest
from peewee import SqliteDatabase

from ao3_helper import constants as const
from ao3_helper.core.database import run_database_migrations
from ao3_helper.core.models import db


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "migration_test.db")


def create_v3_database(path):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE fics (
            url VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255),
            author VARCHAR(255),
            status VARCHAR(255),
            date_added DATETIME
        )
    """
    )
    c.execute(
        "INSERT INTO fics (url, title, author, status, date_added) VALUES (?, ?, ?, ?, ?)",
        ("http://example.com/fic1", "Old Fic", "Old Author", "Read", "2023-01-01"),
    )
    c.execute("PRAGMA user_version = 3")
    conn.commit()
    conn.close()


def test_migration_v3_to_current(db_path):

    create_v3_database(db_path)

    real_db = SqliteDatabase(db_path)
    db.initialize(real_db)

    run_database_migrations(db_path)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    version = c.execute("PRAGMA user_version").fetchone()[0]
    assert version == const.LATEST_DB_VERSION

    columns_info = c.execute("PRAGMA table_info(fics)").fetchall()
    column_names = [col[1] for col in columns_info]

    assert "is_in_library" in column_names
    assert "is_in_history" in column_names
    assert "is_in_reading_queue" in column_names
    assert "queue_order" in column_names

    fic = c.execute("SELECT title, author FROM fics WHERE url = ?", ("http://example.com/fic1",)).fetchone()
    assert fic[0] == "Old Fic"
    assert fic[1] == "Old Author"

    tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]
    assert "saved_filters" in table_names

    conn.close()

    if not real_db.is_closed():
        real_db.close()
