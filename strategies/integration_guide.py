"""
Analytics System Integration Guide
===================================
როგორ მივაერთოთ analytics_system.py შენს ბოტს
"""

# ════════════════════════════════════════════════════════════════
# STEP 1: IMPORT ANALYTICS SYSTEM
# ════════════════════════════════════════════════════════════════

# trading_engine.py-ში (ან სადაც გაქვს main bot):

from analytics_system import AnalyticsDatabase, AnalyticsDashboard

# Initialize
analytics_db = AnalyticsDatabase("trading_analytics.db")
dashboard = AnalyticsDashboard(analytics_db)


# ════════════════════════════════════════════════════════════════
# STEP 2: RECORD SIGNALS WHEN SENT
# ════════════════════════════════════════════════════════════════

# როდესაც სიგნალს აგზავნი Telegram-ში:

def send_signal_to_telegram(signal):
    """
    სიგნალის გაგზავნა Telegram-ში
    """
    # ✅ BEFORE: გაგზავნე Telegram-ში
    message = format_signal_message(signal)
    bot.send_message(ADMIN_CHAT_ID, message)

    # ✅ NEW: ჩაწერე analytics ბაზაში
    signal_id = analytics_db.record_signal(signal)

    # შეინახე signal_id რომ შემდეგ tracking-ისთვის გამოიყენო
    # (შეგიძლია დაამატო Position ობიექტში ან რომელიმე tracking dict-ში)
    active_signals[signal.symbol] = {
        'signal_id': signal_id,
        'entry_price': signal.entry_price,
        'target_price': signal.target_price,
        'stop_loss': signal.stop_loss_price,
        'strategy': signal.strategy_type.value
    }


# ════════════════════════════════════════════════════════════════
# STEP 3: UPDATE PRICE HISTORY (DURING SCANS)
# ════════════════════════════════════════════════════════════════

# სკანირების დროს, თითოეული აქტიური სიგნალისთვის:

def update_active_signals(current_prices: Dict[str, float]):
    """
    აქტიური სიგნალების განახლება
    """
    for symbol, sig_data in active_signals.items():
        if symbol not in current_prices:
            continue

        current_price = current_prices[symbol]
        signal_id = sig_data['signal_id']

        # ✅ Record price update
        analytics_db.record_price_update(
            signal_id=signal_id,
            symbol=symbol,
            current_price=current_price,
            entry_price=sig_data['entry_price'],
            target_price=sig_data['target_price'],
            stop_loss=sig_data['stop_loss']
        )

        # ✅ Check if target/stop hit
        profit_pct = ((current_price - sig_data['entry_price']) / sig_data['entry_price']) * 100

        if current_price >= sig_data['target_price']:
            # TARGET HIT! 🎯
            analytics_db.record_performance(
                signal_id=signal_id,
                outcome='SUCCESS',
                final_profit_pct=profit_pct,
                exit_reason='TARGET_HIT'
            )

            # Send notification
            bot.send_message(
                ADMIN_CHAT_ID,
                f"🎯 TARGET HIT!\n{symbol}: {profit_pct:+.2f}%"
            )

            # Remove from active
            del active_signals[symbol]

        elif current_price <= sig_data['stop_loss']:
            # STOP LOSS HIT 😢
            analytics_db.record_performance(
                signal_id=signal_id,
                outcome='FAILURE',
                final_profit_pct=profit_pct,
                exit_reason='STOP_LOSS'
            )

            # Send notification
            bot.send_message(
                ADMIN_CHAT_ID,
                f"🛑 Stop Loss Hit\n{symbol}: {profit_pct:+.2f}%"
            )

            # Remove from active
            del active_signals[symbol]


# ════════════════════════════════════════════════════════════════
# STEP 4: TELEGRAM COMMANDS FOR VIEWING STATS
# ════════════════════════════════════════════════════════════════

@bot.message_handler(commands=['stats'])
def show_stats(message):
    """
    /stats - სრული analytics dashboard
    """
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ მხოლოდ ადმინისთვის!")
        return

    dashboard_text = dashboard.generate_text_dashboard()
    bot.reply_to(message, dashboard_text, parse_mode='Markdown')


@bot.message_handler(commands=['active'])
def show_active(message):
    """
    /active - აქტიური სიგნალები
    """
    if message.from_user.id != ADMIN_ID:
        return

    active = analytics_db.get_active_signals()

    if not active:
        bot.reply_to(message, "📭 არ არის აქტიური სიგნალები")
        return

    text = "📊 **ACTIVE SIGNALS:**\n\n"

    for sig in active:
        text += f"**{sig['symbol']}** ({sig['strategy']})\n"
        text += f"Entry: ${sig['entry_price']:.4f}\n"
        text += f"Target: ${sig['target_price']:.4f}\n"
        text += f"Confidence: {sig['confidence']:.0f}%\n\n"

    bot.reply_to(message, text, parse_mode='Markdown')


