"""
═══════════════════════════════════════════════════════════════════════════════
SIGNAL MEMORY v1.0 — კრიპტოს მეხსიერება
═══════════════════════════════════════════════════════════════════════════════

თითოეულ კრიპტოზე ინახავს ბოლო 3 სიგნალს:
- entry price, confidence, strategy, outcome
- AI იყენებს ამ ისტორიას შემდეგი სიგნალის შეფასებისას
- "ETH-ზე ბოლო 3 სიგნალიდან 2 win იყო — bullish pattern"

გამოყენება:
    memory = SignalMemory()
    memory.record_signal(symbol, entry, strategy, confidence, tier)
    history = memory.get_history(symbol)  # AI prompt-ისთვის
    memory.update_outcome(symbol, exit_price, profit_pct, win)
═══════════════════════════════════════════════════════════════════════════════
"""

import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

MEMORY_DB = "signal_memory.db"
MAX_PER_SYMBOL = 3


class SignalMemory:
    """
    Per-symbol signal memory.
    ინახავს ბოლო MAX_PER_SYMBOL სიგნალს თითოეული კრიპტოსთვის.
    AI იყენებს evaluate_signal()-ში context-ად.
    """

    def __init__(self, db_path: str = MEMORY_DB):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS symbol_memory (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol       TEXT NOT NULL,
                    entry_price  REAL NOT NULL,
                    strategy     TEXT NOT NULL,
                    confidence   REAL NOT NULL,
                    tier         TEXT NOT NULL,
                    sent_at      TEXT NOT NULL,

                    -- outcome (filled after exit)
                    exit_price   REAL,
                    profit_pct   REAL,
                    win          INTEGER,          -- 1=win, 0=loss, NULL=pending
                    exit_reason  TEXT,
                    exited_at    TEXT,

                    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_symbol ON symbol_memory(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_sent ON symbol_memory(sent_at)")
            conn.commit()
        logger.info("✅ SignalMemory initialized")

    # ═══════════════════════════════════════════════════════════════════════
    # WRITE
    # ═══════════════════════════════════════════════════════════════════════

    def record_signal(
        self,
        symbol: str,
        entry_price: float,
        strategy: str,
        confidence: float,
        tier: str,
    ) -> int:
        """ახალი სიგნალის ჩაწერა. Returns row id."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO symbol_memory
                    (symbol, entry_price, strategy, confidence, tier, sent_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol, entry_price, strategy, confidence, tier, now))
            row_id = cursor.lastrowid

            # Keep only last MAX_PER_SYMBOL per symbol
            conn.execute("""
                DELETE FROM symbol_memory
                WHERE symbol = ?
                  AND id NOT IN (
                      SELECT id FROM symbol_memory
                      WHERE symbol = ?
                      ORDER BY sent_at DESC
                      LIMIT ?
                  )
            """, (symbol, symbol, MAX_PER_SYMBOL))
            conn.commit()

        logger.debug(f"📝 Memory: {symbol} signal recorded (id={row_id})")
        return row_id

    def update_outcome(
        self,
        symbol: str,
        exit_price: float,
        profit_pct: float,
        win: bool,
        exit_reason: str = "unknown",
    ):
        """Exit-ის შემდეგ outcome-ის განახლება (ბოლო pending სიგნალი)."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE symbol_memory
                SET exit_price  = ?,
                    profit_pct  = ?,
                    win         = ?,
                    exit_reason = ?,
                    exited_at   = ?
                WHERE symbol = ?
                  AND win IS NULL
                ORDER BY sent_at DESC
                LIMIT 1
            """, (exit_price, profit_pct, 1 if win else 0, exit_reason, now, symbol))
            conn.commit()
        logger.debug(f"📝 Memory: {symbol} outcome updated ({profit_pct:+.2f}%)")

    # ═══════════════════════════════════════════════════════════════════════
    # READ
    # ═══════════════════════════════════════════════════════════════════════

    def get_history(self, symbol: str) -> List[Dict]:
        """ბოლო MAX_PER_SYMBOL სიგნალი — AI prompt-ისთვის."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT symbol, entry_price, strategy, confidence, tier,
                       sent_at, exit_price, profit_pct, win, exit_reason
                FROM symbol_memory
                WHERE symbol = ?
                ORDER BY sent_at DESC
                LIMIT ?
            """, (symbol, MAX_PER_SYMBOL))
            return [dict(r) for r in cursor.fetchall()]

    def get_summary(self, symbol: str) -> str:
        """
        AI prompt-ში ჩასასმელი მოკლე summary.
        მაგ: "ETH/USD history: 2/3 wins | avg +7.2% | last: swing +12.1%"
        """
        history = self.get_history(symbol)
        if not history:
            return ""

        closed = [h for h in history if h["win"] is not None]
        pending = [h for h in history if h["win"] is None]

        if not closed:
            pending_str = f"{len(pending)} pending signal(s)"
            return f"{symbol} history: {pending_str} (no closed trades yet)"

        wins    = sum(1 for h in closed if h["win"] == 1)
        total   = len(closed)
        profits = [h["profit_pct"] for h in closed if h["profit_pct"] is not None]
        avg_p   = sum(profits) / len(profits) if profits else 0

        last = closed[0]
        last_str = (
            f"last={last['strategy']} {last['profit_pct']:+.1f}%"
            if last["profit_pct"] is not None else "last=pending"
        )

        pending_str = f" | {len(pending)} pending" if pending else ""

        return (
            f"{symbol} history: {wins}/{total} wins | "
            f"avg {avg_p:+.1f}% | {last_str}{pending_str}"
        )

    def get_symbol_stats(self, symbol: str) -> Dict:
        """Symbol-ის სტატისტიკა."""
        history = self.get_history(symbol)
        closed  = [h for h in history if h["win"] is not None]
        if not closed:
            return {"symbol": symbol, "total": 0, "wins": 0, "win_rate": 0, "avg_profit": 0}

        wins    = sum(1 for h in closed if h["win"] == 1)
        profits = [h["profit_pct"] for h in closed if h["profit_pct"]]

        return {
            "symbol":     symbol,
            "total":      len(closed),
            "wins":       wins,
            "win_rate":   wins / len(closed) * 100,
            "avg_profit": sum(profits) / len(profits) if profits else 0,
            "history":    closed,
        }
