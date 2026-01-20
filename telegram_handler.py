"""
AI Trading Bot - Telegram Handler
ყველა Telegram ფუნქცია და ბრძანება (Optimized with Guide Function)
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

    def add_subscription(self, user_id, days=30):
        expires = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        self.subscriptions[user_id] = {
            'expires_at': expires,
            'activated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'plan': 'premium'
        }
        self.save_json(self.subscriptions, SUBSCRIPTIONS_FILE)

    def get_active_subscribers(self):
        return [uid for uid in self.subscriptions.keys() if self.is_active_subscriber(uid)]

    # ========================
    # COMMAND HANDLERS
    # ========================
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command with Guide hint"""
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

        # დამატებითი ინფორმაცია გაიდზე
        welcome_msg += "\n\n📖 **ახალი ხართ?** გამოიყენეთ ბრძანება /guide სიგნალების განმარტებისთვის."

        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def cmd_guide(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guide command - Explains the trading logic to users"""
        guide_text = (
            "📖 **AI სიგნალების განმარტება**\n\n"
            "ჩემი სიგნალები ეფუძნება კომპლექსურ ანალიზს. აი, რა უნდა იცოდეთ:\n\n"
            "🔹 **RSI (სიჩქარის საზომი):**\n"
            "• თუ < 30: აქტივი ძალიან იაფია (გადაყიდულია). საუკეთესო დროა ყიდვისთვის.\n"
            "• თუ > 70: აქტივი ძვირია. ფრთხილად იყავით.\n\n"
            "🔹 **EMA 200 (ტრენდის ხაზი):**\n"
            "• ეს არის ბაზრის 'დინება'. თუ ფასი ამ ხაზის ზემოთაა, ტრენდი აღმავალია და ყიდვა უფრო უსაფრთხოა.\n\n"
            "🔹 **Bollinger Bands (დერეფანი):**\n"
            "• ქვედა ხაზთან შეხება ნიშნავს 'იატაკს', საიდანაც ფასი ხშირად ზემოთ ხტება.\n\n"
            "🔹 **AI Score (ნდობა):**\n"
            "• **80-100:** მაღალი ალბათობა\n"
            "• **60-70:** საშუალო რისკი\n\n"
            "🛡️ **Stop-Loss:** ყოველთვის გამოიყენეთ ეს მაჩვენებელი, რომ დაიცვათ თქვენი ბალანსი დიდი ვარდნისგან."
        )
        await update.message.reply_text(guide_text, parse_mode='Markdown')

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(PAYMENT_INSTRUCTIONS)

    async def cmd_mystatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if self.is_active_subscriber(user_id):
            expires = self.subscriptions[user_id]['expires_at']
            days_left = (datetime.strptime(expires, '%Y-%m-%d').date() - datetime.now().date()).days
            status_msg = (
                f"✅ **აქტიური სტატუსი**\n\n"
                f"📅 იწურება: `{expires}`\n"
                f"⏳ დარჩენილი: {days_left} დღე\n"
                f"🧠 AI ანალიზი: ჩართულია"
            )
        else:
            status_msg = "⚠️ თქვენ არ გაქვთ აქტიური subscription.\nგასააქტიურებლად: /subscribe"
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
            self.save_json(self.subscriptions, SUBSCRIPTIONS_FILE)
            await update.message.reply_text("👋 სერვისი გაუქმებულია. იმედია მალე დაბრუნდებით!")
        else:
            await update.message.reply_text("ℹ️ თქვენ არ გაქვთ აქტიური სერვისი.")

    # ========================
    # ADMIN COMMANDS
    # ========================
    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return
        admin_msg = (
            "👑 **ადმინ პანელი**\n\n"
            "/adduser [ID] [დღეები]\n"
            "/listusers - მომხმარებლები\n"
            "/botstats - სტატისტიკა"
        )
        await update.message.reply_text(admin_msg, parse_mode='Markdown')

    async def cmd_adduser(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        try:
            target_id = int(context.args[0])
            days = int(context.args[1]) if len(context.args) > 1 else 30
            self.add_subscription(target_id, days)
            await update.message.reply_text(f"✅ მომხმარებელი {target_id} დაემატა {days} დღით.")
        except:
            await update.message.reply_text("❌ ფორმატი: /adduser [ID] [დღეები]")

    async def cmd_listusers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        users_text = "📋 **მომხმარებელთა სია:**\n\n"
        for uid, data in self.subscriptions.items():
            status = "✅" if self.is_active_subscriber(uid) else "❌"
            users_text += f"{status} `{uid}` - {data.get('expires_at')}\n"
        await update.message.reply_text(users_text, parse_mode='Markdown')

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        stats = self.trading_engine.stats
        stats_msg = (
            f"📊 **ბოტის სტატისტიკა**\n\n"
            f"👥 სულ მომხმარებელი: {len(self.subscriptions)}\n"
            f"📡 სიგნალები: {stats['total_signals']}\n"
            f"✅ წარმატებული: {stats['successful_trades']}\n"
            f"❌ წაგებული: {stats['failed_trades']}"
        )
        await update.message.reply_text(stats_msg, parse_mode='Markdown')

    # ========================
    # PAYMENT & CALLBACKS
    # ========================
    async def handle_payment_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "User"
        self.payment_requests[str(user_id)] = {
            'username': username,
            'status': 'pending',
            'photo_id': update.message.photo[-1].file_id
        }
        self.save_json(self.payment_requests, PAYMENT_REQUESTS_FILE)

        await update.message.reply_text("📸 ფოტო მიღებულია! ადმინისტრატორი დაადასტურებს 24 საათში.")

        keyboard = [[
            InlineKeyboardButton("✅ დადასტურება", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ უარყოფა", callback_data=f"reject_{user_id}")
        ]]
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=f"🔄 გადახდა: @{username} ({user_id})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if update.effective_user.id != ADMIN_ID: return

        action, target_id = query.data.split("_")
        target_id = int(target_id)

        if action == "approve":
            self.add_subscription(target_id)
            await query.edit_message_caption(caption=f"✅ დადასტურებულია: {target_id}")
            await self.bot.send_message(target_id, "🎉 თქვენი გადახდა დადასტურდა! სერვისი აქტიურია.")
        else:
            await query.edit_message_caption(caption=f"❌ უარყოფილია: {target_id}")
            await self.bot.send_message(target_id, "❌ გადახდა უარყოფილია. გთხოვთ დაუკავშირდეთ ადმინს.")

    # ========================
    # BROADCASTING & SETUP
    # ========================
    async def broadcast_signal(self, message, asset):
        import time
        now = time.time()
        if now - self.last_notifications.get(asset, 0) < NOTIFICATION_COOLDOWN:
            return
        self.last_notifications[asset] = now
        for user_id in self.get_active_subscribers():
            try:
                await self.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
                await asyncio.sleep(0.05)
            except:
                continue

    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("guide", self.cmd_guide))
        self.application.add_handler(CommandHandler("subscribe", self.cmd_subscribe))
        self.application.add_handler(CommandHandler("mystatus", self.cmd_mystatus))
        self.application.add_handler(CommandHandler("stop", self.cmd_stop))
        self.application.add_handler(CommandHandler("admin", self.cmd_admin))
        self.application.add_handler(CommandHandler("adduser", self.cmd_adduser))
        self.application.add_handler(CommandHandler("listusers", self.cmd_listusers))
        self.application.add_handler(CommandHandler("botstats", self.cmd_botstats))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_payment_photo))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

    async def start(self):
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("✅ Telegram Handler წარმატებით გაეშვა")