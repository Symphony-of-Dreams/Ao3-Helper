
import sqlite3

import pytest


@pytest.fixture
def db_connection(monkeypatch):
    """
    Crea un database in memoria pulito per ogni test, applica lo schema
    completo e garantisce che tutte le funzioni del database lo utilizzino.
    """
    conn = sqlite3.connect(":memory:")

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fics (
            url TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT, fandoms TEXT,
            tags TEXT, rating TEXT, word_count INTEGER, summary TEXT, status TEXT NOT NULL,
            date_added TEXT, user_notes TEXT, user_rating INTEGER, category TEXT,
            relationships TEXT, characters TEXT, is_complete INTEGER NOT NULL DEFAULT 0,
            status_verified INTEGER NOT NULL DEFAULT 0
        )"""
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, timestamp TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0, related_url TEXT
        )"""
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS achievements (
            id TEXT PRIMARY KEY,
            unlocked_date TEXT NOT NULL
        )"""
    )

    cursor.execute(
        """
        CREATE TABLE user_tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE fic_tags (
            fic_url TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (fic_url, tag_id),
            FOREIGN KEY (fic_url) REFERENCES fics (url) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES user_tags (tag_id) ON DELETE CASCADE
        )
    """
    )

    columns_to_add = {
        "series_name": "TEXT",
        "series_url": "TEXT",
        "series_part": "INTEGER",
        "chapters": "TEXT",
        "date_published": "TEXT",
        "date_updated": "TEXT",
        "source": "TEXT DEFAULT 'manual'",
        "last_read_date": "TEXT",
        "visit_count": "INTEGER",
        "language": "TEXT",
        "hits": "INTEGER",
        "kudos": "INTEGER",
        "bookmarks": "INTEGER",
        "comments": "INTEGER",
    }
    for col_name, col_type in columns_to_add.items():
        cursor.execute(f"ALTER TABLE fics ADD COLUMN {col_name} {col_type}")

    conn.commit()

    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: conn)

    yield conn

    conn.close()
