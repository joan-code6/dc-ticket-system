"""Offline tests for SQLCipher encryption at rest, key handling, and the
plaintext -> encrypted migration. No Discord connection required."""

import asyncio
import importlib.util
import os
import sqlite3
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from bot.utils.database import Database  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "migrate_encrypt", os.path.join(REPO_ROOT, "scripts", "migrate_encrypt.py")
)
migrate_encrypt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate_encrypt)

TEST_KEY = "test-encryption-key-0123456789abcdef"
PLAINTEXT_HEADER = b"SQLite format 3\x00"


def _header(path):
    with open(path, "rb") as f:
        return f.read(len(PLAINTEXT_HEADER))


def _create_db(db_path, key):
    db = Database(db_path=str(db_path))
    asyncio.run(db.connect())
    asyncio.run(db.close())


def test_encrypted_db_is_not_plain_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_ENCRYPTION_KEY", TEST_KEY)
    db_path = tmp_path / "bot.db"
    _create_db(db_path, TEST_KEY)

    assert _header(db_path) != PLAINTEXT_HEADER

    with pytest.raises(sqlite3.DatabaseError):
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()


def test_encrypted_db_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_ENCRYPTION_KEY", TEST_KEY)
    db_path = str(tmp_path / "bot.db")

    async def run():
        db = Database(db_path=db_path)
        await db.connect()
        ticket_id = await db.create_ticket(1, 100, 200, "support")
        await db.add_transcript_message(
            ticket_id, 1000, 200, "someuser", "hello world",
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            ["https://cdn.example/file.png"],
        )
        await db.close()

        db2 = Database(db_path=db_path)
        await db2.connect()
        ticket = await db2.get_ticket_by_channel(100)
        messages = await db2.get_transcript_messages(ticket_id)
        await db2.close()
        return ticket, messages

    ticket, messages = asyncio.run(run())
    assert ticket["creator_id"] == 200
    assert len(messages) == 1
    assert messages[0]["content"] == "hello world"
    assert messages[0]["author_name"] == "someuser"


def test_missing_key_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("DB_ENCRYPTION_KEY", raising=False)
    db = Database(db_path=str(tmp_path / "bot.db"))
    with pytest.raises(RuntimeError, match="DB_ENCRYPTION_KEY"):
        asyncio.run(db.connect())


def test_wrong_key_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_ENCRYPTION_KEY", TEST_KEY)
    db_path = tmp_path / "bot.db"
    _create_db(db_path, TEST_KEY)

    monkeypatch.setenv("DB_ENCRYPTION_KEY", "completely-different-key")
    db = Database(db_path=str(db_path))
    with pytest.raises(RuntimeError, match="decrypted"):
        asyncio.run(db.connect())


def test_plaintext_db_rejected(tmp_path, monkeypatch):
    db_path = tmp_path / "bot.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE tickets (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    monkeypatch.setenv("DB_ENCRYPTION_KEY", TEST_KEY)
    db = Database(db_path=str(db_path))
    with pytest.raises(RuntimeError, match="migrate_encrypt"):
        asyncio.run(db.connect())


def test_migration_encrypts_in_place(tmp_path):
    db_path = str(tmp_path / "bot.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE transcript_messages (id INTEGER PRIMARY KEY, content TEXT)"
    )
    conn.execute(
        "INSERT INTO transcript_messages (content) VALUES (?)", ("secret message",)
    )
    conn.execute("CREATE TABLE tickets (id INTEGER PRIMARY KEY, category TEXT)")
    conn.execute("INSERT INTO tickets (category) VALUES ('billing')")
    conn.commit()
    conn.close()

    backup_path = migrate_encrypt.migrate(db_path, TEST_KEY)

    assert os.path.exists(backup_path)
    assert _header(backup_path) == PLAINTEXT_HEADER
    assert _header(db_path) != PLAINTEXT_HEADER

    # Old plaintext tooling can no longer read it.
    with pytest.raises(sqlite3.DatabaseError):
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()

    # Data survived the migration and is readable with the key.
    from sqlcipher3 import dbapi2 as sqlcipher

    enc = sqlcipher.connect(db_path)
    enc.execute("PRAGMA key = " + migrate_encrypt._quote(TEST_KEY))
    assert enc.execute("SELECT content FROM transcript_messages").fetchone()[0] == "secret message"
    assert enc.execute("SELECT category FROM tickets").fetchone()[0] == "billing"
    enc.close()

    # Running the migration again on the encrypted file refuses.
    with pytest.raises(RuntimeError, match="not a plaintext"):
        migrate_encrypt.migrate(db_path, TEST_KEY)
