"""
═══════════════════════════════════════════════════════════════════════════════
SIGNAL HISTORY DATABASE - v1.0
═══════════════════════════════════════════════════════════════════════════════

💡 იდეა:
✅ ᲛᲮᲝᲚᲝᲓ გაგზავნილი სიგნალები (არა AI-ის უარყოფილი)
✅ REAL ფასი როცა მომწერა
✅ REAL ფასი როცა დაკეტო (user აღმოჩნდა? stop loss? timeout?)
✅ რამდენი დღე დაჰოდა
✅ რამდენი % მოგება/ზარალი
✅ გრაფიკი: "წინა 30 სიგნალი - win/loss"

✅ ᲐᲠᲘᲡ ᲨᲔᲜᲐᲮᲣᲚᲘ:
- თითოეული სიგნალი რო გაიგზავნა
- როცა დაკეტო (user თხოვნის მიხედვით)
- პროფიტ %
- საიდან რამდენი დღე

❌ ᲐᲠᲘᲡ ᲨᲔᲜᲐᲮᲣᲚᲘ:
- AI-ის უარყოფილი (ეს internal, მომხმარებელი არ იცის)
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════

class SignalStatus(Enum):
    """სიგნალის სტატუსი"""
    SENT = "sent"              # ტელეგრამზე გაიგზავნა
    WAITING_ENTRY = "waiting"  # ელოდება შესვლას
    ENTRY_FILLED = "entry"     # user შევიდა
    CLOSED_WIN = "win"          # დაკეტო მოგებით
    CLOSED_LOSS = "loss"        # დაკეტო ზარალით
    CLOSED_TIMEOUT = "timeout"  # დრო გასული
    CANCELLED = "cancelled"     # გაუქმა

@dataclass
class SentSignal:
    """გაგზავნილი სიგნალი"""
    # Signal info
    symbol: str
    strategy: str
    entry_price: float
    target_price: float
    stop_loss_price: float

    # Time
    sent_time: str  # ISO format

    # Confidence
    confidence_score: float
    ai_approved: bool

    # Expectations
    expected_profit_min: float
    expected_profit_max: float

    # Additional
    tier: str
    message_text: str  # რას დაწერა telegram-ში

@dataclass
class SignalResult:
    """სიგნალის შედეგი"""
    signal_id: int
    symbol: str

    # Entry
    actual_entry_price: float  # რაზე შევიდა user (თუ შევიდა)
    entry_time: str  # user-ის entry დრო

    # Exit
    exit_price: float  # რაზე გამოვიდა
    exit_time: str  # გამოსვლის დრო
    exit_reason: str  # "target", "stop", "timeout", "manual"

    # P&L
    profit_pct: float
    profit_usd: Optional[float] = None  # თუ user-ი თქვა თუ რა თანხა

    # Duration
    days_held: float

    # Status
    status: SignalStatus

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════

class SignalHistoryDB:
    """
    SIGNAL HISTORY DATABASE

    სიგნალის ყველა ისტორია რო გაიგზავნა
    """

    def __init__(self, db_path: str = "signal_history.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Database initialization"""

        with sqlite3.connect(self.db_path) as conn:
            # ════════════════════════════════════════════════════════════════
            # TABLE 1: SENT_SIGNALS - ყველა გაგზავნილი სიგნალი
            # ════════════════════════════════════════════════════════════════

            conn.execute("""
                CREATE TABLE IF NOT EXISTS sent_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- Signal info
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    target_price REAL NOT NULL,
                    stop_loss_price REAL NOT NULL,

                    -- Time
                    sent_time TEXT NOT NULL,

                    -- Confidence
                    confidence_score REAL NOT NULL,
                    ai_approved INTEGER NOT NULL,

                    -- Expectations
                    expected_profit_min REAL NOT NULL,
                    expected_profit_max REAL NOT NULL,

                    -- Additional
                    tier TEXT,
                    message_text TEXT,

                    -- Metadata
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ════════════════════════════════════════════════════════════════
            # TABLE 2: SIGNAL_RESULTS - სიგნალის შედეგი
            # ════════════════════════════════════════════════════════════════

            conn.execute("""
                CREATE TABLE IF NOT EXISTS signal_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER UNIQUE NOT NULL,

                    -- Entry
                    actual_entry_price REAL,
                    entry_time TEXT,

                    -- Exit
                    exit_price REAL,
                    exit_time TEXT,
                    exit_reason TEXT,

                    -- P&L
                    profit_pct REAL,
                    profit_usd REAL,

                    -- Duration
                    days_held REAL,

                    -- Status
                    status TEXT NOT NULL,

                    -- Notes
                    notes TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (signal_id) REFERENCES sent_signals(id)
                )
            """)

            # ════════════════════════════════════════════════════════════════
            # INDEXES
            # ════════════════════════════════════════════════════════════════

            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON sent_signals(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy ON sent_signals(strategy)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON signal_results(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sent_time ON sent_signals(sent_time)")

            conn.commit()
            logger.info("✅ Signal History DB initialized")

    # ═══════════════════════════════════════════════════════════════════════
    # WRITE METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def record_sent_signal(self, signal: SentSignal) -> int:
        """
        ნოვი სიგნალი რო გაიგზავნა

        Returns: signal_id
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO sent_signals (
                    symbol, strategy, entry_price, target_price, stop_loss_price,
                    sent_time, confidence_score, ai_approved,
                    expected_profit_min, expected_profit_max,
                    tier, message_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.symbol,
                signal.strategy,
                signal.entry_price,
                signal.target_price,
                signal.stop_loss_price,
                signal.sent_time,
                signal.confidence_score,
                1 if signal.ai_approved else 0,
                signal.expected_profit_min,
                signal.expected_profit_max,
                signal.tier,
                signal.message_text
            ))

            signal_id = cursor.lastrowid

            # Create empty result row
            conn.execute("""
                INSERT INTO signal_results (signal_id, status)
                VALUES (?, ?)
            """, (signal_id, SignalStatus.SENT.value))

            conn.commit()

            logger.info(f"📝 Signal recorded: {signal.symbol} (ID: {signal_id})")
            return signal_id

    def record_signal_result(self, result: SignalResult):
        """
        სიგნალის შედეგი (როცა დაკეტო)
        """

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE signal_results
                SET
                    actual_entry_price = ?,
                    entry_time = ?,
                    exit_price = ?,
                    exit_time = ?,
                    exit_reason = ?,
                    profit_pct = ?,
                    profit_usd = ?,
                    days_held = ?,
                    status = ?
                WHERE signal_id = ?
            """, (
                result.actual_entry_price,
                result.entry_time,
                result.exit_price,
                result.exit_time,
                result.exit_reason,
                result.profit_pct,
                result.profit_usd,
                result.days_held,
                result.status.value,
                result.signal_id
            ))

            conn.commit()

            logger.info(
                f"✅ Result recorded: {result.symbol} | "
                f"{result.profit_pct:+.2f}% | {result.exit_reason}"
            )

    def add_note(self, signal_id: int, note: str):
        """დამატებითი ჩანაწერი"""

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE signal_results
                SET notes = ?
                WHERE signal_id = ?
            """, (note, signal_id))

            conn.commit()

    # ═══════════════════════════════════════════════════════════════════════
    # READ METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def get_signal_with_result(self, signal_id: int) -> Optional[Dict]:
        """
        სიგნალი + შედეგი
        """

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT
                    s.*,
                    r.actual_entry_price,
                    r.entry_time,
                    r.exit_price,
                    r.exit_time,
                    r.exit_reason,
                    r.profit_pct,
                    r.profit_usd,
                    r.days_held,
                    r.status,
                    r.notes
                FROM sent_signals s
                LEFT JOIN signal_results r ON s.id = r.signal_id
                WHERE s.id = ?
            """, (signal_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_recent_signals(self, limit: int = 30) -> List[Dict]:
        """
        ბოლო N სიგნალი (რო გაიგზავნა)
        """

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT
                    s.id,
                    s.symbol,
                    s.strategy,
                    s.entry_price,
                    s.target_price,
                    s.sent_time,
                    s.confidence_score,
                    r.status,
                    r.profit_pct,
                    r.exit_reason,
                    r.days_held
                FROM sent_signals s
                LEFT JOIN signal_results r ON s.id = r.signal_id
                ORDER BY s.sent_time DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_symbol_history(self, symbol: str) -> Dict:
        """
        კონკრეტული symbol-ის ისტორია
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN r.profit_pct > 0 THEN 1 ELSE 0 END) as wins,
                    AVG(r.profit_pct) as avg_profit,
                    MAX(r.profit_pct) as best_trade,
                    MIN(r.profit_pct) as worst_trade,
                    SUM(r.profit_pct) as total_profit
                FROM sent_signals s
                LEFT JOIN signal_results r ON s.id = r.signal_id
                WHERE s.symbol = ? AND r.status IS NOT NULL
            """, (symbol,))

            row = cursor.fetchone()
            total, wins, avg, best, worst, total_prof = row

            return {
                'symbol': symbol,
                'total_signals': total or 0,
                'wins': wins or 0,
                'win_rate': (wins / total * 100) if total else 0,
                'avg_profit': avg or 0,
                'best_trade': best or 0,
                'worst_trade': worst or 0,
                'total_profit': total_prof or 0
            }

    def get_strategy_performance(self, strategy: str) -> Dict:
        """
        სტრატეგიის performance
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN r.profit_pct > 0 THEN 1 ELSE 0 END) as wins,
                    AVG(r.profit_pct) as avg_profit,
                    AVG(r.days_held) as avg_days
                FROM sent_signals s
                LEFT JOIN signal_results r ON s.id = r.signal_id
                WHERE s.strategy = ? AND r.status IS NOT NULL
            """, (strategy,))

            row = cursor.fetchone()
            total, wins, avg, avg_days = row

            return {
                'strategy': strategy,
                'total_signals': total or 0,
                'wins': wins or 0,
                'win_rate': (wins / total * 100) if total else 0,
                'avg_profit_pct': avg or 0,
                'avg_days_held': avg_days or 0
            }

    def get_overall_stats(self) -> Dict:
        """
        მთლიანი სტატისტიკა
        """

        with sqlite3.connect(self.db_path) as conn:
            # Total signals sent
            cursor = conn.execute("SELECT COUNT(*) FROM sent_signals")
            total_sent = cursor.fetchone()[0]

            # Closed signals
            cursor = conn.execute(
                "SELECT COUNT(*) FROM signal_results WHERE status != ?"
                "", (SignalStatus.SENT.value,)
            )
            total_closed = cursor.fetchone()[0]

            # Results
            cursor = conn.execute("""
                SELECT
                    SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) as wins,
                    AVG(profit_pct) as avg_profit,
                    SUM(profit_pct) as total_profit
                FROM signal_results
                WHERE status != ?
            """, (SignalStatus.SENT.value,))

            wins, avg_profit, total_profit = cursor.fetchone()

            return {
                'total_signals_sent': total_sent,
                'total_signals_closed': total_closed,
                'pending': total_sent - total_closed,
                'wins': wins or 0,
                'win_rate': (wins / total_closed * 100) if total_closed else 0,
                'avg_profit_pct': avg_profit or 0,
                'total_profit_pct': total_profit or 0
            }

    # ═══════════════════════════════════════════════════════════════════════
    # REPORTING
    # ═══════════════════════════════════════════════════════════════════════

    def generate_report(self) -> str:
        """
        დაწვრილებული რეპორტი
        """

        stats = self.get_overall_stats()
        recent = self.get_recent_signals(limit=10)

        report = "📊 **SIGNAL HISTORY REPORT**\n\n"

        # Overall
        report += f"**📈 მთლიანი:**\n"
        report += f"• გაგზავნილი: {stats['total_signals_sent']}\n"
        report += f"• დახურული: {stats['total_signals_closed']}\n"
        report += f"• ელოდება: {stats['pending']}\n"
        report += f"• Win Rate: {stats['win_rate']:.1f}%\n"
        report += f"• საშუალო მოგება: {stats['avg_profit_pct']:+.2f}%\n"
        report += f"• ჯამი: {stats['total_profit_pct']:+.2f}%\n\n"

        # Recent
        report += "**📝 ბოლო 10 სიგნალი:**\n\n"
        for sig in recent:
            emoji = "✅" if (sig['profit_pct'] and sig['profit_pct'] > 0) else "❌"
            status = sig['status'] or "⏳"
            profit_str = f"{sig['profit_pct']:+.2f}%" if sig['profit_pct'] else "Pending"

            report += f"{emoji} {sig['symbol']} ({sig['strategy']})\n"
            report += f"   └─ {profit_str} | {sig['exit_reason'] or 'waiting'}\n"

        return report

    def get_dashboard_data(self) -> Dict:
        """
        დაშბორდის ამჟამინდელი მონაცემი
        """

        stats = self.get_overall_stats()

        return {
            'total_signals': stats['total_signals_sent'],
            'closed': stats['total_signals_closed'],
            'pending': stats['pending'],
            'win_rate': stats['win_rate'],
            'avg_profit': stats['avg_profit_pct'],
            'total_profit': stats['total_profit_pct'],
            'last_updated': datetime.now().isoformat()
        }

# ═══════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # Initialize DB
    db = SignalHistoryDB("signal_history.db")

    # Example 1: Record a sent signal
    sent_signal = SentSignal(
        symbol="BTC/USD",
        strategy="long_term",
        entry_price=45000.0,
        target_price=47000.0,
        stop_loss_price=43500.0,
        sent_time=datetime.now().isoformat(),
        confidence_score=75.0,
        ai_approved=True,
        expected_profit_min=2.0,
        expected_profit_max=6.0,
        tier="BLUE_CHIP",
        message_text="🔵 Long-Term Investment..."
    )

    signal_id = db.record_sent_signal(sent_signal)
    print(f"✅ Signal recorded with ID: {signal_id}")

    # Example 2: Record result (simulating user closing at profit)
    from datetime import timedelta

    exit_time_dt = datetime.now() + timedelta(days=3)

    result = SignalResult(
        signal_id=signal_id,
        symbol="BTC/USD",
        actual_entry_price=45000.0,
        entry_time=datetime.now().isoformat(),
        exit_price=46500.0,  # User closed at 46500
        exit_time=exit_time_dt.isoformat(),
        exit_reason="manual",  # User closed manually
        profit_pct=3.33,  # 1500 / 45000 * 100
        profit_usd=1500.0,  # If user had 1 BTC
        days_held=3.0,
        status=SignalStatus.CLOSED_WIN
    )

    db.record_signal_result(result)
    print(f"✅ Result recorded")

    # Example 3: Get report
    report = db.generate_report()
    print(report)

    # Example 4: Get dashboard
    dashboard = db.get_dashboard_data()
    print(f"📊 Dashboard: {dashboard}")