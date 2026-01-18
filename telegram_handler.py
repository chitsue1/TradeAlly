"""
AI Trading Bot - Telegram Handler
ყველა Telegram ფუნქცია და ბრძანება
"""

import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

from config import *

logger = logging.getLogger(__name__)


class TelegramHandler:
    """Telegram bot handler - commands, messages, callbacks"""

    def __init__(self, trading_engine):
        self.trading_engine = trading_engine
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.bot = self.application.bot

        # Load data
        self.subscriptions = self.load_json(SUBSCRIPTIONS_FILE)
        self.payment_requests = self.load_json(PAYMENT_REQUESTS_FILE)
        self.last_notifications = {}

        # Setup handlers
        self.setup_handlers()

    # ========================
    # JSON OPERATIONS
    # ========================
    def load_json(self, filename):
        """Load JSON file"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                    if filename == SUBSCRIPTIONS_FILE:
                        return {int(k): v for k, v in data.items()}
                    return data
            return {}
        except Exception as e:
            logger.error(f"Load error {filename}: {e}")
            return {}

    def save_json(self, data, filename):
        """Save JSON file"""
        try:
            if filename == SUBSCRIPTIONS_FILE:
                data = {str(k): v for k, v in data.items()}
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Save error {filename}: {e}")

    # ========================
    # SUBSCRIPTION MANAGEMENT
    # ========================
    def is_active_subscriber(self, user_id):
        """Check if user has active subscription"""
        if user_id not in self.subscriptions:
            return False

        expires_str = self.subscriptions[user_id].get('expires_at')
        if not expires_str:
            return False

        try:
            expires = datetime.strptime(expires_str, '%Y-%m-%d').date()
            today = datetime.now().date()
            return today <= expires
        except:
            return False

    def add_subscription(self, user_id, days=30):
        """Add or extend subscription"""
        expires = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        self.subscriptions[user_id] = {
            'expires_at': expires,
            'activated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'plan': 'premium'
        }
        self.save_json(self.subscriptions, SUBSCRIPTIONS_FILE)

    def get_active_subscribers(self):
        """Get list of active subscriber IDs"""
        return [uid for uid in self.subscriptions.keys() if self.is_active_subscriber(uid)]

    # ========================
    # COMMAND HANDLERS
    # ========================
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        username = update.effective_user.username or "მომხმარებელი"

        ai_info = f"{len(self.trading_engine.trading_knowledge.get('patterns', []))} ნიმუში" \
                  if self.trading_engine.trading_knowledge.get('patterns') else "ბაზა"

        welcome_msg = WELCOME_MSG_TEMPLATE.format(
            username=username,
            ai_info=ai_info,
            crypto_count=len(CRYPTO),
            stocks_count=len(STOCKS),
            commodities_count=len(COMMODITIES)
        )

        await update.message.reply_text(welcome_msg)

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Subscribe command"""
        user_id = update.effective_user.id

        if self.is_active_subscriber(user_id):
            expires = self.subscriptions[user_id]['expires_at']
            await update.message.reply_text(
                f"✅ უკვე გაქვთ აქტიური subscription!\n"
                f"📅 იწურება: {expires}"
            )
            return

        await update.message.reply_text(PAYMENT_INSTRUCTIONS)

    async def cmd_mystatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """My status command"""
        user_id = update.effective_user.id

        if self.is_active_subscriber(user_id):
            expires = self.subscriptions[user_id]['expires_at']
            days_left = (datetime.strptime(expires, '%Y-%m-%d').date() - datetime.now().date()).days

            status_msg = (
                f"✅ აქტიური subscription\n\n"
                f"📅 იწურება: {expires}\n"
                f"⏳ დარჩენილი: {days_left} დღე\n"
                f"📊 სტატუსი: აქტიური\n"
                f"🧠 AI: აქტიური\n\n"
                f"🤖 მიიღებთ ყველა სიგნალს!"
            )
        else:
            status_msg = (
                "⚠️ არააქტიური subscription\n\n"
                "გააქტიურება: /subscribe"
            )

        await update.message.reply_text(status_msg)

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop subscription"""
        user_id = update.effective_user.id

        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
            self.save_json(self.subscriptions, SUBSCRIPTIONS_FILE)
            await update.message.reply_text(
                "👋 subscription გაუქმებულია.\n\n"
                "მადლობა! /subscribe - ხელახალი გააქტიურება"
            )
        else:
            await update.message.reply_text("ℹ️ არ გაქვთ აქტიური subscription.")

    # ========================
    # ADMIN COMMANDS
    # ========================
    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel"""
        user_id = update.effective_user.id

        if user_id != ADMIN_ID:
            await update.message.reply_text("🚫 არ გაქვთ უფლება!")
            return

        ai_stats = (
            f"• ნიმუშები: {len(self.trading_engine.trading_knowledge.get('patterns', []))}\n"
            f"• სტრატეგიები: {len(self.trading_engine.trading_knowledge.get('strategies', []))}"
        ) if self.trading_engine.trading_knowledge else "• AI არ არის ჩატვირთული"

        admin_msg = (
            f"👑 ადმინის პანელი\n\n"
            f"📋 ბრძანებები:\n"
            f"/adduser [ID] [დღეები] - ახალი user\n"
            f"/listusers - ყველა user\n"
            f"/botstats - სტატისტიკა\n\n"
            f"🧠 AI სტატუსი:\n{ai_stats}\n\n"
            f"💳 გადახდის ფოტოებზე:\n"
            f"გამოიყენეთ ღილაკები"
        )
        await update.message.reply_text(admin_msg)

    async def cmd_adduser(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add user (admin only)"""
        user_id = update.effective_user.id

        if user_id != ADMIN_ID:
            await update.message.reply_text("🚫 არ გაქვთ უფლება!")
            return

        try:
            if len(context.args) < 1:
                await update.message.reply_text("❌ ფორმატი: /adduser [ID] [დღეები=30]")
                return

            target_id = int(context.args[0])
            days = int(context.args[1]) if len(context.args) > 1 else 30

            self.add_subscription(target_id, days)
            await update.message.reply_text(
                f"✅ მომხმარებელი დაემატა!\n"
                f"🆔 {target_id}\n"
                f"📅 {days} დღე"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ შეცდომა: {e}")

    async def cmd_listusers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all users (admin only)"""
        user_id = update.effective_user.id

        if user_id != ADMIN_ID:
            await update.message.reply_text("🚫 არ გაქვთ უფლება!")
            return

        if not self.subscriptions:
            await update.message.reply_text("ℹ️ არ არის მომხმარებლები.")
            return

        users_list = "📋 ყველა მომხმარებელი:\n\n"
        active_count = 0

        for uid, data in self.subscriptions.items():
            if self.is_active_subscriber(uid):
                status = "✅ აქტიური"
                active_count += 1
            else:
                status = "❌ არააქტიური"

            expires = data.get('expires_at', 'N/A')
            users_list += f"🆔 {uid}: {status}\n📅 {expires}\n\n"

        users_list += (
            f"👥 სულ: {len(self.subscriptions)}\n"
            f"✅ აქტიური: {active_count}\n"
            f"💰 შემოსავალი: {active_count * 150}₾/თვე"
        )
        await update.message.reply_text(users_list)

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot statistics (admin only)"""
        user_id = update.effective_user.id

        if user_id != ADMIN_ID:
            await update.message.reply_text("🚫 არ გაქვთ უფლება!")
            return

        active_users = len(self.get_active_subscribers())
        pending_payments = sum(1 for req in self.payment_requests.values() if req.get('status') == 'pending')

        ai_info = (
            f"🧠 AI ცოდნა:\n"
            f"• ნიმუშები: {len(self.trading_engine.trading_knowledge.get('patterns', []))}\n"
            f"• სტრატეგიები: {len(self.trading_engine.trading_knowledge.get('strategies', []))}\n\n"
        ) if self.trading_engine.trading_knowledge.get('patterns') else ""

        stats = self.trading_engine.stats
        win_rate = (
            (stats['successful_trades'] / stats['total_signals'] * 100)
            if stats['total_signals'] > 0 else 0
        )

        stats_msg = (
            f"📊 ბოტის სტატისტიკა\n\n"
            f"👥 მომხმარებლები: {len(self.subscriptions)}\n"
            f"✅ აქტიური: {active_users}\n"
            f"💳 გადახდის მოთხოვნები: {pending_payments}\n"
            f"📈 აქტიური პოზიციები: {len(self.trading_engine.active_positions)}\n"
            f"📡 მონიტორინგი: {len(ASSETS)} აქტივი\n"
            f"⏱️ ციკლი: ~{len(CRYPTO) * ASSET_DELAY / 60:.1f}წთ\n\n"
            f"{ai_info}"
            f"📊 ტრეიდინგის სტატისტიკა:\n"
            f"• სულ სიგნალები: {stats['total_signals']}\n"
            f"• წარმატებული: {stats['successful_trades']}\n"
            f"• წაგებული: {stats['failed_trades']}\n"
            f"• Win Rate: {win_rate:.1f}%\n"
            f"• საშუალო მოგება: {stats['total_profit_percent']:.2f}%\n\n"
            f"💰 შემოსავალი: {active_users * 150}₾/თვე"
        )
        await update.message.reply_text(stats_msg)

    # ========================
    # PAYMENT HANDLING
    # ========================
    async def handle_payment_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle payment screenshot"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"

        self.payment_requests[str(user_id)] = {
            'username': username,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending',
            'photo_id': update.message.photo[-1].file_id if update.message.photo else None
        }
        self.save_json(self.payment_requests, PAYMENT_REQUESTS_FILE)

        await update.message.reply_text(
            "📸 გადახდის ფოტო მიღებულია!\n\n"
            "ადმინისტრატორი გადაამოწმებს და გაააქტიურებს subscription-ს.\n"
            "⏱️ პროცესი: 24 საათში.\n\n"
            "❓ კითხვები? https://t.me/Kagurashinakami"
        )

        keyboard = [[
            InlineKeyboardButton("✅ დადასტურება", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ უარყოფა", callback_data=f"reject_{user_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=update.message.photo[-1].file_id,
                    caption=(
                        f"🔄 ახალი გადახდის მოთხოვნა\n\n"
                        f"👤 @{username}\n"
                        f"🆔 {user_id}\n"
                        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
                    ),
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"ადმინისთვის გაგზავნის შეცდომა: {e}")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback buttons"""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id

        if user_id != ADMIN_ID:
            await query.edit_message_text("🚫 არ გაქვთ უფლება!")
            return

        data = query.data
        if data.startswith("approve_"):
            target_user_id = int(data.split("_")[1])
            await self.approve_payment(query, target_user_id)
        elif data.startswith("reject_"):
            target_user_id = int(data.split("_")[1])
            await self.reject_payment(query, target_user_id)

    async def approve_payment(self, query, user_id):
        """Approve payment"""
        self.add_subscription(user_id, days=30)

        if str(user_id) in self.payment_requests:
            self.payment_requests[str(user_id)]['status'] = 'approved'
            self.save_json(self.payment_requests, PAYMENT_REQUESTS_FILE)

        await query.edit_message_text(
            f"✅ გადახდა დადასტურებულია!\n\n"
            f"👤 {user_id}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"Subscription გააქტიურდა 30 დღით."
        )

        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 თქვენი გადახდა დადასტურდა!\n\n"
                    "✅ Subscription გააქტიურდა 30 დღით.\n"
                    "🤖 ახლა მიიღებთ ყველა AI სიგნალს.\n\n"
                    "/mystatus - სტატუსი"
                )
            )
        except:
            pass

    async def reject_payment(self, query, user_id):
        """Reject payment"""
        if str(user_id) in self.payment_requests:
            self.payment_requests[str(user_id)]['status'] = 'rejected'
            self.save_json(self.payment_requests, PAYMENT_REQUESTS_FILE)

        await query.edit_message_text(
            f"❌ გადახდა უარყოფილია\n\n"
            f"👤 {user_id}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )

        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ თქვენი გადახდა უარყოფილია\n\n"
                    "დაუკავშირდით: https://t.me/Kagurashinakami"
                )
            )
        except:
            pass

    # ========================
    # BROADCASTING
    # ========================
    async def broadcast_signal(self, message, asset):
        """Broadcast signal to subscribers"""
        import time
        now = time.time()

        # Cooldown check
        if now - self.last_notifications.get(asset, 0) < NOTIFICATION_COOLDOWN:
            logger.info(f"⏸️ Cooldown აქტიური: {asset}")
            return

        self.last_notifications[asset] = now
        success_count = 0
        failed_count = 0

        for user_id in self.get_active_subscribers():
            try:
                await self.bot.send_message(chat_id=user_id, text=message)
                success_count += 1
                await asyncio.sleep(0.05)  # 20 msg/sec Telegram limit
            except Exception as e:
                failed_count += 1
                logger.warning(f"გაგზავნის შეცდომა {user_id}: {e}")

        logger.info(f"📨 Broadcast: {success_count} წარმატებული, {failed_count} წარუმატებელი")

    # ========================
    # SETUP HANDLERS
    # ========================
    def setup_handlers(self):
        """Setup all command handlers"""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("subscribe", self.cmd_subscribe))
        self.application.add_handler(CommandHandler("mystatus", self.cmd_mystatus))
        self.application.add_handler(CommandHandler("stop", self.cmd_stop))
        self.application.add_handler(CommandHandler("admin", self.cmd_admin))
        self.application.add_handler(CommandHandler("adduser", self.cmd_adduser))
        self.application.add_handler(CommandHandler("listusers", self.cmd_listusers))
        self.application.add_handler(CommandHandler("botstats", self.cmd_botstats))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_payment_photo))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

    # ========================
    # START APPLICATION
    # ========================
    async def start(self):
        """Start Telegram application"""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        logger.info("✅ Telegram Bot აქტიურია")