@bot.message_handler(commands=['history'])
def show_history(message):
    """
    /history SYMBOL - კონკრეტული აქტივის ისტორია
    """
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /history SYMBOL")
        return

    symbol = parts[1].upper()
    history = analytics_db.get_symbol_history(symbol)

    text = f"📜 **{symbol} HISTORY:**\n\n"
    text += f"Total Signals: {history['total_signals']}\n"
    text += f"Wins: {history['wins']}\n"
    text += f"Win Rate: {history['win_rate']:.1f}%\n"
    text += f"Avg Profit: {history['avg_profit']:+.2f}%\n"

    bot.reply_to(message, text, parse_mode='Markdown')


@bot.message_handler(commands=['performance'])
def show_performance(message):
    """
    /performance - სტრატეგიების შედარება
    """
    if message.from_user.id != ADMIN_ID:
        return

    text = "🎯 **STRATEGY PERFORMANCE:**\n\n"

    for strategy in ['long_term', 'scalping', 'opportunistic']:
        perf = analytics_db.get_strategy_performance(strategy)

        if perf['total_signals'] == 0:
            continue

        text += f"**{strategy.upper()}:**\n"
        text += f"• Win Rate: {perf['success_rate']:.1f}%\n"
        text += f"• Avg Profit: {perf['avg_profit']:+.2f}%\n"
        text += f"• Total Signals: {perf['total_signals']}\n\n"

    bot.reply_to(message, text, parse_mode='Markdown')


# ════════════════════════════════════════════════════════════════
# STEP 5: PERIODIC DASHBOARD LOGGING
# ════════════════════════════════════════════════════════════════

# Trading Engine-ის scan ციკლში:

def scan_cycle():
    """
    მთავარი სკანირების ციკლი
    """
    # ... არსებული scan logic ...

    # ✅ Print dashboard to console every 10 scans
    if scan_count % 10 == 0:
        dashboard.generate_console_dashboard()


# ════════════════════════════════════════════════════════════════
# STEP 6: EXPORT TO CSV (OPTIONAL)
# ════════════════════════════════════════════════════════════════

def export_analytics_to_csv():
    """
    Analytics export Excel/CSV-ში
    """
    import pandas as pd
    import sqlite3

    conn = sqlite3.connect("trading_analytics.db")

    # Export signals
    signals_df = pd.read_sql_query("SELECT * FROM signals", conn)
    signals_df.to_csv("signals_export.csv", index=False)

    # Export performance
    perf_df = pd.read_sql_query("SELECT * FROM performance", conn)
    perf_df.to_csv("performance_export.csv", index=False)

    # Export price history
    prices_df = pd.read_sql_query("SELECT * FROM price_history", conn)
    prices_df.to_csv("price_history_export.csv", index=False)

    conn.close()

    logger.info("✅ Analytics exported to CSV")


# Telegram command
@bot.message_handler(commands=['export'])
def export_command(message):
    """
    /export - CSV export
    """
    if message.from_user.id != ADMIN_ID:
        return

    export_analytics_to_csv()

    # Send files
    bot.send_document(message.chat.id, open('signals_export.csv', 'rb'))
    bot.send_document(message.chat.id, open('performance_export.csv', 'rb'))
    bot.send_document(message.chat.id, open('price_history_export.csv', 'rb'))


# ════════════════════════════════════════════════════════════════
# EXAMPLE: FULL INTEGRATION IN MAIN BOT
# ════════════════════════════════════════════════════════════════

"""
# trading_engine.py

from analytics_system import AnalyticsDatabase, AnalyticsDashboard

class TradingEngine:
    def __init__(self):
        # ... existing init ...

        # ✅ Analytics
        self.analytics_db = AnalyticsDatabase()
        self.dashboard = AnalyticsDashboard(self.analytics_db)
        self.active_signals = {}  # symbol → signal_data

    def process_signal(self, signal):
        # Send to Telegram
        self.send_telegram_notification(signal)

        # ✅ Record in analytics
        signal_id = self.analytics_db.record_signal(signal)

        # Track
        self.active_signals[signal.symbol] = {
            'signal_id': signal_id,
            'entry_price': signal.entry_price,
            'target_price': signal.target_price,
            'stop_loss': signal.stop_loss_price
        }

    def scan_cycle(self):
        # ... scan logic ...

        # ✅ Update active signals
        for symbol, data in list(self.active_signals.items()):
            current_price = self.get_current_price(symbol)

            self.analytics_db.record_price_update(
                signal_id=data['signal_id'],
                symbol=symbol,
                current_price=current_price,
                entry_price=data['entry_price'],
                target_price=data['target_price'],
                stop_loss=data['stop_loss']
            )

            # Check exit conditions
            profit_pct = ((current_price - data['entry_price']) / data['entry_price']) * 100

            if current_price >= data['target_price']:
                self.analytics_db.record_performance(
                    signal_id=data['signal_id'],
                    outcome='SUCCESS',
                    final_profit_pct=profit_pct,
                    exit_reason='TARGET_HIT'
                )
                del self.active_signals[symbol]

            elif current_price <= data['stop_loss']:
                self.analytics_db.record_performance(
                    signal_id=data['signal_id'],
                    outcome='FAILURE',
                    final_profit_pct=profit_pct,
                    exit_reason='STOP_LOSS'
                )
                del self.active_signals[symbol]
"""