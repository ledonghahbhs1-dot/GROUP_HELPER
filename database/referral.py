"""Referral links + manual group events storage (task 102).

Uses the same SQLite file as `database.db.db`. Everything is plain SQL on epoch-second timestamps so it is easy to test
with a temporary database. Nothing here ever grants a reward: it only counts, and records which milestones were announced.
"""
import time
from typing import Any, Dict, List, Optional

import aiosqlite

from database.db import db as main_db

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS referral_links (
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        invite_link TEXT NOT NULL,
        name TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        PRIMARY KEY (chat_id, user_id)
    )""",
    # one row per (chat, invited member): a member can only ever be credited once per chat
    """CREATE TABLE IF NOT EXISTS referral_joins (
        chat_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        referrer_id INTEGER NOT NULL,
        joined_at INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',   -- pending | confirmed | revoked
        resolved_at INTEGER,
        PRIMARY KEY (chat_id, member_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_referral_joins_pending ON referral_joins(status, joined_at)",
    """CREATE TABLE IF NOT EXISTS referral_counts (
        chat_id INTEGER NOT NULL,
        referrer_id INTEGER NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL,
        PRIMARY KEY (chat_id, referrer_id)
    )""",
    # the "already announced" memory: a milestone is announced at most once per (chat, referrer, milestone)
    """CREATE TABLE IF NOT EXISTS referral_milestones_notified (
        chat_id INTEGER NOT NULL,
        referrer_id INTEGER NOT NULL,
        milestone INTEGER NOT NULL,
        notified_at INTEGER NOT NULL,
        PRIMARY KEY (chat_id, referrer_id, milestone)
    )""",
    """CREATE TABLE IF NOT EXISTS group_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        message_id INTEGER,
        pinned INTEGER NOT NULL DEFAULT 0,
        created_by INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        ends_at INTEGER,
        status TEXT NOT NULL DEFAULT 'active'     -- active | ended | cancelled
    )""",
    "CREATE INDEX IF NOT EXISTS idx_group_events_active ON group_events(status, chat_id)",
)


class ReferralStore:
    def __init__(self, database=main_db, clock=time.time):
        self._database = database
        self._clock = clock

    @property
    def path(self) -> str:
        return self._database.db_path

    def now(self) -> int:
        return int(self._clock())

    async def ensure_schema(self) -> None:
        async with aiosqlite.connect(self.path) as conn:
            for statement in _SCHEMA:
                await conn.execute(statement)
            await conn.commit()

    # ------------------------------------------------------------------ links
    async def get_link(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM referral_links WHERE chat_id=? AND user_id=?", (chat_id, user_id))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def save_link(self, chat_id: int, user_id: int, invite_link: str, name: str) -> None:
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT INTO referral_links (chat_id, user_id, invite_link, name, created_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET invite_link=excluded.invite_link, name=excluded.name",
                (chat_id, user_id, invite_link, name, self.now()))
            await conn.commit()

    # ------------------------------------------------------------------ joins
    async def record_join(self, chat_id: int, member_id: int, referrer_id: int) -> bool:
        """Registers a pending referral. False when this member was already recorded in this chat (no double credit)
        or invited themself."""
        if member_id == referrer_id:
            return False
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute(
                "INSERT OR IGNORE INTO referral_joins (chat_id, member_id, referrer_id, joined_at, status) VALUES (?,?,?,?, 'pending')",
                (chat_id, member_id, referrer_id, self.now()))
            await conn.commit()
            return cur.rowcount == 1

    async def get_join(self, chat_id: int, member_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM referral_joins WHERE chat_id=? AND member_id=?", (chat_id, member_id))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def due_pending(self, older_than_sec: int, limit: int = 100) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM referral_joins WHERE status='pending' AND joined_at <= ? ORDER BY joined_at LIMIT ?",
                (self.now() - older_than_sec, limit))
            return [dict(r) for r in await cur.fetchall()]

    async def confirm_join(self, chat_id: int, member_id: int) -> Optional[int]:
        """pending -> confirmed and +1 for the referrer, atomically. Returns the referrer's new count, or None if the row
        was not pending (so a repeated call can never double count)."""
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            cur = await conn.execute(
                "UPDATE referral_joins SET status='confirmed', resolved_at=? WHERE chat_id=? AND member_id=? AND status='pending'",
                (self.now(), chat_id, member_id))
            if cur.rowcount != 1:
                await conn.rollback()
                return None
            cur = await conn.execute("SELECT referrer_id FROM referral_joins WHERE chat_id=? AND member_id=?", (chat_id, member_id))
            referrer_id = (await cur.fetchone())[0]
            await conn.execute(
                "INSERT INTO referral_counts (chat_id, referrer_id, count, updated_at) VALUES (?,?,1,?) "
                "ON CONFLICT(chat_id, referrer_id) DO UPDATE SET count = count + 1, updated_at = excluded.updated_at",
                (chat_id, referrer_id, self.now()))
            cur = await conn.execute("SELECT count FROM referral_counts WHERE chat_id=? AND referrer_id=?", (chat_id, referrer_id))
            count = (await cur.fetchone())[0]
            await conn.commit()
            return count

    async def revoke_join(self, chat_id: int, member_id: int) -> bool:
        """pending -> revoked (left/kicked/banned before the confirm window). A confirmed join that is revoked later also
        takes the point back (never below 0)."""
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            cur = await conn.execute("SELECT referrer_id, status FROM referral_joins WHERE chat_id=? AND member_id=?", (chat_id, member_id))
            row = await cur.fetchone()
            if not row or row[1] == "revoked":
                await conn.rollback()
                return False
            referrer_id, status = row
            await conn.execute("UPDATE referral_joins SET status='revoked', resolved_at=? WHERE chat_id=? AND member_id=?",
                               (self.now(), chat_id, member_id))
            if status == "confirmed":
                await conn.execute(
                    "UPDATE referral_counts SET count = MAX(count - 1, 0), updated_at=? WHERE chat_id=? AND referrer_id=?",
                    (self.now(), chat_id, referrer_id))
            await conn.commit()
            return True

    # ----------------------------------------------------------------- counts
    async def get_counts(self, chat_id: int, referrer_id: int) -> Dict[str, int]:
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute("SELECT count FROM referral_counts WHERE chat_id=? AND referrer_id=?", (chat_id, referrer_id))
            row = await cur.fetchone()
            cur = await conn.execute(
                "SELECT COUNT(*) FROM referral_joins WHERE chat_id=? AND referrer_id=? AND status='pending'", (chat_id, referrer_id))
            pending = (await cur.fetchone())[0]
            return {"confirmed": row[0] if row else 0, "pending": pending}

    async def claim_milestone(self, chat_id: int, referrer_id: int, milestone: int) -> bool:
        """True exactly once per (chat, referrer, milestone): the caller that gets True announces it."""
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute(
                "INSERT OR IGNORE INTO referral_milestones_notified (chat_id, referrer_id, milestone, notified_at) VALUES (?,?,?,?)",
                (chat_id, referrer_id, milestone, self.now()))
            await conn.commit()
            return cur.rowcount == 1

    # ----------------------------------------------------------------- events
    async def add_event(self, chat_id: int, text: str, created_by: int, message_id: Optional[int], pinned: bool,
                        ends_at: Optional[int]) -> int:
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute(
                "INSERT INTO group_events (chat_id, text, message_id, pinned, created_by, created_at, ends_at) VALUES (?,?,?,?,?,?,?)",
                (chat_id, text, message_id, 1 if pinned else 0, created_by, self.now(), ends_at))
            await conn.commit()
            return cur.lastrowid

    async def active_events(self, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            if chat_id is None:
                cur = await conn.execute("SELECT * FROM group_events WHERE status='active' ORDER BY id")
            else:
                cur = await conn.execute("SELECT * FROM group_events WHERE status='active' AND chat_id=? ORDER BY id", (chat_id,))
            return [dict(r) for r in await cur.fetchall()]

    async def get_event(self, chat_id: int, event_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute("SELECT * FROM group_events WHERE id=? AND chat_id=?", (event_id, chat_id))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def finish_event(self, event_id: int, status: str) -> bool:
        """active -> ended|cancelled (once)."""
        if status not in ("ended", "cancelled"):
            raise ValueError(status)
        async with aiosqlite.connect(self.path) as conn:
            cur = await conn.execute("UPDATE group_events SET status=? WHERE id=? AND status='active'", (status, event_id))
            await conn.commit()
            return cur.rowcount == 1

    async def expired_events(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM group_events WHERE status='active' AND ends_at IS NOT NULL AND ends_at <= ?", (self.now(),))
            return [dict(r) for r in await cur.fetchall()]


referral_store = ReferralStore()
