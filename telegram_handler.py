"""
═══════════════════════════════════════════════════════════════════════════════
TELEGRAM HANDLER v3.0 - SAFE MARKDOWN VERSION
═══════════════════════════════════════════════════════════════════════════════

✅ Fixed:
- All markdown parsing errors
- Safe text formatting
- No asterisks/backticks issues
"""

import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, 
    filters, CallbackQueryHandler
)

from config import *
from analytics_system import AnalyticsDatabase, AnalyticsDashboard
from exit_signals_handler import ExitSignalsHandler
from position_monitor import PositionMonitor
from sell_signal_message_generator import SellSignalMessageGenerator
from signal_history_db import SignalHistoryDB, SentSignal, SignalResult, SignalStatus

try:
    from signal_memory import SignalMemory
    MEMORY_AVAILABLE = True
except Exception:
    MEMORY_AVAILABLE = False

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# HELPER: Safe text formatting
# ═══════════════════════════════════════════════════════════════════════════

def safe_text(text: str) -> str:
    """Remove problematic markdown characters"""
    return text.replace('**', '').replace('`', '').replace('_', '')

# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

WELCOME_MSG_TEMPLATE = """Welcome to AI Trading Bot!

Hello {username}!

Our Service:
- 56 Crypto Monitoring 24/7
- AI Risk Evaluator Active
- 4 Professional Strategies
- Seamless Payments

Price: 150₾ / month

Get Started: /subscribe
Learn: /guide
"""

TIER_DESCRIPTIONS = """TIER DESCRIPTIONS

TIER 1: BLUE CHIP
- BTC, ETH, SOL, BNB
- High Liquidity
- Low Volatility
- Stable Trading

TIER 2: HIGH GROWTH
- AVAX, LINK, POLKADOT, etc
- Medium Liquidity
- Medium Volatility

TIER 3: MEME COINS
- DOGE, SHIB, PEPE, etc
- Hot, Fast
- High Risk, High Reward

TIER 4: NARRATIVE
- AI tokens, DeFi, Layer2
- Development
- Medium Risk

TIER 5: EMERGING
- New Projects
- Ultimate Risk
- Ultimate Upside
"""

PAYMENT_INSTRUCTIONS = """PAYMENT INSTRUCTIONS

Access: 150₾ / month

Payment Methods:

1. TBC Bank Transfer
   Recipient: [NAME]
   Account: [ACCOUNT]
   Reference: Your user_id

2. UNISTREAM
   Number: [NUMBER]
   Message: Your user_id

3. BOG / USDT
   Send BOG/USDT
   Reference: Your user_id

After Payment:
1. Take photo of proof
2. Upload photo here
3. Admin confirms (1-24 hours)

Then:
- Premium Active 30 days
- AI Signals On
- Analytics Access

Questions? Contact @support
"""

GUIDE_FOOTER = (
    "\n\nRemember: DYOR (Do Your Own Research)\n"
    "Risk Disclaimer: Not financial advice\n"
    "Tip: Always use stop-loss!\n"
)

# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM HANDLER v3.0 SAFE
# ═══════════════════════════════════════════════════════════════════════════

