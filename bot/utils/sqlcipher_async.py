"""Minimal async wrapper around sqlcipher3 (SQLCipher) connections.

The bot previously used aiosqlite. aiosqlite is built on the standard
sqlite3 module, which has no encryption codec, so it cannot open
SQLCipher databases. This module implements only the small subset of the
aiosqlite API that bot/utils/database.py uses:

- awaitable execute() / executescript() / commit() / close()
- row_factory (set to Row for dict-like rows)
- cursors usable with "async with", fetchone()/fetchall(), lastrowid

All calls are serialized onto a single background thread because sqlite
connections are not thread-safe by default.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from sqlcipher3 import dbapi2 as sqlcipher

Row = sqlcipher.Row
DatabaseError = sqlcipher.DatabaseError


def quote_key(key: str) -> str:
    """Quote a passphrase for use in PRAGMA key (parameter binding is not
    supported for PRAGMA statements, so the key must be inlined safely)."""
    return "'" + key.replace("'", "''") + "'"


class Cursor:
    def __init__(self, connection: "Connection", raw):
        self._connection = connection
        self._raw = raw

    @property
    def lastrowid(self):
        return self._raw.lastrowid

    async def fetchone(self):
        return await self._connection._run(self._raw.fetchone)

    async def fetchall(self):
        return await self._connection._run(self._raw.fetchall)

    async def close(self):
        await self._connection._run(self._raw.close)


class _Execute:
    """Awaitable returned by Connection.execute(); also an async context
    manager, matching the aiosqlite usage in database.py."""

    def __init__(self, connection: "Connection", sql: str, parameters):
        self._connection = connection
        self._sql = sql
        self._parameters = parameters
        self._cursor = None

    async def _run_cursor(self) -> Cursor:
        if self._cursor is None:
            raw = await self._connection._run(
                self._connection._conn.execute, self._sql, self._parameters
            )
            self._cursor = Cursor(self._connection, raw)
        return self._cursor

    def __await__(self):
        return self._run_cursor().__await__()

    async def __aenter__(self) -> Cursor:
        return await self._run_cursor()

    async def __aexit__(self, *exc):
        if self._cursor is not None:
            await self._cursor.close()
        return False


class Connection:
    def __init__(self):
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="sqlcipher"
        )
        self._conn = None
        self.row_factory = None

    async def _run(self, fn, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn, *args)

    def execute(self, sql: str, parameters=()) -> _Execute:
        return _Execute(self, sql, parameters)

    async def executescript(self, script: str):
        await self._run(self._conn.executescript, script)

    async def commit(self):
        await self._run(self._conn.commit)

    async def close(self):
        if self._conn is not None:
            await self._run(self._conn.close)
            self._conn = None
        self._executor.shutdown(wait=True)


async def connect(db_path: str, key: str) -> Connection:
    """Open (or create) a SQLCipher-encrypted database.

    Raises sqlcipher.DatabaseError if the file exists but cannot be
    decrypted with the given key (e.g. wrong key).
    """
    wrapper = Connection()

    def _open():
        conn = sqlcipher.connect(db_path)
        conn.execute("PRAGMA key = " + quote_key(key))
        # Force the first page read so a wrong key fails here, not later.
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return conn

    wrapper._conn = await wrapper._run(_open)
    wrapper.row_factory = Row
    wrapper._conn.row_factory = Row
    return wrapper
