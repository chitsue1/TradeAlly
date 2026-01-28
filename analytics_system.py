"""
Trading Analytics System
========================
📊 სრული სტატისტიკა სიგნალებზე, ფასებზე, და პერფორმანსზე
✅ SQLite ბაზები ყველაფრის შესანახად
✅ Real-time tracking
✅ Performance metrics
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ════════════════════════════════════════════════════════════════

@dataclass
class SignalPerformance:
    """სიგნალის პერფორმანსი"""
    signal_id: int
    symbol: str
    strategy: str
    entry_price: float
    current_price: float
    target_price: float
    stop_loss: float
    entry_time: str
    current_profit_pct: float
    max_profit_reached: float
    min_loss_reached: float
    status: str  # OPEN, TARGET_HIT, STOP_LOSS, EXPIRED
    outcome: Optional[str] = None  # SUCCESS, FAILURE, PENDING


class AnalyticsDatabase:
    """
    ანალიტიკის ბაზის მართვა

    3 მთავარი ცხრილი:
    1. signals - ყველა გაგზავნილი სიგნალი
    2. price_history - ფასების ისტორია
    3. performance - სიგნალების შედეგები
    """

    def __init__(self, db_path: str = "trading_analytics.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """ქმნის ბაზას და ცხრილებს"""
        with sqlite3.connect(self.db_path) as conn:
            # ════════════════════════════════════════════════
            # TABLE 1: SIGNALS - ყველა გაგზავნილი სიგნალი
            # ════════════════════════════════════════════════
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    action TEXT NOT NULL,

                    -- ფასები
                    entry_price REAL NOT NULL,
                    target_price REAL NOT NULL,
                    stop_loss_price REAL NOT NULL,

                    -- დროები
                    entry_timestamp TEXT NOT NULL,
                    expected_hold_duration TEXT,

                    -- ნდობა & რისკი
                    confidence_level TEXT,
                    confidence_score REAL,
                    risk_level TEXT,

                    -- მიზეზები
                    primary_reason TEXT,
                    supporting_reasons TEXT,  -- JSON array
                    risk_factors TEXT,        -- JSON array

                    -- პროგნოზები
                    expected_profit_min REAL,
                    expected_profit_max REAL,
                    market_regime TEXT,

                    -- სტატუსი
                    status TEXT DEFAULT 'ACTIVE',  -- ACTIVE, COMPLETED, STOPPED, EXPIRED
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ════════════════════════════════════════════════
            # TABLE 2: PRICE_HISTORY - ფასების ისტორია
            # ════════════════════════════════════════════════
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL,

                    -- გამოთვლილი მეტრიკები
                    profit_pct REAL,  -- % entry_price-დან
                    distance_to_target_pct REAL,
                    distance_to_stop_pct REAL,

                    FOREIGN KEY (signal_id) REFERENCES signals(id)
                )
            """)

            # ════════════════════════════════════════════════
            # TABLE 3: PERFORMANCE - სიგნალების შედეგები
            # ════════════════════════════════════════════════
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,

                    -- შედეგები
                    outcome TEXT NOT NULL,  -- SUCCESS, FAILURE, STOPPED_EARLY, EXPIRED
                    final_profit_pct REAL NOT NULL,

                    -- მიღწეული ექსტრემუმები
                    max_profit_pct REAL,
                    min_loss_pct REAL,

                    -- დროები
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    hold_duration_hours REAL,

                    -- პროგნოზი vs რეალობა
                    expected_profit_min REAL,
                    expected_profit_max REAL,
                    confidence_score REAL,

                    -- მიზეზი დახურვისა
                    exit_reason TEXT,  -- TARGET_HIT, STOP_LOSS, MANUAL, TIMEOUT

                    FOREIGN KEY (signal_id) REFERENCES signals(id)
                )
            """)

            # ════════════════════════════════════════════════
            # INDEXES - სწრაფი ძებნისთვის
            # ════════════════════════════════════════════════
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_signal ON price_history(signal_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_performance_strategy ON performance(strategy)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_performance_outcome ON performance(outcome)")

            conn.commit()
            logger.info("✅ Analytics database initialized")

    # ════════════════════════════════════════════════════════════
    # RECORDING METHODS
    # ════════════════════════════════════════════════════════════

    def record_signal(self, signal) -> int:
        """
        ახალი სიგნალის ჩაწერა

        Returns:
            signal_id - ჩანაწერის ID
        """
        import json

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO signals (
                    symbol, strategy, action,
                    entry_price, target_price, stop_loss_price,
                    entry_timestamp, expected_hold_duration,
                    confidence_level, confidence_score, risk_level,
                    primary_reason, supporting_reasons, risk_factors,
                    expected_profit_min, expected_profit_max,
                    market_regime, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.symbol,
                signal.strategy_type.value,
                signal.action.value,
                signal.entry_price,
                signal.target_price,
                signal.stop_loss_price,
                signal.entry_timestamp,
                signal.expected_hold_duration,
                signal.confidence_level.value,
                signal.confidence_score,
                signal.risk_level,
                signal.primary_reason,
                json.dumps(signal.supporting_reasons),
                json.dumps(signal.risk_factors),
                signal.expected_profit_min,
                signal.expected_profit_max,
                signal.market_regime,
                'ACTIVE'
            ))

            signal_id = cursor.lastrowid
            conn.commit()

            logger.info(f"📝 Signal recorded: {signal.symbol} (ID: {signal_id})")
            return signal_id

    def record_price_update(self, signal_id: int, symbol: str, 
                           current_price: float, entry_price: float,
                           target_price: float, stop_loss: float):
        """
        ფასის განახლების ჩაწერა
        """
        profit_pct = ((current_price - entry_price) / entry_price) * 100
        distance_to_target = ((target_price - current_price) / current_price) * 100
        distance_to_stop = ((current_price - stop_loss) / current_price) * 100

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO price_history (
                    signal_id, symbol, price, timestamp,
                    profit_pct, distance_to_target_pct, distance_to_stop_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_id, symbol, current_price,
                datetime.now().isoformat(),
                profit_pct, distance_to_target, distance_to_stop
            ))
            conn.commit()

    def record_performance(self, signal_id: int, outcome: str,
                          final_profit_pct: float, exit_reason: str):
        """
        სიგნალის საბოლოო შედეგის ჩაწერა
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get signal details
            cursor = conn.execute("""
                SELECT symbol, strategy, entry_timestamp, entry_price,
                       expected_profit_min, expected_profit_max, confidence_score
                FROM signals WHERE id = ?
            """, (signal_id,))

            row = cursor.fetchone()
            if not row:
                logger.error(f"❌ Signal {signal_id} not found")
                return

            symbol, strategy, entry_time, entry_price, exp_min, exp_max, conf = row

            # Get max/min from price history
            cursor = conn.execute("""
                SELECT MAX(profit_pct), MIN(profit_pct)
                FROM price_history WHERE signal_id = ?
            """, (signal_id,))

            max_profit, min_loss = cursor.fetchone()

            # Calculate hold duration
            entry_dt = datetime.fromisoformat(entry_time)
            exit_dt = datetime.now()
            hold_hours = (exit_dt - entry_dt).total_seconds() / 3600

            # Insert performance
            conn.execute("""
                INSERT INTO performance (
                    signal_id, symbol, strategy, outcome, final_profit_pct,
                    max_profit_pct, min_loss_pct,
                    entry_time, exit_time, hold_duration_hours,
                    expected_profit_min, expected_profit_max, confidence_score,
                    exit_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_id, symbol, strategy, outcome, final_profit_pct,
                max_profit or 0, min_loss or 0,
                entry_time, exit_dt.isoformat(), hold_hours,
                exp_min, exp_max, conf, exit_reason
            ))

            # Update signal status
            conn.execute("""
                UPDATE signals SET status = 'COMPLETED'
                WHERE id = ?
            """, (signal_id,))

            conn.commit()
            logger.info(f"✅ Performance recorded: {symbol} - {outcome} ({final_profit_pct:+.2f}%)")

    # ════════════════════════════════════════════════════════════
    # QUERY METHODS
    # ════════════════════════════════════════════════════════════

    def get_strategy_performance(self, strategy: str) -> Dict:
        """
        სტრატეგიის ჯამური პერფორმანსი
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN outcome = 'FAILURE' THEN 1 ELSE 0 END) as failed,
                    AVG(final_profit_pct) as avg_profit,
                    MAX(final_profit_pct) as best_trade,
                    MIN(final_profit_pct) as worst_trade,
                    AVG(hold_duration_hours) as avg_hold_hours,
                    AVG(confidence_score) as avg_confidence
                FROM performance
                WHERE strategy = ?
            """, (strategy,))

            row = cursor.fetchone()

            if not row or row[0] == 0:
                return {
                    "total_signals": 0,
                    "successful": 0,
                    "failed": 0,
                    "success_rate": 0,
                    "avg_profit": 0,
                    "best_trade": 0,
                    "worst_trade": 0,
                    "avg_hold_hours": 0,
                    "avg_confidence": 0
                }

            total, success, fail, avg_profit, best, worst, avg_hold, avg_conf = row

            return {
                "total_signals": total,
                "successful": success or 0,
                "failed": fail or 0,
                "success_rate": (success / total * 100) if total > 0 else 0,
                "avg_profit": avg_profit or 0,
                "best_trade": best or 0,
                "worst_trade": worst or 0,
                "avg_hold_hours": avg_hold or 0,
                "avg_confidence": avg_conf or 0
            }

    def get_active_signals(self) -> List[Dict]:
        """
        ყველა აქტიური სიგნალი
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    id, symbol, strategy, entry_price, target_price,
                    stop_loss_price, entry_timestamp, confidence_score,
                    expected_profit_max
                FROM signals
                WHERE status = 'ACTIVE'
                ORDER BY entry_timestamp DESC
            """)

            signals = []
            for row in cursor.fetchall():
                signals.append({
                    "id": row[0],
                    "symbol": row[1],
                    "strategy": row[2],
                    "entry_price": row[3],
                    "target_price": row[4],
                    "stop_loss": row[5],
                    "entry_time": row[6],
                    "confidence": row[7],
                    "expected_profit": row[8]
                })

            return signals

    def get_symbol_history(self, symbol: str) -> Dict:
        """
        კონკრეტული აქტივის ისტორია
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END) as wins,
                    AVG(final_profit_pct) as avg_profit
                FROM performance
                WHERE symbol = ?
            """, (symbol,))

            row = cursor.fetchone()
            total, wins, avg = row if row else (0, 0, 0)

            return {
                "total_signals": total or 0,
                "wins": wins or 0,
                "win_rate": (wins / total * 100) if total > 0 else 0,
                "avg_profit": avg or 0
            }

    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """
        ბოლო N სიგნალი
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    s.symbol, s.strategy, s.entry_price, s.entry_timestamp,
                    s.confidence_score, s.status,
                    p.outcome, p.final_profit_pct
                FROM signals s
                LEFT JOIN performance p ON s.id = p.signal_id
                ORDER BY s.entry_timestamp DESC
                LIMIT ?
            """, (limit,))

            signals = []
            for row in cursor.fetchall():
                signals.append({
                    "symbol": row[0],
                    "strategy": row[1],
                    "entry_price": row[2],
                    "time": row[3],
                    "confidence": row[4],
                    "status": row[5],
                    "outcome": row[6],
                    "profit": row[7]
                })

            return signals

    def get_overall_stats(self) -> Dict:
        """
        ზოგადი სტატისტიკა
        """
        with sqlite3.connect(self.db_path) as conn:
            # Total signals
            cursor = conn.execute("SELECT COUNT(*) FROM signals")
            total_signals = cursor.fetchone()[0]

            # Active signals
            cursor = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'ACTIVE'")
            active_signals = cursor.fetchone()[0]

            # Completed trades
            cursor = conn.execute("SELECT COUNT(*) FROM performance")
            completed_trades = cursor.fetchone()[0]

            # Overall performance
            cursor = conn.execute("""
                SELECT 
                    SUM(CASE WHEN outcome = 'SUCCESS' THEN 1 ELSE 0 END) as wins,
                    AVG(final_profit_pct) as avg_profit,
                    SUM(final_profit_pct) as total_profit
                FROM performance
            """)
            wins, avg_profit, total_profit = cursor.fetchone()

            return {
                "total_signals": total_signals,
                "active_signals": active_signals,
                "completed_trades": completed_trades,
                "wins": wins or 0,
                "win_rate": (wins / completed_trades * 100) if completed_trades > 0 else 0,
                "avg_profit_per_trade": avg_profit or 0,
                "total_profit": total_profit or 0
            }


# ════════════════════════════════════════════════════════════════
# DASHBOARD GENERATOR
# ════════════════════════════════════════════════════════════════

class AnalyticsDashboard:
    """
    Dashboard-ის გენერატორი - ტერმინალში და Telegram-ში საჩვენებლად
    """

    def __init__(self, analytics_db: AnalyticsDatabase):
        self.db = analytics_db

    def generate_text_dashboard(self) -> str:
        """
        ტექსტური dashboard (Telegram-ისთვის)
        """
        overall = self.db.get_overall_stats()

        dashboard = "📊 **TRADING ANALYTICS DASHBOARD**\n"
        dashboard += "═" * 40 + "\n\n"

        # Overall Stats
        dashboard += "**📈 OVERALL PERFORMANCE:**\n"
        dashboard += f"• Total Signals: {overall['total_signals']}\n"
        dashboard += f"• Active: {overall['active_signals']}\n"
        dashboard += f"• Completed: {overall['completed_trades']}\n"
        dashboard += f"• Win Rate: {overall['win_rate']:.1f}%\n"
        dashboard += f"• Avg Profit/Trade: {overall['avg_profit_per_trade']:+.2f}%\n"
        dashboard += f"• Total Profit: {overall['total_profit']:+.2f}%\n\n"

        # Strategy Performance
        dashboard += "**🎯 STRATEGY PERFORMANCE:**\n\n"

        for strategy in ['long_term', 'scalping', 'opportunistic']:
            perf = self.db.get_strategy_performance(strategy)

            if perf['total_signals'] == 0:
                dashboard += f"**{strategy.upper()}:** No data yet\n\n"
                continue

            dashboard += f"**{strategy.upper()}:**\n"
            dashboard += f"• Signals: {perf['total_signals']}\n"
            dashboard += f"• Success Rate: {perf['success_rate']:.1f}%\n"
            dashboard += f"• Avg Profit: {perf['avg_profit']:+.2f}%\n"
            dashboard += f"• Best Trade: {perf['best_trade']:+.2f}%\n"
            dashboard += f"• Worst Trade: {perf['worst_trade']:+.2f}%\n"
            dashboard += f"• Avg Hold: {perf['avg_hold_hours']:.1f}h\n\n"

        # Recent Signals
        recent = self.db.get_recent_signals(5)

        if recent:
            dashboard += "**📝 RECENT SIGNALS:**\n"
            for sig in recent:
                status_emoji = "✅" if sig['outcome'] == 'SUCCESS' else "❌" if sig['outcome'] == 'FAILURE' else "⏳"
                profit_str = f"{sig['profit']:+.2f}%" if sig['profit'] else "Pending"
                dashboard += f"{status_emoji} {sig['symbol']} ({sig['strategy']}) - {profit_str}\n"

        return dashboard

    def generate_console_dashboard(self):
        """
        კონსოლის dashboard (ლოგებისთვის)
        """
        overall = self.db.get_overall_stats()

        print("\n" + "═" * 60)
        print("📊 TRADING ANALYTICS DASHBOARD")
        print("═" * 60)

        print(f"\n📈 OVERALL:")
        print(f"   Total Signals: {overall['total_signals']}")
        print(f"   Active: {overall['active_signals']} | Completed: {overall['completed_trades']}")
        print(f"   Win Rate: {overall['win_rate']:.1f}%")
        print(f"   Total Profit: {overall['total_profit']:+.2f}%")

        print(f"\n🎯 STRATEGY BREAKDOWN:")

        for strategy in ['long_term', 'scalping', 'opportunistic']:
            perf = self.db.get_strategy_performance(strategy)

            if perf['total_signals'] == 0:
                continue

            print(f"\n   {strategy.upper()}:")
            print(f"   ├─ Signals: {perf['total_signals']}")
            print(f"   ├─ Win Rate: {perf['success_rate']:.1f}%")
            print(f"   ├─ Avg Profit: {perf['avg_profit']:+.2f}%")
            print(f"   └─ Best: {perf['best_trade']:+.2f}% | Worst: {perf['worst_trade']:+.2f}%")

        print("\n" + "═" * 60 + "\n")