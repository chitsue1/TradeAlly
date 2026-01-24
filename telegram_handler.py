import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# ივარაუდება, რომ config.py-ში გაქვს ყველა საჭირო ცვლადი (TOKEN, ADMIN_ID და ა.შ.)
from config import *

logger = logging.getLogger(__name__)

class TelegramHandler:
    """
    პროფესიონალური Telegram Bot Handler.
    მართავს მომხმარებლებს, გადახდებს, სიგნალების დაგზავნას და ადმინისტრირებას.
    """

    def __init__(self, trading_engine):
        self.trading_engine = trading_engine
        # აპლიკაციის ინიციალიზაცია
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.bot = self.application.bot

        # მონაცემების ფაილების გზები (config-დან)
        self.subscriptions_file = SUBSCRIPTIONS_FILE
        self.payment_requests_file = PAYMENT_REQUESTS_FILE

        # მონაცემების ჩატვირთვა
        self.subscriptions = self.load_json(self.subscriptions_file)
        self.payment_requests = self.load_json(self.payment_requests_file)
        self.last_notifications = {}

        # დაცვის მექანიზმები
        self._is_running = False
        self._start_lock = asyncio.Lock()

        # ჰენდლერების გამართვა
        self.setup_handlers()

    # ========================
    # მონაცემთა მართვა (JSON)
    # ========================
    def load_json(self, filename):
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if filename == self.subscriptions_file:
                        return {int(k): v for k, v in data.items()}
                    return data
            return {}
        except Exception as e:
            logger.error(f"❌ ფაილის ჩატვირთვის შეცდომა {filename}: {e}")
            return {}

    def save_json(self, data, filename):
        try:
            temp_data = data
            if filename == self.subscriptions_file:
                temp_data = {str(k): v for k, v in data.items()}

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(temp_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ ფაილის შენახვის შეცდომა {filename}: {e}")

    # ========================
    # SUBSCRIPTION ლოგიკა
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
        self.save_json(self.subscriptions, self.subscriptions_file)
        logger.info(f"✅ მომხმარებელს {user_id} გაუაქტიურდა პრემიუმი {days} დღით.")

    def get_active_subscribers(self):
        return [uid for uid in self.subscriptions.keys() if self.is_active_subscriber(uid)]

    # ========================
    # მომხმარებლის ბრძანებები
    # ========================
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.effective_user.username or "მომხმარებელი"
        welcome_msg = WELCOME_MSG_TEMPLATE.format(
            username=username,
            ai_info="აქტიური 🧠",
            crypto_count="50+",
            stocks_count="Top 100",
            commodities_count="Gold/Oil"
        )
        welcome_msg += "\n\n📖 **ახალი ხართ?** გამოიყენეთ /guide სიგნალების განმარტებისთვის."
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def cmd_guide(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        guide_text = (
            "📖 **AI ვაჭრობის გზამკვლევი**\n\n"
            "🔹 **RSI (სიჩქარე):** <30 = იაფია (ყიდვა), >70 = ძვირია.\n"
            "🔹 **EMA 200:** თუ ფასი ხაზს ზემოთაა - ტრენდი ზრდადია.\n"
            "🔹 **BB Low:** ქვედა ზოლთან შეხება - პოტენციური ასხლეტა.\n"
            "🔹 **Stop-Loss:** ყოველთვის დააყენეთ რისკის დასაზღვევად!"
        )
        await update.message.reply_text(guide_text, parse_mode='Markdown')

    async def cmd_tiers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # კატეგორიების ჩვენება (config-დან წამოღებული)
        from config import TIER_1_BLUE_CHIPS, TIER_2_HIGH_GROWTH, TIER_3_MEME_COINS
        tiers_msg = (
            "📊 **კრიპტო კატეგორიები:**\n\n"
            f"🔵 **Tier 1 (სტაბილური):** {', '.join([c.split('/')[0] for c in TIER_1_BLUE_CHIPS[:5]])}...\n"
            f"🟢 **Tier 2 (ზრდადი):** {', '.join([c.split('/')[0] for c in TIER_2_HIGH_GROWTH[:5]])}...\n"
            f"🟡 **Tier 3 (მემეები):** {', '.join([c.split('/')[0] for c in TIER_3_MEME_COINS[:5]])}..."
        )
        await update.message.reply_text(tiers_msg, parse_mode='Markdown')

    async def cmd_mystatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if self.is_active_subscriber(user_id):
            expires = self.subscriptions[user_id]['expires_at']
            status_msg = f"✅ **სტატუსი: აქტიური**\n📅 იწურება: `{expires}`"
        else:
            status_msg = "⚠️ არ გაქვთ აქტიური პაკეტი. /subscribe"
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    # ========================
    # ადმინისტრატორის ფუნქციები
    # ========================
    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        msg = "👑 **ადმინ პანელი**\n\n/adduser [ID] [days]\n/listusers\n/botstats"
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        stats = getattr(self.trading_engine, 'stats', {})
        msg = (
            f"📊 **ბოტის სტატისტიკა**\n\n"
            f"👥 მომხმარებლები: {len(self.subscriptions)}\n"
            f"📡 სულ სიგნალები: {stats.get('total_signals', 0)}"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    # ========================
    # გადახდების დამუშავება
    # ========================
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
        self.save_json(self.payment_requests, self.payment_requests_file)

        await update.message.reply_text("📸 ფოტო მიღებულია! ადმინისტრატორი განიხილავს უმოკლეს დროში.")

        # ადმინთან გაგზავნა დასადასტურებლად
        keyboard = [[
            InlineKeyboardButton("✅ დადასტურება", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ უარყოფა", callback_data=f"reject_{user_id}")
        ]]
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=f"🔄 გადახდის მოთხოვნა: @{username} ({user_id})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if update.effective_user.id != ADMIN_ID: return

        action, target_id = query.data.split("_")
        target_id = int(target_id)

        if action == "approve":
            self.add_subscription(target_id)
            await query.edit_message_caption(caption=f"✅ დადასტურებულია: {target_id}")
            await self.bot.send_message(target_id, "🎉 გადახდა დადასტურდა! სიგნალები ჩართულია.")
        else:
            await query.edit_message_caption(caption=f"❌ უარყოფილია: {target_id}")
            await self.bot.send_message(target_id, "❌ გადახდა უარყოფილია. ხარვეზის შემთხვევაში მოგვწერეთ.")

        await query.answer()

    # ========================
    # სიგნალების დაგზავნა (Broadcasting)
    # ========================
    async def broadcast_signal(self, message, asset):
        import time
        now = time.time()
        # Cooldown დაცვა (config-დან)
        if now - self.last_notifications.get(asset, 0) < NOTIFICATION_COOLDOWN:
            return

        self.last_notifications[asset] = now
        full_message = message + "\n\n" + GUIDE_FOOTER

        active_users = self.get_active_subscribers()
        for user_id in active_users:
            try:
                await self.bot.send_message(chat_id=user_id, text=full_message, parse_mode='Markdown')
                await asyncio.sleep(0.05) # Flood protection
            except Exception as e:
                logger.debug(f"შეცდომა გაგზავნისას {user_id}: {e}")

    # ========================
    # LIFECYCLE მენეჯმენტი
    # ========================
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("guide", self.cmd_guide))
        self.application.add_handler(CommandHandler("tiers", self.cmd_tiers))
        self.application.add_handler(CommandHandler("mystatus", self.cmd_mystatus))
        self.application.add_handler(CommandHandler("subscribe", lambda u, c: u.message.reply_text(PAYMENT_INSTRUCTIONS)))
        self.application.add_handler(CommandHandler("admin", self.cmd_admin))
        self.application.add_handler(CommandHandler("botstats", self.cmd_botstats))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_payment_photo))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

    async def start(self):
        """ბოტის უსაფრთხო გაშვება"""
        async with self._start_lock:
            if self._is_running: return

            try:
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling(drop_pending_updates=True)

                self._is_running = True
                logger.info("🚀 Telegram ბოტი წარმატებით გაეშვა!")

                self._stop_event = asyncio.Event()
                await self._stop_event.wait()
            except Exception as e:
                logger.error(f"❌ გაშვების კრიტიკული შეცდომა: {e}")
                self._is_running = False

    async def stop(self):
        """ბოტის უსაფრთხო გაჩერება"""
        if not self._is_running: return

        logger.info("🛑 Telegram ბოტის გაჩერება...")
        if hasattr(self, '_stop_event'):
            self._stop_event.set()

        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        self._is_running = False