class TelegramHandler:
    """TELEGRAM HANDLER v3.0 - SAFE VERSION"""

    def __init__(self, trading_engine):
        logger.info("Telegram Handler v3.0 initializing...")

        self.trading_engine = trading_engine
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.bot = self.application.bot

        self.subscriptions_file = "subscriptions.json"
        self.payment_requests_file = "payment_requests.json"

        self.subscriptions = self._load_json(self.subscriptions_file)
        self.payment_requests = self._load_json(self.payment_requests_file)
        self.last_notifications = {}

        self.analytics_db = AnalyticsDatabase("trading_analytics.db")
        self.dashboard = AnalyticsDashboard(self.analytics_db)

        self.exit_handler = trading_engine.exit_handler
        self.position_monitor = None
        self.signal_history_db = SignalHistoryDB("signal_history.db")

        # Signal Memory
        self.signal_memory = None
        if MEMORY_AVAILABLE:
            try:
                self.signal_memory = SignalMemory()
            except Exception:
                pass

        self._is_running = False
        self._start_lock = asyncio.Lock()

        self._setup_handlers()
        logger.info("Telegram Handler v3.0 ready")

    # ═══════════════════════════════════════════════════════════════════════
    # FILE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def _load_json(self, filename: str) -> Dict:
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if filename == self.subscriptions_file:
                        return {int(k): v for k, v in data.items()}
                    return data
            return {}
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return {}

    def _save_json(self, data: Dict, filename: str):
        try:
            temp_data = data
            if filename == self.subscriptions_file:
                temp_data = {str(k): v for k, v in data.items()}

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(temp_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def is_subscriber(self, user_id: int) -> bool:
        if user_id not in self.subscriptions:
            return False

        expires_str = self.subscriptions[user_id].get('expires_at')
        if not expires_str:
            return False

        try:
            expires = datetime.strptime(expires_str, '%Y-%m-%d').date()
            return datetime.now().date() <= expires
        except:
            return False

    def add_subscription(self, user_id: int, days: int = 30) -> bool:
        expires = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        self.subscriptions[user_id] = {
            'expires_at': expires,
            'activated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'plan': 'premium',
            'days': days
        }
        self._save_json(self.subscriptions, self.subscriptions_file)
        logger.info(f"User {user_id} subscribed for {days} days")
        return True

    def remove_subscription(self, user_id: int) -> bool:
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
            self._save_json(self.subscriptions, self.subscriptions_file)
            logger.info(f"User {user_id} subscription removed")
            return True
        return False

    def get_active_subscribers(self) -> List[int]:
        return [uid for uid in self.subscriptions.keys() if self.is_subscriber(uid)]

    def get_subscriber_info(self, user_id: int) -> Optional[Dict]:
        if user_id in self.subscriptions:
            return self.subscriptions[user_id]
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # USER COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.effective_user.username or "friend"
        message = WELCOME_MSG_TEMPLATE.format(username=username)
        message += "\n\n/results — ბოლო 20 სიგნალის შედეგები"
        await update.message.reply_text(message)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """Help

User Commands:
/start - Begin
/guide - RSI/EMA explanation
/tiers - Tier descriptions
/mystatus - Your subscription
/subscribe - Premium activation

Admin Commands:
/admin - Admin panel
/stats - Analytics
/signals - Signal history
/dashboard - Full report
"""
        await update.message.reply_text(help_text)

    async def cmd_guide(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        guide_text = """AI Trading Guide

RSI (Relative Strength Index)
- <30 = Oversold (Buy signal)
- 30-70 = Normal
- >70 = Overbought (Sell signal)

EMA 200 (Exponential Moving Average)
- Price > EMA200 = Uptrend
- Price < EMA200 = Downtrend
- Long-term trend indicator

Bollinger Bands (BB)
- BB Low touch = Possible bounce
- BB High touch = Possible decline
- Volatility measure

MACD (Moving Average Convergence)
- Histogram > 0 = Uptrend momentum
- Histogram < 0 = Downtrend momentum
- Crossover = Trend change

Stop-Loss & Take-Profit
- Stop-Loss = Limit losses
- Take-Profit = Lock in gains
- Always use!

AI Score
- 0-30: Weak
- 30-45: Medium
- 45-65: Good
- 65+: Strong
"""
        await update.message.reply_text(guide_text)

    async def cmd_tiers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(TIER_DESCRIPTIONS)

    async def cmd_mystatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        sub = self.get_subscriber_info(user_id)

        if sub and self.is_subscriber(user_id):
            expires = sub['expires_at']
            activated = sub.get('activated_at', 'N/A')
            expires_date = datetime.strptime(expires, '%Y-%m-%d').date()
            days_left = (expires_date - datetime.now().date()).days

            status_msg = (
                f"Status: Premium Active\n\n"
                f"Activated: {activated}\n"
                f"Expires: {expires}\n"
                f"Days left: {days_left}\n\n"
                f"Signals: Active\n"
                f"Notifications: On"
            )
        else:
            status_msg = (
                "No Active Subscription\n\n"
                "Price: 150₾ / month\n\n"
                "Get premium: /subscribe"
            )

        await update.message.reply_text(status_msg)

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(PAYMENT_INSTRUCTIONS)

    # ═══════════════════════════════════════════════════════════════════════
    # ADMIN COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("Unauthorized")
            return

        admin_msg = """Admin Panel v3.0

User Management:
/adduser [id] [days] - Add subscription
/removeuser [id] - Remove subscription
/listusers - List all users
/botstats - Bot statistics

Signal History:
/signals - Recent 20 signals
/signalstats - Overall stats
/symbolstats [SYM] - Symbol stats
/strategystats [STR] - Strategy stats
/dashboard - Full dashboard

Position Monitoring:
/openpositions - Active positions
/closedpositions - Closed trades
/exitstats - Exit statistics
/enginestatus - Engine status

Analytics:
/stats - Analytics dashboard
/active - Active signals
/performance - Strategy performance
/history [SYM] - Symbol history
/recent [N] - Recent signals
"""
        await update.message.reply_text(admin_msg)

    async def cmd_adduser(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            user_id = int(context.args[0])
            days = int(context.args[1]) if len(context.args) > 1 else 30

            self.add_subscription(user_id, days)

            await update.message.reply_text(
                f"User {user_id} activated for {days} days"
            )

            try:
                await self.bot.send_message(
                    user_id,
                    f"Premium Activated!\n\n"
                    f"Valid for {days} days\n"
                    f"Signals: Active\n"
                    f"Get Started: /guide"
                )
            except:
                pass

        except (IndexError, ValueError):
            await update.message.reply_text("Usage: /adduser [user_id] [days]")

    async def cmd_removeuser(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            user_id = int(context.args[0])
            if self.remove_subscription(user_id):
                await update.message.reply_text(f"User {user_id} removed")
            else:
                await update.message.reply_text(f"User {user_id} not found")

        except (IndexError, ValueError):
            await update.message.reply_text("Usage: /removeuser [user_id]")

    async def cmd_listusers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        active = self.get_active_subscribers()
        inactive = [uid for uid in self.subscriptions.keys() if uid not in active]

        msg = (
            f"Users\n\n"
            f"Active: {len(active)}\n"
            f"Inactive: {len(inactive)}\n"
            f"Total: {len(self.subscriptions)}\n\n"
        )

        if active:
            msg += "Active Users:\n"
            for uid in active[:15]:
                info = self.subscriptions[uid]
                expires = info['expires_at']
                msg += f"{uid} - {expires}\n"

        await update.message.reply_text(msg)

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        stats = getattr(self.trading_engine, 'stats', {})

        msg = (
            f"Bot Statistics\n\n"
            f"Users:\n"
            f"Total: {len(self.subscriptions)}\n"
            f"Active: {len(self.get_active_subscribers())}\n\n"
            f"Signals:\n"
            f"Sent: {stats.get('total_signals', 0)}\n"
            f"AI Approved: {stats.get('ai_approved', 0)}\n"
            f"AI Rejected: {stats.get('ai_rejected', 0)}\n\n"
            f"System:\n"
            f"Cryptos: {len(CRYPTO)}\n"
            f"Strategies: 4\n"
            f"AI: {'Active' if AI_RISK_ENABLED else 'Inactive'}"
        )
        await update.message.reply_text(msg)

    # ═══════════════════════════════════════════════════════════════════════
    # ANALYTICS COMMANDS (SAFE TEXT)
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("Unauthorized")
            return

        try:
            dashboard_text = self.dashboard.generate_text_dashboard()
            safe = safe_text(dashboard_text)
            await update.message.reply_text(safe)
        except Exception as e:
            logger.error(f"Error /stats: {e}")
            await update.message.reply_text(f"Error: {str(e)[:100]}")

    async def cmd_active(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            active_signals = self.analytics_db.get_active_signals()

            if not active_signals:
                await update.message.reply_text("No active signals")
                return

            text = "Active Signals:\n\n"
            for sig in active_signals[:10]:
                text += f"{sig['symbol']} ({sig['strategy']})\n"
                text += f"Entry: ${sig['entry_price']:.4f}\n"
                text += f"Target: ${sig['target_price']:.4f}\n"
                text += f"Stop: ${sig['stop_loss']:.4f}\n"
                text += f"Conf: {sig['confidence']:.0f}%\n\n"

            await update.message.reply_text(safe_text(text))

        except Exception as e:
            logger.error(f"Error /active: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            text = "Strategy Performance:\n\n"

            for strategy in ['long_term', 'scalping', 'opportunistic', 'swing']:
                perf = self.analytics_db.get_strategy_performance(strategy)

                if perf['total_signals'] == 0:
                    text += f"{strategy}: No data\n\n"
                    continue

                text += f"{strategy.upper()}\n"
                text += f"Signals: {perf['total_signals']}\n"
                text += f"Win: {perf['success_rate']:.1f}%\n"
                text += f"Avg: {perf['avg_profit']:+.2f}%\n"
                text += f"Best: {perf['best_trade']:+.2f}%\n\n"

            await update.message.reply_text(safe_text(text))

        except Exception as e:
            logger.error(f"Error /performance: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        if not context.args:
            await update.message.reply_text("Usage: /history SYMBOL\n\nEx: /history BTCUSDT")
            return

        try:
            symbol = context.args[0].upper()
            history = self.analytics_db.get_symbol_history(symbol)

            if history['total_signals'] == 0:
                await update.message.reply_text(f"{symbol} - No history")
                return

            text = f"{symbol}\n\n"
            text += f"Signals: {history['total_signals']}\n"
            text += f"Win Rate: {history['win_rate']:.1f}%\n"
            text += f"Avg: {history['avg_profit']:+.2f}%\n"
            text += f"Best: {history['best_trade']:+.2f}%\n"

            await update.message.reply_text(safe_text(text))

        except Exception as e:
            logger.error(f"Error /history: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_recent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            limit = 10
            if context.args:
                try:
                    limit = int(context.args[0])
                    limit = min(max(limit, 1), 20)
                except:
                    pass

            recent = self.analytics_db.get_recent_signals(limit)

            if not recent:
                await update.message.reply_text("No signals")
                return

            text = f"Recent {len(recent)}:\n\n"

            for sig in recent:
                emoji = "+" if sig['outcome'] == 'SUCCESS' else "-" if sig['outcome'] == 'FAILURE' else "?"
                profit_str = f"{sig['profit']:+.2f}%" if sig['profit'] is not None else "Pending"

                text += f"{emoji} {sig['symbol']} ({sig['strategy']})\n"
                text += f"   {profit_str} | {sig['confidence']:.0f}%\n"

            await update.message.reply_text(safe_text(text))

        except Exception as e:
            logger.error(f"Error /recent: {e}")
            await update.message.reply_text(f"Error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MONITORING COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_openpositions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            if not self.position_monitor:
                await update.message.reply_text("Position Monitor not ready")
                return

            status_report = self.position_monitor.get_position_status_report()
            await update.message.reply_text(safe_text(status_report))

        except Exception as e:
            logger.error(f"Error /openpositions: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_closedpositions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            if not self.position_monitor:
                await update.message.reply_text("Position Monitor not ready")
                return

            summary = self.position_monitor.get_closed_positions_summary()
            await update.message.reply_text(safe_text(summary))

        except Exception as e:
            logger.error(f"Error /closedpositions: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_exitstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            exit_stats = self.exit_handler.get_exit_statistics()

            text = "Exit Statistics:\n\n"
            text += f"Total Exits: {exit_stats['total_exits']}\n"
            text += f"Wins: {exit_stats['successful']}\n"
            text += f"Losses: {exit_stats['failed']}\n"
            text += f"Win Rate: {exit_stats.get('win_rate', 0):.1f}%\n\n"
            text += f"Avg Profit: {exit_stats['avg_profit']:+.2f}%\n"
            text += f"Best: {exit_stats['best_trade']:+.2f}%\n"
            text += f"Worst: {exit_stats['worst_trade']:+.2f}%\n"

            await update.message.reply_text(safe_text(text))

        except Exception as e:
            logger.error(f"Error /exitstats: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_enginestatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            status = self.trading_engine.get_engine_status()
            await update.message.reply_text(safe_text(status))

        except Exception as e:
            logger.error(f"Error /enginestatus: {e}")
            await update.message.reply_text(f"Error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL HISTORY COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            recent = self.signal_history_db.get_recent_signals(limit=20)

            if not recent:
                await update.message.reply_text("No signals")
                return

            text = "Recent 20:\n\n"

            for sig in recent:
                emoji = "+" if sig['status'] == 'win' else "-" if sig['status'] == 'loss' else "?"
                profit_str = f"{sig['profit_pct']:+.2f}%" if sig['profit_pct'] else "Pending"

                text += f"{emoji} {sig['symbol']} ({sig['strategy']})\n"
                text += f"Entry: ${sig['entry_price']:.4f}\n"
                text += f"P&L: {profit_str}\n"
                text += f"Hold: {sig['days_held']:.1f}d\n"
                text += f"Conf: {sig['confidence_score']:.0f}%\n\n"

            await update.message.reply_text(safe_text(text))

        except Exception as e:
            logger.error(f"Error /signals: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_signalstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            stats = self.signal_history_db.get_overall_stats()

            text = "Signal Statistics\n\n"
            text += "Sent:\n"
            text += f"Total: {stats['total_signals_sent']}\n"
            text += f"Closed: {stats['total_signals_closed']}\n"
            text += f"Pending: {stats['pending']}\n\n"

            text += "Results:\n"
            text += f"Win Rate: {stats['win_rate']:.1f}%\n"
            text += f"Wins: {stats['wins']}\n"
            text += f"Losses: {stats['total_signals_closed'] - stats['wins']}\n\n"

            text += "Financial:\n"
            text += f"Avg: {stats['avg_profit_pct']:+.2f}%\n"
            text += f"Total: {stats['total_profit_pct']:+.2f}%\n"

            await update.message.reply_text(safe_text(text))

        except Exception as e:
            logger.error(f"Error /signalstats: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_symbolstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        if not context.args:
            await update.message.reply_text("Usage: /symbolstats SYMBOL\n\nEx: /symbolstats BTC/USD")
            return

        try:
            symbol = context.args[0].upper()
            stats = self.signal_history_db.get_symbol_history(symbol)

            if stats['total_signals'] == 0:
                await update.message.reply_text(f"{symbol} - No signals")
                return

            text = f"{symbol}\n\n"
            text += f"Signals: {stats['total_signals']}\n"
            text += f"Win Rate: {stats['win_rate']:.1f}%\n"
            text += f"Wins: {stats['wins']}\n\n"

            text += "Financial:\n"
            text += f"Avg: {stats['avg_profit']:+.2f}%\n"
            text += f"Best: {stats['best_trade']:+.2f}%\n"
            text += f"Worst: {stats['worst_trade']:+.2f}%\n"
            text += f"Total: {stats['total_profit']:+.2f}%\n"

            await update.message.reply_text(safe_text(text))

        except Exception as e:
            logger.error(f"Error /symbolstats: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_strategystats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        if not context.args:
            strategies = ["long_term", "swing", "scalping", "opportunistic"]
            msg = "Usage: /strategystats STRATEGY\n\nStrategies:\n"
            for s in strategies:
                msg += f"{s}\n"
            await update.message.reply_text(msg)
            return

        try:
            strategy = context.args[0].lower()
            stats = self.signal_history_db.get_strategy_performance(strategy)

            if stats['total_signals'] == 0:
                await update.message.reply_text(f"{strategy} - No signals")
                return

            text = f"{strategy.upper()}\n\n"
            text += f"Signals: {stats['total_signals']}\n"
            text += f"Win Rate: {stats['win_rate']:.1f}%\n"
            text += f"Wins: {stats['wins']}\n\n"

            text += "Financial:\n"
            text += f"Avg: {stats['avg_profit_pct']:+.2f}%\n"
            text += f"Avg Days: {stats['avg_days_held']:.1f}\n"

            await update.message.reply_text(safe_text(text))

        except Exception as e:
            logger.error(f"Error /strategystats: {e}")
            await update.message.reply_text(f"Error: {e}")

    async def cmd_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            report = self.signal_history_db.generate_report()
            await update.message.reply_text(safe_text(report))

        except Exception as e:
            logger.error(f"Error /dashboard: {e}")
            await update.message.reply_text(f"Error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # PAYMENT HANDLING
    # ═══════════════════════════════════════════════════════════════════════

    async def handle_payment_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "User"

        photo_id = update.message.photo[-1].file_id
        self.payment_requests[str(user_id)] = {
            'username': username,
            'status': 'pending',
            'photo_id': photo_id,
            'time': datetime.now().isoformat()
        }
        self._save_json(self.payment_requests, self.payment_requests_file)

        await update.message.reply_text(
            "Payment received!\n\n"
            "Awaiting admin approval (1-24 hours)"
        )

        keyboard = [[
            InlineKeyboardButton("Approve", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("Reject", callback_data=f"reject_{user_id}")
        ]]

        await self.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=f"Payment\n\nUser @{username} ({user_id})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query

        if update.effective_user.id != ADMIN_ID:
            await query.answer("Unauthorized")
            return

        action, target_id = query.data.split("_")
        target_id = int(target_id)

        if action == "approve":
            self.add_subscription(target_id, days=30)

            await query.edit_message_caption(
                caption=f"Approved\n\nUser: {target_id}"
            )

            try:
                await self.bot.send_message(
                    target_id,
                    "Payment Approved!\n\n"
                    "Premium activated for 30 days\n"
                    "Signals: Active\n\n"
                    "Get Started: /guide"
                )
            except:
                pass

        else:
            await query.edit_message_caption(
                caption=f"Rejected\n\nUser: {target_id}"
            )

            try:
                await self.bot.send_message(
                    target_id,
                    "Payment Rejected\n\n"
                    "Please contact support"
                )
            except:
                pass

        await query.answer()

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL BROADCASTING
    # ═══════════════════════════════════════════════════════════════════════

    async def broadcast_signal(self, message: str, asset: str):
        full_message = message + GUIDE_FOOTER
        active_users = self.get_active_subscribers()

        logger.info(f"Broadcasting to {len(active_users)} users: {asset}")

        success = 0
        failed = 0

        for user_id in active_users:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=full_message
                )
                success += 1
                await asyncio.sleep(0.05)

            except Exception as e:
                failed += 1
                logger.debug(f"Send failed {user_id}: {e}")

        logger.info(f"Broadcast complete: {success} OK, {failed} FAILED")

    # ═══════════════════════════════════════════════════════════════════════
    # HANDLERS SETUP
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ბოლო 20 სიგნალის შედეგები — ყველა user-ისთვის ხელმისაწვდომი"""
        try:
            recent = self.signal_history_db.get_recent_signals(limit=20)

            if not recent:
                await update.message.reply_text(
                    "📊 სიგნალების ისტორია\n\nჯერ არ არის დახურული სიგნალები.\n"
                    "ბოტი იწყებს ჩაწერას პირველი trade-დან."
                )
                return

            # Header
            lines = ["📊 ბოლო 20 სიგნალი\n"]

            closed = [s for s in recent if s.get("status") in ("win", "loss")]
            pending = [s for s in recent if s.get("status") not in ("win", "loss")]

            wins = sum(1 for s in closed if s.get("status") == "win" or (s.get("profit_pct") or 0) > 0)
            total_closed = len(closed)
            win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

            if total_closed > 0:
                avg_profit = sum(s["profit_pct"] for s in closed) / total_closed
                lines.append(
                    f"✅ {wins}W / ❌ {total_closed - wins}L  |  Win rate: {win_rate:.0f}%"
                )
                lines.append(f"Avg: {avg_profit:+.1f}%  |  Pending: {len(pending)}\n")
            lines.append("━━━━━━━━━━━━━━━━━━━━")

            for sig in recent:
                symbol   = sig.get("symbol", "?")
                strategy = sig.get("strategy", "?")
                sent_at  = sig.get("sent_time", "")
                profit   = sig.get("profit_pct")
                status   = sig.get("status")

                # Format time
                try:
                    dt = datetime.fromisoformat(sent_at)
                    time_str = dt.strftime("%d %b %H:%M")
                except Exception:
                    time_str = sent_at[:16] if sent_at else "?"

                # 100$ simulation
                status_val = sig.get("status")
                if profit is not None and status_val in ("win", "loss"):
                    sim_val  = 100 * (1 + profit / 100)
                    sim_diff = sim_val - 100
                    sim_str  = f"${sim_val:.1f} ({sim_diff:+.1f}$)"
                    result_emoji = "🟢" if profit > 0 else "🔴"
                    profit_str = f"{profit:+.2f}%  {sim_str}"
                else:
                    result_emoji = "🟡"
                    profit_str   = "HOLD..."

                lines.append(
                    f"{result_emoji} {symbol}  {time_str}\n"
                    f"   {profit_str}"
                )

            lines.append("\n━━━━━━━━━━━━━━━━━━━━")
            lines.append("🟢 მოგება  🔴 ზარალი  🟡 HOLD")
            lines.append("\n⚠️ წარსული შედეგი არ გარანტიას ძლევს")

            text = "\n".join(lines)

            # Telegram 4096 char limit
            if len(text) > 4000:
                text = text[:4000] + "\n... (truncated)"

            await update.message.reply_text(text)

        except Exception as e:
            logger.error(f"cmd_results error: {e}")
            await update.message.reply_text("⚠️ ისტორია დროებით მიუწვდომელია")

    def _setup_handlers(self):
        # User commands
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("results", self.cmd_results))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("guide", self.cmd_guide))
        self.application.add_handler(CommandHandler("tiers", self.cmd_tiers))
        self.application.add_handler(CommandHandler("mystatus", self.cmd_mystatus))
        self.application.add_handler(CommandHandler("subscribe", self.cmd_subscribe))

        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.cmd_admin))
        self.application.add_handler(CommandHandler("adduser", self.cmd_adduser))
        self.application.add_handler(CommandHandler("removeuser", self.cmd_removeuser))
        self.application.add_handler(CommandHandler("listusers", self.cmd_listusers))
        self.application.add_handler(CommandHandler("botstats", self.cmd_botstats))

        # Analytics commands
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("active", self.cmd_active))
        self.application.add_handler(CommandHandler("performance", self.cmd_performance))
        self.application.add_handler(CommandHandler("history", self.cmd_history))
        self.application.add_handler(CommandHandler("recent", self.cmd_recent))

        # Position monitoring commands
        self.application.add_handler(CommandHandler("openpositions", self.cmd_openpositions))
        self.application.add_handler(CommandHandler("closedpositions", self.cmd_closedpositions))
        self.application.add_handler(CommandHandler("exitstats", self.cmd_exitstats))
        self.application.add_handler(CommandHandler("enginestatus", self.cmd_enginestatus))

        # Signal history commands
        self.application.add_handler(CommandHandler("signals", self.cmd_signals))
        self.application.add_handler(CommandHandler("signalstats", self.cmd_signalstats))
        self.application.add_handler(CommandHandler("symbolstats", self.cmd_symbolstats))
        self.application.add_handler(CommandHandler("strategystats", self.cmd_strategystats))
        self.application.add_handler(CommandHandler("dashboard", self.cmd_dashboard))

        # Payment handling
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_payment_photo))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    async def start(self):
        async with self._start_lock:
            if self._is_running:
                logger.warning("Bot already running")
                return

            try:
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling(drop_pending_updates=True)

                self._is_running = True
                logger.info("Telegram Bot v3.0 started!")

                self._stop_event = asyncio.Event()
                await self._stop_event.wait()

            except Exception as e:
                logger.error(f"Bot error: {e}")
                self._is_running = False
                raise

    async def stop(self):
        if not self._is_running:
            logger.warning("Bot not running")
            return

        logger.info("Stopping bot...")
        if hasattr(self, '_stop_event'):
            self._stop_event.set()

        try:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        self._is_running = False
        logger.info("Bot stopped")