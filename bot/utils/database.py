import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

DATABASE_PATH = "bot/bot.db"


class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database connection is not established. Call connect() first.")
        return self._connection

    async def connect(self):
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self):
        if self._connection:
            await self._connection.close()

    async def _create_tables(self):
        await self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL UNIQUE,
                creator_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                assigned_ids TEXT DEFAULT '[]',
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                close_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS transcript_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                attachments_json TEXT DEFAULT '[]',
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );
            CREATE TABLE IF NOT EXISTS ticket_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details_json TEXT DEFAULT '{}',
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );
        """)
        await self.conn.commit()

    async def create_ticket(self, guild_id: int, channel_id: int, creator_id: int, category: str) -> int:
        cursor = await self.conn.execute(
            "INSERT INTO tickets (guild_id, channel_id, creator_id, category) VALUES (?, ?, ?, ?)",
            (guild_id, channel_id, creator_id, category)
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def get_open_ticket_by_user(self, creator_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM tickets WHERE creator_id = ? AND guild_id = ? AND status = 'open'",
            (creator_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def get_ticket_by_id(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def update_ticket_assigned(self, ticket_id: int, assigned_ids: List[int]):
        await self.conn.execute(
            "UPDATE tickets SET assigned_ids = ? WHERE id = ?",
            (json.dumps(assigned_ids), ticket_id)
        )
        await self.conn.commit()

    async def close_ticket(self, ticket_id: int, reason: Optional[str] = None):
        await self.conn.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ?, close_reason = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), reason, ticket_id)
        )
        await self.conn.commit()

    async def rename_ticket_channel(self, ticket_id: int, new_name: str):
        pass

    async def add_transcript_message(self, ticket_id: int, message_id: int, author_id: int,
                                     author_name: str, content: str, timestamp: datetime,
                                     attachments: List[str]):
        await self.conn.execute(
            "INSERT INTO transcript_messages (ticket_id, message_id, author_id, author_name, content, timestamp, attachments_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, message_id, author_id, author_name, content, timestamp.isoformat(), json.dumps(attachments))
        )
        await self.conn.commit()

    async def update_transcript_attachment_urls(self, ticket_id: int, url_map: Dict[str, str]):
        async with self.conn.execute(
            "SELECT id, attachments_json FROM transcript_messages WHERE ticket_id = ?",
            (ticket_id,)
        ) as cursor:
            rows = await cursor.fetchall()

        for row in rows:
            attachments = json.loads(row["attachments_json"])
            updated = [url_map.get(url, url) for url in attachments]
            if updated != attachments:
                await self.conn.execute(
                    "UPDATE transcript_messages SET attachments_json = ? WHERE id = ?",
                    (json.dumps(updated), row["id"])
                )

        await self.conn.commit()

    async def get_transcript_messages(self, ticket_id: int) -> List[Dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM transcript_messages WHERE ticket_id = ? ORDER BY timestamp ASC",
            (ticket_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_ticket_log(self, ticket_id: int, action: str, user_id: int, details: Optional[Dict[str, Any]] = None):
        await self.conn.execute(
            "INSERT INTO ticket_logs (ticket_id, action, user_id, details_json) VALUES (?, ?, ?, ?)",
            (ticket_id, action, user_id, json.dumps(details or {}))
        )
        await self.conn.commit()

    async def get_ticket_logs(self, ticket_id: int) -> List[Dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM ticket_logs WHERE ticket_id = ? ORDER BY timestamp ASC",
            (ticket_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_open_tickets_count(self, guild_id: int) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) as count FROM tickets WHERE guild_id = ? AND status = 'open'",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0

    async def get_staff_loads(self, guild_id: int) -> Dict[int, int]:
        async with self.conn.execute(
            "SELECT assigned_ids FROM tickets WHERE guild_id = ? AND status = 'open'",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            loads = {}
            for row in rows:
                ids = json.loads(row["assigned_ids"])
                for uid in ids:
                    loads[uid] = loads.get(uid, 0) + 1
            return loads

    async def search_tickets(self, guild_id: int, **filters) -> List[Dict[str, Any]]:
        query = "SELECT * FROM tickets WHERE guild_id = ? AND status = 'closed'"
        params = [guild_id]

        if "creator_id" in filters:
            query += " AND creator_id = ?"
            params.append(filters["creator_id"])
        if "category" in filters:
            query += " AND category = ?"
            params.append(filters["category"])
        if "after" in filters:
            query += " AND created_at >= ?"
            params.append(filters["after"])
        if "before" in filters:
            query += " AND created_at <= ?"
            params.append(filters["before"])

        query += " ORDER BY closed_at DESC"

        async with self.conn.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_interaction_leaderboard(self, guild_id: int, since: str = None) -> Dict[int, int]:
        """Count distinct tickets each staff member interacted with since a given timestamp."""
        if since:
            query = """
                SELECT tl.user_id, COUNT(DISTINCT tl.ticket_id) AS count
                FROM ticket_logs tl
                JOIN tickets t ON tl.ticket_id = t.id
                WHERE t.guild_id = ? AND tl.timestamp >= ?
                GROUP BY tl.user_id
                ORDER BY count DESC
            """
            params = (guild_id, since)
        else:
            query = """
                SELECT tl.user_id, COUNT(DISTINCT tl.ticket_id) AS count
                FROM ticket_logs tl
                JOIN tickets t ON tl.ticket_id = t.id
                WHERE t.guild_id = ?
                GROUP BY tl.user_id
                ORDER BY count DESC
            """
            params = (guild_id,)
        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return {row["user_id"]: row["count"] for row in rows}
