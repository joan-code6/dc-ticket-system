#!/usr/bin/env python3
"""One-time offline migration: plaintext SQLite -> SQLCipher-encrypted database.

Usage:
    DB_ENCRYPTION_KEY=your-key python scripts/migrate_encrypt.py [db path]

Defaults to bot/bot.db. The key is read from the DB_ENCRYPTION_KEY
environment variable (or from .env next to the repo root).

What it does:
  1. Refuses to run if the database is already encrypted.
  2. Copies every table and index into a new SQLCipher database using
     sqlcipher_export (original file is not modified yet).
  3. Verifies table row counts match between old and new database.
  4. Renames the original to <db>.plaintext-backup and moves the encrypted
     database into its place.

STOP THE BOT BEFORE RUNNING THIS. Keep the .plaintext-backup file somewhere
safe (or delete it securely) - it still contains all data unencrypted.
"""

import os
import shutil
import sys

from sqlcipher3 import dbapi2 as sqlcipher

PLAINTEXT_HEADER = b"SQLite format 3\x00"
DEFAULT_DB_PATH = os.path.join("bot", "bot.db")


def _load_dotenv_if_present(db_path: str):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    env_path = os.path.normpath(env_path)
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def is_plaintext_sqlite(db_path: str) -> bool:
    with open(db_path, "rb") as f:
        return f.read(len(PLAINTEXT_HEADER)) == PLAINTEXT_HEADER


def _table_counts(conn) -> dict:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {name: conn.execute(f"SELECT COUNT(*) FROM \"{name}\"").fetchone()[0] for (name,) in rows}


def migrate(db_path: str, key: str) -> str:
    """Encrypt db_path in place. Returns the backup path."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    if not is_plaintext_sqlite(db_path):
        raise RuntimeError(f"{db_path} is not a plaintext SQLite database - nothing to migrate.")

    tmp_path = db_path + ".encrypted"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    src = sqlcipher.connect(db_path)
    src.execute(f"ATTACH DATABASE {_quote(tmp_path)} AS encrypted KEY {_quote(key)}")
    src.execute("SELECT sqlcipher_export('encrypted')")
    src.execute("DETACH DATABASE encrypted")
    plain_counts = _table_counts(src)
    src.close()

    enc = sqlcipher.connect(tmp_path)
    enc.execute("PRAGMA key = " + _quote(key))
    encrypted_counts = _table_counts(enc)
    enc.close()

    if plain_counts != encrypted_counts:
        os.remove(tmp_path)
        raise RuntimeError(
            f"Verification failed, row counts differ: {plain_counts} vs {encrypted_counts}. "
            "Original database was left untouched."
        )

    backup_path = db_path + ".plaintext-backup"
    if os.path.exists(backup_path):
        raise RuntimeError(f"{backup_path} already exists - remove it first.")
    shutil.move(db_path, backup_path)
    shutil.move(tmp_path, db_path)
    return backup_path


def main():
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
    _load_dotenv_if_present(db_path)
    key = os.getenv("DB_ENCRYPTION_KEY")
    if not key:
        sys.exit("DB_ENCRYPTION_KEY is not set. Add it to .env or export it first.")
    backup_path = migrate(db_path, key)
    print(f"Encrypted {db_path}")
    print(f"Plaintext backup kept at {backup_path} - delete it securely when you no longer need it.")


if __name__ == "__main__":
    main()
