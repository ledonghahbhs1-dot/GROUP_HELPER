import aiosqlite
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import config
from utils.logger import logger

class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS group_settings (
                    chat_id INTEGER PRIMARY KEY,
                    anti_spam INTEGER DEFAULT 1,
                    anti_link INTEGER DEFAULT 1,
                    anti_bot INTEGER DEFAULT 1,
                    anti_badwords INTEGER DEFAULT 1,
                    max_warns INTEGER DEFAULT 5,
                    warn_action TEXT DEFAULT 'ban',
                    mute_duration INTEGER DEFAULT 3600,
                    auto_delete_logs INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS banned_words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER DEFAULT 0,
                    word TEXT NOT NULL,
                    created_by INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chat_id, word)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_warnings (
                    chat_id INTEGER,
                    user_id INTEGER,
                    warn_count INTEGER DEFAULT 0,
                    last_reason TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(chat_id, user_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS whitelisted_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    domain TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chat_id, domain)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS custom_emojis (
                    key_name TEXT PRIMARY KEY,
                    emoji_id TEXT NOT NULL,
                    fallback TEXT DEFAULT ''
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS violation_stats (
                    chat_id INTEGER,
                    violation_type TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY(chat_id, violation_type)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS users_cache (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_cache_username ON users_cache(username)
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    chat_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    full_name TEXT,
                    reason TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(chat_id, user_id)
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_banned_users_username ON banned_users(username)
            """)
            await db.commit()
            logger.info("Database initialized successfully at %s", self.db_path)

    async def get_chat_settings(self, chat_id: int) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM group_settings WHERE chat_id = ?", (chat_id,))
            row = await cursor.fetchone()
            if row:
                return dict(row)
            
            # Default settings (5 warns max -> BAN)
            await db.execute("""
                INSERT INTO group_settings (chat_id, anti_spam, anti_link, anti_bot, anti_badwords, max_warns, warn_action, mute_duration, auto_delete_logs)
                VALUES (?, 1, 1, 1, 1, ?, ?, ?, 1)
            """, (chat_id, config.DEFAULT_MAX_WARNS, config.DEFAULT_WARN_ACTION, config.DEFAULT_MUTE_DURATION))
            await db.commit()
            return {
                "chat_id": chat_id,
                "anti_spam": 1,
                "anti_link": 1,
                "anti_bot": 1,
                "anti_badwords": 1,
                "max_warns": config.DEFAULT_MAX_WARNS,
                "warn_action": config.DEFAULT_WARN_ACTION,
                "mute_duration": config.DEFAULT_MUTE_DURATION,
                "auto_delete_logs": 1
            }

    async def update_chat_setting(self, chat_id: int, key: str, value: Any):
        async with aiosqlite.connect(self.db_path) as db:
            await self.get_chat_settings(chat_id)
            query = f"UPDATE group_settings SET {key} = ? WHERE chat_id = ?"
            await db.execute(query, (value, chat_id))
            await db.commit()

    async def get_all_group_chat_ids(self) -> List[int]:
        """Every group chat_id the bot has ever handled a moderated message
        in (a row is upserted there by get_chat_settings on first contact).
        Used to broadcast announcements (e.g. the VIP flash sale) everywhere
        the bot is active."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT chat_id FROM group_settings")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def get_warns(self, chat_id: int, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT warn_count FROM user_warnings WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def add_warn(self, chat_id: int, user_id: int, reason: str = "") -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT warn_count FROM user_warnings WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id)
            )
            row = await cursor.fetchone()
            current_warns = (row[0] if row else 0) + 1
            await db.execute("""
                INSERT INTO user_warnings (chat_id, user_id, warn_count, last_reason, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    warn_count = ?,
                    last_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
            """, (chat_id, user_id, current_warns, reason, current_warns, reason))
            await db.commit()
            return current_warns

    async def remove_warn(self, chat_id: int, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT warn_count FROM user_warnings WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id)
            )
            row = await cursor.fetchone()
            if not row or row[0] <= 0:
                return 0
            new_count = max(0, row[0] - 1)
            await db.execute("""
                UPDATE user_warnings SET warn_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE chat_id = ? AND user_id = ?
            """, (new_count, chat_id, user_id))
            await db.commit()
            return new_count

    async def reset_warns(self, chat_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM user_warnings WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id)
            )
            await db.commit()

    async def add_banned_word(self, chat_id: int, word: str, created_by: int = 0) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO banned_words (chat_id, word, created_by)
                    VALUES (?, ?, ?)
                """, (chat_id, word.lower().strip(), created_by))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def remove_banned_word(self, chat_id: int, word: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM banned_words WHERE (chat_id = ? OR chat_id = 0) AND word = ?
            """, (chat_id, word.lower().strip()))
            await db.commit()
            return cursor.rowcount > 0

    async def get_banned_words(self, chat_id: int) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT DISTINCT word FROM banned_words WHERE chat_id = ? OR chat_id = 0
            """, (chat_id,))
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def add_whitelist_link(self, chat_id: int, domain: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO whitelisted_links (chat_id, domain)
                    VALUES (?, ?)
                """, (chat_id, domain.lower().strip()))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def remove_whitelist_link(self, chat_id: int, domain: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                DELETE FROM whitelisted_links WHERE chat_id = ? AND domain = ?
            """, (chat_id, domain.lower().strip()))
            await db.commit()
            return cursor.rowcount > 0

    async def get_whitelist_links(self, chat_id: int) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT domain FROM whitelisted_links WHERE chat_id = ?
            """, (chat_id,))
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def set_custom_emoji(self, key_name: str, emoji_id: str, fallback: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO custom_emojis (key_name, emoji_id, fallback)
                VALUES (?, ?, ?)
                ON CONFLICT(key_name) DO UPDATE SET emoji_id = ?, fallback = ?
            """, (key_name, emoji_id, fallback, emoji_id, fallback))
            await db.commit()

    async def get_all_custom_emojis(self) -> Dict[str, Dict[str, str]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM custom_emojis")
            rows = await cursor.fetchall()
            result = {}
            for r in rows:
                result[r["key_name"]] = {"id": r["emoji_id"], "fallback": r["fallback"]}
            return result

    async def increment_stat(self, chat_id: int, violation_type: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO violation_stats (chat_id, violation_type, count)
                VALUES (?, ?, 1)
                ON CONFLICT(chat_id, violation_type) DO UPDATE SET count = count + 1
            """, (chat_id, violation_type))
            await db.commit()

    async def get_stats(self, chat_id: int) -> Dict[str, int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT violation_type, count FROM violation_stats WHERE chat_id = ?
            """, (chat_id,))
            rows = await cursor.fetchall()
            return {r[0]: r[1] for r in rows}

    async def save_user(self, user_id: int, username: str = "", full_name: str = ""):
        """Caches user id, username, and full name for @username admin command resolution"""
        if not user_id:
            return
        clean_username = (username or "").lstrip("@").strip()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users_cache (user_id, username, full_name, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = ?,
                    full_name = CASE WHEN ? != '' THEN ? ELSE users_cache.full_name END,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, clean_username, full_name, clean_username, full_name, full_name))
            await db.commit()

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Looks up cached user by username (case-insensitive)"""
        clean = (username or "").lstrip("@").strip().lower()
        if not clean:
            return None
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT user_id, username, full_name FROM users_cache WHERE LOWER(username) = ? ORDER BY updated_at DESC LIMIT 1
            """, (clean,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Looks up cached user by user ID"""
        if not user_id:
            return None
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT user_id, username, full_name FROM users_cache WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def add_banned_user(self, chat_id: int, user_id: int, username: str = "", full_name: str = "", reason: str = ""):
        """Records a banned user with their username and details"""
        if not user_id:
            return
        clean_username = (username or "").lstrip("@").strip()
        await self.save_user(user_id, clean_username, full_name)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO banned_users (chat_id, user_id, username, full_name, reason, banned_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    username = CASE WHEN ? != '' THEN ? ELSE banned_users.username END,
                    full_name = CASE WHEN ? != '' THEN ? ELSE banned_users.full_name END,
                    reason = ?,
                    banned_at = CURRENT_TIMESTAMP
            """, (chat_id, user_id, clean_username, full_name, reason, clean_username, clean_username, full_name, full_name, reason))
            await db.commit()

    async def remove_banned_user(self, chat_id: int, user_id: int):
        """Removes a user from the banned_users registry"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM banned_users WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            await db.commit()

    async def get_banned_users(self, chat_id: int, limit: int = 50) -> list[Dict[str, Any]]:
        """Returns the list of currently banned users in a chat"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT chat_id, user_id, username, full_name, reason, banned_at
                FROM banned_users
                WHERE chat_id = ?
                ORDER BY banned_at DESC
                LIMIT ?
            """, (chat_id, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_banned_user_by_username(self, username: str, chat_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Looks up a banned user by username across chat or globally"""
        clean = (username or "").lstrip("@").strip().lower()
        if not clean:
            return None
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if chat_id:
                cursor = await db.execute("""
                    SELECT user_id, username, full_name, reason FROM banned_users
                    WHERE chat_id = ? AND LOWER(username) = ?
                    ORDER BY banned_at DESC LIMIT 1
                """, (chat_id, clean))
            else:
                cursor = await db.execute("""
                    SELECT user_id, username, full_name, reason FROM banned_users
                    WHERE LOWER(username) = ?
                    ORDER BY banned_at DESC LIMIT 1
                """, (clean,))
            row = await cursor.fetchone()
            return dict(row) if row else None

db = Database()
