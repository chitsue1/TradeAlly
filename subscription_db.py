"""
═══════════════════════════════════════════════════════════════════════════════
SUBSCRIPTION DB v1.0 — Railway-safe SQLite persistence
═══════════════════════════════════════════════════════════════════════════════

პრობლემა: Railway ephemeral filesystem — JSON ფაილები restart-ზე იშლება.
გამოსავალი: SQLite database (ყველა სხვა DB ფაილი ისედაც SQLite-ია).

✅ Drop-in replacement subscriptions.json-ისთვის
✅ /adduser, /removeuser, /listusers — ყველა command unchanged
✅ Backup to JSON on every write (legacy compat)
═══════════════════════════════════════════════════════════════════════════════
"""

import sqlite3
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SUBS_DB = "subscriptions.db"


class SubscriptionDB:
    """
    SQLite-backed subscription store.
    Railway restarts-safe — ყველა სხვა .db ფაილი ისედაც გადარჩება.

    API მიირება dict-ის მსგავსია:
        db[user_id]           → sub dict | None
        db[user_id] = data    → upsert
        del db[user_id]       → remove
        user_id in db         → check exists
        db.keys()             → all user_ids
    """

    def __init__(self, db_path: str = SUBS_DB):
        self.db_path = db_path
        self._cache: Dict[int, Dict] = {}
        self._init_db()
        self._load_cache()
        logger.info(f"✅ SubscriptionDB ready ({len(self._cache)} users)")

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_id      INTEGER PRIMARY KEY,
                    expires_at   TEXT    NOT NULL,
                    activated_at TEXT    NOT NULL,
                    plan         TEXT    DEFAULT 'premium',
                    days         INTEGER DEFAULT 30,
                    username     TEXT,
                    notes        TEXT,
                    updated_at   TEXT    DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sub_expires ON subscriptions(expires_at)")
            conn.commit()

    def _load_cache(self):
        """Load all subs into memory cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM subscriptions").fetchall()
        self._cache = {}
        for row in rows:
            self._cache[row["user_id"]] = dict(row)
        logger.debug(f"SubscriptionDB cache loaded: {len(self._cache)} rows")

    # ═══════════════════════════════════════════════════════════════════════
    # DICT-LIKE INTERFACE (backward compat with old self.subscriptions dict)
    # ═══════════════════════════════════════════════════════════════════════

    def __getitem__(self, user_id: int) -> Dict:
        return self._cache[int(user_id)]

    def __setitem__(self, user_id: int, data: Dict):
        user_id = int(user_id)
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO subscriptions
                    (user_id, expires_at, activated_at, plan, days, username, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    expires_at   = excluded.expires_at,
                    activated_at = excluded.activated_at,
                    plan         = excluded.plan,
                    days         = excluded.days,
                    username     = excluded.username,
                    notes        = excluded.notes,
                    updated_at   = excluded.updated_at
            """, (
                user_id,
                data.get("expires_at", ""),
                data.get("activated_at", now),
                data.get("plan", "premium"),
                data.get("days", 30),
                data.get("username"),
                data.get("notes"),
                now,
            ))
            conn.commit()
        self._cache[user_id] = data
        self._backup_json()

    def __delitem__(self, user_id: int):
        user_id = int(user_id)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
            conn.commit()
        self._cache.pop(user_id, None)
        self._backup_json()

    def __contains__(self, user_id) -> bool:
        return int(user_id) in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def keys(self):
        return self._cache.keys()

    def items(self):
        return self._cache.items()

    def values(self):
        return self._cache.values()

    def get(self, user_id, default=None):
        return self._cache.get(int(user_id), default)

    def pop(self, user_id, default=None):
        user_id = int(user_id)
        if user_id in self._cache:
            del self[user_id]
            return self._cache.get(user_id, default)
        return default

    # ═══════════════════════════════════════════════════════════════════════
    # HIGH-LEVEL METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def add_subscription(self, user_id: int, days: int = 30, username: str = None) -> bool:
        """Add or extend subscription."""
        user_id = int(user_id)
        expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        self[user_id] = {
            "expires_at":   expires,
            "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plan":         "premium",
            "days":         days,
            "username":     username,
        }
        logger.info(f"✅ Subscription added: user={user_id} days={days} expires={expires}")
        return True

    def remove_subscription(self, user_id: int) -> bool:
        """Remove subscription."""
        user_id = int(user_id)
        if user_id in self._cache:
            del self[user_id]
            logger.info(f"✅ Subscription removed: user={user_id}")
            return True
        return False

    def is_active(self, user_id: int) -> bool:
        """Check if subscription is active today."""
        user_id = int(user_id)
        sub = self._cache.get(user_id)
        if not sub:
            return False
        expires_str = sub.get("expires_at", "")
        if not expires_str:
            return False
        try:
            expires = datetime.strptime(expires_str, "%Y-%m-%d").date()
            return datetime.now().date() <= expires
        except Exception:
            return False

    def get_active_ids(self) -> List[int]:
        """Return list of active subscriber IDs."""
        return [uid for uid in self._cache.keys() if self.is_active(uid)]

    def get_all_ids(self) -> List[int]:
        return list(self._cache.keys())

    def days_left(self, user_id: int) -> int:
        """Days remaining in subscription."""
        sub = self._cache.get(int(user_id))
        if not sub:
            return 0
        try:
            expires = datetime.strptime(sub["expires_at"], "%Y-%m-%d").date()
            delta = (expires - datetime.now().date()).days
            return max(delta, 0)
        except Exception:
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # MIGRATION: JSON → SQLite
    # ═══════════════════════════════════════════════════════════════════════

    def migrate_from_json(self, json_path: str = "subscriptions.json") -> int:
        """
        One-time migration from old subscriptions.json → SQLite.
        Safe to call every startup — skips existing records.
        """
        if not os.path.exists(json_path):
            return 0

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            migrated = 0
            for k, v in data.items():
                user_id = int(k)
                if user_id not in self._cache:
                    self[user_id] = v
                    migrated += 1

            if migrated:
                logger.info(f"✅ Migrated {migrated} subscriptions from {json_path}")
                # Rename old file so migration doesn't run again
                os.rename(json_path, json_path + ".migrated")

            return migrated

        except Exception as e:
            logger.error(f"❌ Migration error: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # BACKUP (write JSON for manual inspection)
    # ═══════════════════════════════════════════════════════════════════════

    def _backup_json(self):
        """Write JSON backup after every change (for debugging/admin)."""
        try:
            data = {str(k): v for k, v in self._cache.items()}
            with open("subscriptions_backup.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"Backup write failed: {e}")

    def stats(self) -> Dict:
        """Return quick stats dict."""
        active = self.get_active_ids()
        return {
            "total":   len(self._cache),
            "active":  len(active),
            "expired": len(self._cache) - len(active),
        }