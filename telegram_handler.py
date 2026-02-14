"""
═══════════════════════════════════════════════════════════════════════════════
TELEGRAM HANDLER v3.0 - COMPLETE PRODUCTION
═══════════════════════════════════════════════════════════════════════════════

✅ ის თავიდან ყველა (ძველი):
- User commands
- Admin commands
- Payment handling
- Analytics
- Broadcasting

✅ ახლის დამატება:
- Exit Handler integration
- Position Monitoring commands
- Signal History Database
- Complete dashboard

AUTHOR: Trading System Architecture Team
DATE: 2024-02-14
VERSION: 3.0
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

# ═══════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════

from config import *
from analytics_system import AnalyticsDatabase, AnalyticsDashboard

# ✅ NEW IMPORTS
from exit_signals_handler import ExitSignalsHandler
from position_monitor import PositionMonitor
from sell_signal_message_generator import SellSignalMessageGenerator
from signal_history_db import SignalHistoryDB, SentSignal, SignalResult, SignalStatus

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

WELCOME_MSG_TEMPLATE = """🎯 **Welcome to AI Trading Bot!**

👋 Hello {username}!

📊 **ჩვენი სერვისი:**
• 🔍 {crypto_count} კრიპტო მონიტორინგი 24/7
• 🧠 {ai_info} AI Risk Evaluator
• 📈 4 პროფესიონალური სტრატეგია
• 💳 დაახლოვებული გადახდა

💰 **ფასი:** 150₾ / თვე

🚀 დაიწყეთ: /subscribe
📖 დაფიქსირება: /guide
"""

TIER_DESCRIPTIONS = """📊 **TIER DESCRIPTIONS**

**TIER 1: BLUE CHIP** 🔵
• BTC, ETH, SOL, BNBUSDT
• მაღალი ლიკვიდობა
• დაბალი ვოლატილობა
• მსუბუქი ტრეიდი

**TIER 2: HIGH GROWTH** 📈
• AVAX, LINK, POLKADOT, etc
• საშუალო ლიკვიდობა
• საშუალო ვოლატილობა

**TIER 3: MEME COINS** 🎪
• DOGE, SHIB, PEPE, etc
• ცხელი, სწრაფი
• მაღალი რისკი, მაღალი რეზიულტატი

**TIER 4: NARRATIVE** 📚
• AI tokens, DeFi, Layer2
• განვითარება
• საშუალო რისკი

**TIER 5: EMERGING** 🌱
• ახალი პროჯექტი
• უმაღლესი რისკი
• უმაღლესი რეზულტატი სიზღვარი
"""

PAYMENT_INSTRUCTIONS = """💳 **PAYMENT INSTRUCTIONS**

**ხელმისაწვდომი:** 150₾ / თვე

📱 **გადახდის გზები:**

1️⃣ **TBC Bank Transfer**
   • Recipient: [NAME]
   • Account: [ACCOUNT]
   • Reference: თქვენი user_id

2️⃣ **UNISTREAM**
   • Number: [NUMBER]
   • Message: თქვენი user_id

3️⃣ **BOG / USDT**
   • Send BOG/USDT
   • Reference: თქვენი user_id

📸 **გადახდის შემდეგ:**
1. გააკეთეთ ფოტო proof-ის
2. გამოუზიდეთ ფოტო აქ
3. ადმინი დადასტურებს (1-24 საათი)

✅ **მერე:**
• Premium აქტივირებული 30 დღით
• AI სიგნალი ჩართული
• Analytics access

