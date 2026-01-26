import sqlite3
from datetime import datetime

class TradingDB:
    def __init__(self, db_name="trading_data.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """ქმნის ცხრილებს, თუ ისინი არ არსებობს"""
        with sqlite3.connect(self.db_name) as conn:
            # ცხრილი სტრატეგიების სტატისტიკისთვის
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_stats (
                    strategy_name TEXT PRIMARY KEY,
                    signals_sent INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    last_update TIMESTAMP
                )
            """)
            # ცხრილი კონკრეტული სიგნალების ისტორიისთვის
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signal_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    strategy TEXT,
                    entry_price REAL,
                    timestamp TIMESTAMP
                )
            """)
            conn.commit()

    def update_signal_count(self, strategy_name, symbol, price):
        """აგროვებს სტატისტიკას ყოველი ახალი სიგნალისას"""
        with sqlite3.connect(self.db_name) as conn:
            # 1. ვამატებთ ისტორიაში
            conn.execute(
                "INSERT INTO signal_history (symbol, strategy, entry_price, timestamp) VALUES (?, ?, ?, ?)",
                (symbol, strategy_name, price, datetime.now().isoformat())
            )
            # 2. ვანახლებთ ზოგად სტატისტიკას
            conn.execute("""
                INSERT INTO strategy_stats (strategy_name, signals_sent, last_update)
                VALUES (?, 1, ?)
                ON CONFLICT(strategy_name) DO UPDATE SET
                    signals_sent = signals_sent + 1,
                    last_update = excluded.last_update
            """, (strategy_name, datetime.now().isoformat()))
            conn.commit()

    def get_stats(self, strategy_name):
        """ბოტი ამას გამოიძახებს ლოგებისთვის"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.execute(
                "SELECT signals_sent FROM strategy_stats WHERE strategy_name = ?", 
                (strategy_name,)
            )
            row = cursor.fetchone()
            return {"signals_sent": row[0] if row else 0}