❓ **კითხვები?** @support_bot
"""

GUIDE_FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📍 **Remember:** DYOR (Do Your Own Research)\n"
    "⚠️ **Risk Disclaimer:** აქ ფინანსური რჩევა არა\n"
    "💡 **Tip:** ყოველთვის გამოიყენეთ stop-loss!\n"
)

# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM HANDLER v3.0
# ═══════════════════════════════════════════════════════════════════════════

class TelegramHandler:
    """TELEGRAM HANDLER v3.0 - COMPLETE PRODUCTION"""

    def __init__(self, trading_engine):
        logger.info("🚀 TelegramHandler v3.0 initializing...")

        self.trading_engine = trading_engine

        # ════════════════════════════════════════════════════════════════════
        # TELEGRAM APPLICATION
        # ════════════════════════════════════════════════════════════════════

        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.bot = self.application.bot

        # ════════════════════════════════════════════════════════════════════
        # FILE PATHS
        # ════════════════════════════════════════════════════════════════════

        self.subscriptions_file = "subscriptions.json"
        self.payment_requests_file = "payment_requests.json"

        # ════════════════════════════════════════════════════════════════════
        # DATA MANAGEMENT
        # ════════════════════════════════════════════════════════════════════

        self.subscriptions = self._load_json(self.subscriptions_file)
        self.payment_requests = self._load_json(self.payment_requests_file)
        self.last_notifications = {}

        # ════════════════════════════════════════════════════════════════════
        # DATABASES
        # ════════════════════════════════════════════════════════════════════

        self.analytics_db = AnalyticsDatabase("trading_analytics.db")
        self.dashboard = AnalyticsDashboard(self.analytics_db)

        # ✅ NEW: Exit Handler & Databases
        self.exit_handler = trading_engine.exit_handler
        self.position_monitor = None  # დაყენდება run-ის დროს
        self.signal_history_db = SignalHistoryDB("signal_history.db")

        # ════════════════════════════════════════════════════════════════════
        # LIFECYCLE
        # ════════════════════════════════════════════════════════════════════

        self._is_running = False
        self._start_lock = asyncio.Lock()

        # Setup all handlers
        self._setup_handlers()

        logger.info("✅ TelegramHandler v3.0 ready")

    # ═══════════════════════════════════════════════════════════════════════
    # FILE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def _load_json(self, filename: str) -> Dict:
        """JSON ჩატვირთვა"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert string keys to int for subscriptions
                    if filename == self.subscriptions_file:
                        return {int(k): v for k, v in data.items()}
                    return data
            return {}
        except Exception as e:
            logger.error(f"❌ Error loading {filename}: {e}")
            return {}

    def _save_json(self, data: Dict, filename: str):
        """JSON შენახვა"""
        try:
            temp_data = data
            if filename == self.subscriptions_file:
                temp_data = {str(k): v for k, v in data.items()}

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(temp_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Error saving {filename}: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def is_subscriber(self, user_id: int) -> bool:
        """აქტიური საბსქრიფშენი?"""
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
        """საბსქრიფშენ დამატება"""
        expires = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        self.subscriptions[user_id] = {
            'expires_at': expires,
            'activated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'plan': 'premium',
            'days': days
        }
        self._save_json(self.subscriptions, self.subscriptions_file)
        logger.info(f"✅ User {user_id} subscribed for {days} days (expires: {expires})")
        return True

    def remove_subscription(self, user_id: int) -> bool:
        """საბსქრიფშენ მოხსნა"""
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
            self._save_json(self.subscriptions, self.subscriptions_file)
            logger.info(f"✅ User {user_id} subscription removed")
            return True
        return False

    def get_active_subscribers(self) -> List[int]:
        """აქტიური მომხმარებელი"""
        return [uid for uid in self.subscriptions.keys() if self.is_subscriber(uid)]

    def get_subscriber_info(self, user_id: int) -> Optional[Dict]:
        """მომხმარებელი info"""
        if user_id in self.subscriptions:
            return self.subscriptions[user_id]
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # USER COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🌟 /start - მოგესალმო"""
        username = update.effective_user.username or "friend"
        message = WELCOME_MSG_TEMPLATE.format(
            username=username,
            crypto_count=len(CRYPTO),
            ai_info="Active 🧠",
            stocks_count=0,
            commodities_count=0
        )
        await update.message.reply_text(message, parse_mode='Markdown')

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """❓ /help - დახმარება"""
        help_text = (
            "❓ **დახმარება**\n\n"
            "**User Commands:**\n"
            "/start - დაიწყეთ\n"
            "/guide - RSI/EMA განმარტება\n"
            "/tiers - ტიერ აღწერა\n"
            "/mystatus - თქვენი ხელმისაწვდომი\n"
            "/subscribe - Premium აქტივაცია\n\n"
            "**Admin Commands:**\n"
            "/admin - ადმინ პანელი\n"
            "/stats - Analytics\n"
            "/signals - ბოლო signals\n"
            "/dashboard - Dashboard\n"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def cmd_guide(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📖 /guide - სიგნალის განმარტება"""
        guide_text = (
            "📖 **AI Trading Guide**\n\n"

            "**RSI (Relative Strength Index)**\n"
            "• <30 = გადაყიდულია (ყიდვა 📉)\n"
            "• 30-70 = ნორმა\n"
            "• >70 = გადახურებული (გაყიდვა 📈)\n\n"

            "**EMA 200 (Exponential Moving Average)**\n"
            "• ფასი > EMA200 = აღმავალი 📈\n"
            "• ფასი < EMA200 = დაღმავალი 📉\n"
            "• გრძელვადიანი ტრენდი\n\n"

            "**Bollinger Bands (BB)**\n"
            "• BB Low = შესაძლო ასხლეტა 🎯\n"
            "• BB High = შესაძლო დაცემა ⚠️\n"
            "• ვოლატილობის მაჩვენებელი\n\n"

            "**MACD (Moving Average Convergence)**\n"
            "• Histogram > 0 = აღმავალი momentum\n"
            "• Histogram < 0 = დაღმავალი momentum\n"
            "• Crossover = ტრენდ ცვლილება\n\n"

            "**Stop-Loss & Take-Profit**\n"
            "• Stop-Loss = ზარალის შეზღუდვა 🔴\n"
            "• Take-Profit = მოგების ფიქსირება 🟢\n"
            "• ყოველთვის გამოიყენეთ!\n\n"

            "**AI Score**\n"
            "• 0-30: სუსტი ❌\n"
            "• 30-45: საშუალო ⚠️\n"
            "• 45-65: კარგი ✅\n"
            "• 65+: ძლიერი 🔥\n"
        )
        await update.message.reply_text(guide_text, parse_mode='Markdown')

    async def cmd_tiers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /tiers - ტიერ აღწერა"""
        await update.message.reply_text(TIER_DESCRIPTIONS, parse_mode='Markdown')

    async def cmd_mystatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """✅ /mystatus - თქვენი ხელმისაწვდომი"""
        user_id = update.effective_user.id
        sub = self.get_subscriber_info(user_id)

        if sub and self.is_subscriber(user_id):
            expires = sub['expires_at']
            activated = sub.get('activated_at', 'N/A')
            expires_date = datetime.strptime(expires, '%Y-%m-%d').date()
            days_left = (expires_date - datetime.now().date()).days

            status_msg = (
                f"✅ **Premium Active**\n\n"
                f"📅 Activated: `{activated}`\n"
                f"📅 Expires: `{expires}`\n"
                f"⏳ Days left: **{days_left}**\n\n"
                f"📊 Signals: ✅ Active\n"
                f"🔔 Notifications: ✅ On"
            )
        else:
            status_msg = (
                "⚠️ **No Active Subscription**\n\n"
                "💰 Price: 150₾ / month\n\n"
                "Get premium: /subscribe"
            )

        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """💳 /subscribe - გამოწერა"""
        await update.message.reply_text(PAYMENT_INSTRUCTIONS, parse_mode='Markdown')

    # ═══════════════════════════════════════════════════════════════════════
    # ADMIN COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """👑 /admin - ადმინ პანელი"""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Unauthorized")
            return

        admin_msg = (
            "👑 **Admin Panel v3.0**\n\n"

            "**👥 User Management:**\n"
            "/adduser [id] [days] - Add subscription\n"
            "/removeuser [id] - Remove subscription\n"
            "/listusers - List all users\n"
            "/botstats - Bot statistics\n\n"

            "**📊 Signal History:**\n"
            "/signals - Recent 20 signals\n"
            "/signalstats - Overall stats\n"
            "/symbolstats [SYM] - Symbol stats\n"
            "/strategystats [STR] - Strategy stats\n"
            "/dashboard - Full dashboard\n\n"

            "**📍 Position Monitoring:**\n"
            "/openpositions - Active positions\n"
            "/closedpositions - Closed trades\n"
            "/exitstats - Exit statistics\n"
            "/enginestatus - Engine status\n\n"

            "**📈 Analytics:**\n"
            "/stats - Analytics dashboard\n"
            "/active - Active signals\n"
            "/performance - Strategy performance\n"
            "/history [SYM] - Symbol history\n"
            "/recent [N] - Recent signals"
        )
        await update.message.reply_text(admin_msg, parse_mode='Markdown')

    async def cmd_adduser(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """➕ /adduser - მომხმარებელ დამატება"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            user_id = int(context.args[0])
            days = int(context.args[1]) if len(context.args) > 1 else 30

            self.add_subscription(user_id, days)

            await update.message.reply_text(
                f"✅ User `{user_id}` activated for {days} days",
                parse_mode='Markdown'
            )

            # Notify user
            try:
                await self.bot.send_message(
                    user_id,
                    f"🎉 **Premium Activated!**\n\n"
                    f"⏳ Valid for {days} days\n"
                    f"📊 Signals: Active ✅\n"
                    f"🚀 Get Started: /guide"
                )
            except:
                pass

        except (IndexError, ValueError):
            await update.message.reply_text("❌ Usage: /adduser [user_id] [days]")

    async def cmd_removeuser(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """➖ /removeuser - მომხმარებელ მოხსნა"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            user_id = int(context.args[0])
            if self.remove_subscription(user_id):
                await update.message.reply_text(f"✅ User `{user_id}` removed")
            else:
                await update.message.reply_text(f"❌ User `{user_id}` not found")

        except (IndexError, ValueError):
            await update.message.reply_text("❌ Usage: /removeuser [user_id]")

    async def cmd_listusers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📋 /listusers - მომხმარებელი სია"""
        if update.effective_user.id != ADMIN_ID:
            return

        active = self.get_active_subscribers()
        inactive = [uid for uid in self.subscriptions.keys() if uid not in active]

        msg = (
            f"👥 **Users**\n\n"
            f"✅ Active: {len(active)}\n"
            f"❌ Inactive: {len(inactive)}\n"
            f"📊 Total: {len(self.subscriptions)}\n\n"
        )

        if active:
            msg += "**Active Users:**\n"
            for uid in active[:15]:
                info = self.subscriptions[uid]
                expires = info['expires_at']
                msg += f"• `{uid}` - {expires}\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /botstats - ბოტი სტატისტიკა"""
        if update.effective_user.id != ADMIN_ID:
            return

        stats = getattr(self.trading_engine, 'stats', {})

        msg = (
            f"📊 **Bot Statistics**\n\n"
            f"**Users:**\n"
            f"• Total: {len(self.subscriptions)}\n"
            f"• Active: {len(self.get_active_subscribers())}\n\n"

            f"**Signals:**\n"
            f"• Sent: {stats.get('total_signals', 0)}\n"
            f"• AI Approved: {stats.get('ai_approved', 0)}\n"
            f"• AI Rejected: {stats.get('ai_rejected', 0)}\n\n"

            f"**System:**\n"
            f"• Cryptos: {len(CRYPTO)}\n"
            f"• Strategies: 4\n"
            f"• AI: {'Active' if AI_RISK_ENABLED else 'Inactive'}"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    # ═══════════════════════════════════════════════════════════════════════
    # ANALYTICS COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /stats - Analytics Dashboard"""
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Unauthorized")
            return

        try:
            dashboard_text = self.dashboard.generate_text_dashboard()
            await update.message.reply_text(dashboard_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"❌ /stats error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

    async def cmd_active(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📍 /active - აქტიური სიგნალი"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            active_signals = self.analytics_db.get_active_signals()

            if not active_signals:
                await update.message.reply_text("📭 **No active signals**")
                return

            text = "📍 **Active Signals:**\n\n"
            for sig in active_signals[:10]:
                text += f"**{sig['symbol']}** ({sig['strategy']})\n"
                text += f"├─ Entry: ${sig['entry_price']:.4f}\n"
                text += f"├─ Target: ${sig['target_price']:.4f}\n"
                text += f"├─ Stop: ${sig['stop_loss']:.4f}\n"
                text += f"└─ Conf: {sig['confidence']:.0f}%\n\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /active error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🎯 /performance - სტრატეგიის performance"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            text = "🎯 **Strategy Performance:**\n\n"

            for strategy in ['long_term', 'scalping', 'opportunistic', 'swing']:
                perf = self.analytics_db.get_strategy_performance(strategy)

                if perf['total_signals'] == 0:
                    text += f"**{strategy}:** No data\n\n"
                    continue

                text += f"**{strategy.upper()}**\n"
                text += f"├─ Signals: {perf['total_signals']}\n"
                text += f"├─ Win: {perf['success_rate']:.1f}%\n"
                text += f"├─ Avg: {perf['avg_profit']:+.2f}%\n"
                text += f"└─ Best: {perf['best_trade']:+.2f}%\n\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /performance error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📜 /history - Symbol History"""
        if update.effective_user.id != ADMIN_ID:
            return

        if not context.args:
            await update.message.reply_text("📝 /history SYMBOL\n\nEx: /history BTCUSDT")
            return

        try:
            symbol = context.args[0].upper()
            history = self.analytics_db.get_symbol_history(symbol)

            if history['total_signals'] == 0:
                await update.message.reply_text(f"📭 **{symbol}** - No history")
                return

            text = f"📜 **{symbol}**\n\n"
            text += f"• Signals: {history['total_signals']}\n"
            text += f"• Win Rate: {history['win_rate']:.1f}%\n"
            text += f"• Avg: {history['avg_profit']:+.2f}%\n"
            text += f"• Best: {history['best_trade']:+.2f}%\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /history error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_recent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📝 /recent - ბოლო სიგნალი"""
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
                await update.message.reply_text("📭 **No signals**")
                return

            text = f"📝 **Recent {len(recent)}:**\n\n"

            for sig in recent:
                emoji = "✅" if sig['outcome'] == 'SUCCESS' else "❌" if sig['outcome'] == 'FAILURE' else "⏳"
                profit_str = f"{sig['profit']:+.2f}%" if sig['profit'] is not None else "Pending"

                text += f"{emoji} **{sig['symbol']}** ({sig['strategy']})\n"
                text += f"   {profit_str} | {sig['confidence']:.0f}%\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /recent error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MONITORING COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_openpositions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /openpositions - აქტიური პოზიციები"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            if not self.position_monitor:
                await update.message.reply_text("⚠️ Position Monitor not ready")
                return

            status_report = self.position_monitor.get_position_status_report()
            await update.message.reply_text(status_report, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /openpositions error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_closedpositions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📋 /closedpositions - დახურული ტრეიდი"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            if not self.position_monitor:
                await update.message.reply_text("⚠️ Position Monitor not ready")
                return

            summary = self.position_monitor.get_closed_positions_summary()
            await update.message.reply_text(summary, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /closedpositions error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_exitstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /exitstats - Exit სტატისტიკა"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            exit_stats = self.exit_handler.get_exit_statistics()

            text = "📊 **Exit Statistics:**\n\n"
            text += f"• Total Exits: {exit_stats['total_exits']}\n"
            text += f"• Wins: {exit_stats['successful']}\n"
            text += f"• Losses: {exit_stats['failed']}\n"
            text += f"• Win Rate: {exit_stats.get('win_rate', 0):.1f}%\n\n"
            text += f"• Avg Profit: {exit_stats['avg_profit']:+.2f}%\n"
            text += f"• Best: {exit_stats['best_trade']:+.2f}%\n"
            text += f"• Worst: {exit_stats['worst_trade']:+.2f}%\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /exitstats error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_enginestatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🤖 /enginestatus - Engine status"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            status = self.trading_engine.get_engine_status()
            await update.message.reply_text(status, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /enginestatus error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL HISTORY COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    async def cmd_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📋 /signals - ბოლო სიგნალი"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            recent = self.signal_history_db.get_recent_signals(limit=20)

            if not recent:
                await update.message.reply_text("📭 **No signals**")
                return

            text = "📋 **Recent 20:**\n\n"

            for sig in recent:
                emoji = "✅" if sig['status'] == 'win' else "❌" if sig['status'] == 'loss' else "⏳"
                profit_str = f"{sig['profit_pct']:+.2f}%" if sig['profit_pct'] else "Pending"

                text += f"{emoji} **{sig['symbol']}** ({sig['strategy']})\n"
                text += f"├─ Entry: ${sig['entry_price']:.4f}\n"
                text += f"├─ P&L: {profit_str}\n"
                text += f"├─ Hold: {sig['days_held']:.1f}d\n"
                text += f"└─ Conf: {sig['confidence_score']:.0f}%\n\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /signals error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_signalstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /signalstats - Signal სტატისტიკა"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            stats = self.signal_history_db.get_overall_stats()

            text = "📊 **Signal Statistics:**\n\n"
            text += f"**Sent:**\n"
            text += f"• Total: {stats['total_signals_sent']}\n"
            text += f"• Closed: {stats['total_signals_closed']}\n"
            text += f"• Pending: {stats['pending']}\n\n"

            text += f"**Results:**\n"
            text += f"• Win Rate: {stats['win_rate']:.1f}%\n"
            text += f"• Wins: {stats['wins']}\n"
            text += f"• Losses: {stats['total_signals_closed'] - stats['wins']}\n\n"

            text += f"**Financial:**\n"
            text += f"• Avg: {stats['avg_profit_pct']:+.2f}%\n"
            text += f"• Total: {stats['total_profit_pct']:+.2f}%\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /signalstats error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_symbolstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /symbolstats - Symbol სტატისტიკა"""
        if update.effective_user.id != ADMIN_ID:
            return

        if not context.args:
            await update.message.reply_text("📝 /symbolstats SYMBOL\n\nEx: /symbolstats BTC/USD")
            return

        try:
            symbol = context.args[0].upper()
            stats = self.signal_history_db.get_symbol_history(symbol)

            if stats['total_signals'] == 0:
                await update.message.reply_text(f"📭 **{symbol}** - No signals")
                return

            text = f"📊 **{symbol}**\n\n"
            text += f"• Signals: {stats['total_signals']}\n"
            text += f"• Win Rate: {stats['win_rate']:.1f}%\n"
            text += f"• Wins: {stats['wins']}\n\n"

            text += f"**Financial:**\n"
            text += f"• Avg: {stats['avg_profit']:+.2f}%\n"
            text += f"• Best: {stats['best_trade']:+.2f}%\n"
            text += f"• Worst: {stats['worst_trade']:+.2f}%\n"
            text += f"• Total: {stats['total_profit']:+.2f}%\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /symbolstats error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_strategystats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /strategystats - Strategy სტატისტიკა"""
        if update.effective_user.id != ADMIN_ID:
            return

        if not context.args:
            strategies = ["long_term", "swing", "scalping", "opportunistic"]
            msg = "📝 /strategystats STRATEGY\n\n"
            msg += "Strategies:\n"
            for s in strategies:
                msg += f"• {s}\n"
            await update.message.reply_text(msg)
            return

        try:
            strategy = context.args[0].lower()
            stats = self.signal_history_db.get_strategy_performance(strategy)

            if stats['total_signals'] == 0:
                await update.message.reply_text(f"📭 **{strategy}** - No signals")
                return

            text = f"📊 **{strategy.upper()}**\n\n"
            text += f"• Signals: {stats['total_signals']}\n"
            text += f"• Win Rate: {stats['win_rate']:.1f}%\n"
            text += f"• Wins: {stats['wins']}\n\n"

            text += f"**Financial:**\n"
            text += f"• Avg: {stats['avg_profit_pct']:+.2f}%\n"
            text += f"• Avg Days: {stats['avg_days_held']:.1f}\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /strategystats error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /dashboard - სრული დაშბორდი"""
        if update.effective_user.id != ADMIN_ID:
            return

        try:
            report = self.signal_history_db.generate_report()
            await update.message.reply_text(report, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ /dashboard error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # PAYMENT HANDLING
    # ═══════════════════════════════════════════════════════════════════════

    async def handle_payment_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📸 გადახდის ფოტო"""
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
            "📸 **Payment received!**\n\n"
            "⏳ Awaiting admin approval (1-24 hours)"
        )

        # Send to admin
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
        ]]

        await self.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=f"🔄 **Payment**\n\n👤 @{username} (`{user_id}`)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """გადახდის callback"""
        query = update.callback_query

        if update.effective_user.id != ADMIN_ID:
            await query.answer("❌ Unauthorized")
            return

        action, target_id = query.data.split("_")
        target_id = int(target_id)

        if action == "approve":
            self.add_subscription(target_id, days=30)

            await query.edit_message_caption(
                caption=f"✅ **Approved**\n\nUser: {target_id}",
                parse_mode='Markdown'
            )

            # Notify user
            try:
                await self.bot.send_message(
                    target_id,
                    "🎉 **Payment Approved!**\n\n"
                    "✅ Premium activated for 30 days\n"
                    "📊 Signals: Active\n\n"
                    "/guide - დაიწყეთ"
                )
            except:
                pass

        else:  # reject
            await query.edit_message_caption(
                caption=f"❌ **Rejected**\n\nUser: {target_id}",
                parse_mode='Markdown'
            )

            try:
                await self.bot.send_message(
                    target_id,
                    "❌ **Payment Rejected**\n\n"
                    "Please contact support"
                )
            except:
                pass

        await query.answer()

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL BROADCASTING
    # ═══════════════════════════════════════════════════════════════════════

    async def broadcast_signal(self, message: str, asset: str):
        """სიგნალის გაგზავნა აქტიური მომხმარებელზე"""
        full_message = message + GUIDE_FOOTER
        active_users = self.get_active_subscribers()

        logger.info(f"📤 Broadcasting to {len(active_users)} users: {asset}")

        success = 0
        failed = 0

        for user_id in active_users:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=full_message,
                    parse_mode='Markdown'
                )
                success += 1
                await asyncio.sleep(0.05)

            except Exception as e:
                failed += 1
                logger.debug(f"Send failed {user_id}: {e}")

        logger.info(f"✅ Broadcast complete: {success} OK, {failed} FAILED")

    # ═══════════════════════════════════════════════════════════════════════
    # HANDLERS SETUP
    # ═══════════════════════════════════════════════════════════════════════

    def _setup_handlers(self):
        """ყველა ბრძანების რეგისტრაცია"""

        # User commands
        self.application.add_handler(CommandHandler("start", self.cmd_start))
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
        """ბოტის გაშვება"""
        async with self._start_lock:
            if self._is_running:
                logger.warning("⚠️ Bot already running")
                return

            try:
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling(drop_pending_updates=True)

                self._is_running = True
                logger.info("🚀 Telegram Bot v3.0 started!")

                # Wait for stop signal
                self._stop_event = asyncio.Event()
                await self._stop_event.wait()

            except Exception as e:
                logger.error(f"❌ Bot error: {e}")
                self._is_running = False
                raise

    async def stop(self):
        """ბოტის შეწყვეტა"""
        if not self._is_running:
            logger.warning("⚠️ Bot not running")
            return

        logger.info("🛑 Stopping bot...")
        if hasattr(self, '_stop_event'):
            self._stop_event.set()

        try:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")

        self._is_running = False
        logger.info("✅ Bot stopped")