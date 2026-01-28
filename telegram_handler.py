import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# ✅ FIXED: Import ALL message templates from config
from config import *

# ✅ NEW: Import analytics system
from analytics_system import AnalyticsDatabase, AnalyticsDashboard

logger = logging.getLogger(__name__)

class TelegramHandler:
    """
    პროფესიონალური Telegram Bot Handler.
    მართავს მომხმარებლებს, გადახდებს, სიგნალების დაგზავნას და ადმინისტრირებას.
    ✅ NEW: Analytics integration
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

        # ✅ NEW: Analytics initialization
        self.analytics_db = AnalyticsDatabase("trading_analytics.db")
        self.dashboard = AnalyticsDashboard(self.analytics_db)

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
        """✅ FIXED: გამოიყენებს WELCOME_MSG_TEMPLATE config-დან"""
        username = update.effective_user.username or "მომხმარებელი"

        # ✅ სწორად ივსება template config-დან
        welcome_msg = WELCOME_MSG_TEMPLATE.format(
            username=username,
            crypto_count=len(CRYPTO),  # 34
            ai_info="აქტიური 🧠",
            stocks_count="0",  # crypto-only
            commodities_count="0"  # crypto-only
        )

        # დამატებითი ინფო
        welcome_msg += "\n\n📖 **ახალი ხართ?** გამოიყენეთ /guide სიგნალების განმარტებისთვის."

        await update.message.reply_text(welcome_msg, parse_mode='Markdown')

    async def cmd_guide(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """✅ დეტალური გზამკვლევი"""
        guide_text = (
            "📖 **AI ვაჭრობის გზამკვლევი**\n\n"
            "**🔹 RSI (Relative Strength Index)**\n"
            "• <30 = გადაყიდულია (ყიდვის სიგნალი 📉)\n"
            "• 30-70 = ნორმალური ზონა\n"
            "• >70 = გადახურებულია (გაყიდვის სიგნალი 📈)\n\n"

            "**🔹 EMA 200 (Exponential Moving Average)**\n"
            "• ფასი > EMA200 = აღმავალი ტრენდი 📈\n"
            "• ფასი < EMA200 = დაღმავალი ტრენდი 📉\n"
            "• გრძელვადიანი ტრენდის მაჩვენებელი\n\n"

            "**🔹 Bollinger Bands (BB)**\n"
            "• BB Low-თან შეხება = შესაძლო ასხლეტა 🎯\n"
            "• BB High-თან შეხება = შესაძლო დაცემა ⚠️\n"
            "• ვოლატილობის საზომი\n\n"

            "**🔹 Stop-Loss & Take-Profit**\n"
            "• Stop-Loss: ავტომატური გაყიდვა ზარალის შეზღუდვისთვის 🔴\n"
            "• Take-Profit: მოგების ფიქსირება მიზნის მიღწევისას 🟢\n"
            "• **ყოველთვის** დააყენეთ რისკის მართვისთვის!\n\n"

            "**🎯 AI Score განმარტება:**\n"
            "• 0-30: სუსტი სიგნალი ❌\n"
            "• 30-45: საშუალო სიგნალი ⚠️\n"
            "• 45-65: კარგი სიგნალი ✅\n"
            "• 65+: ძლიერი სიგნალი 🔥\n\n"

            "💡 **რჩევა:** არ შევიდეთ ტრეიდში მხოლოდ AI Score-ის მიხედვით. "
            "ყოველთვის გაითვალისწინეთ ბაზრის ზოგადი მდგომარეობა!"
        )
        await update.message.reply_text(guide_text, parse_mode='Markdown')

    async def cmd_tiers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """✅ FIXED: გამოიყენებს TIER_DESCRIPTIONS config-დან"""

        # ✅ უბრალოდ გამოაქვს უკვე დაფორმატებული TIER_DESCRIPTIONS
        # (TIER_DESCRIPTIONS config.py-ში უკვე .format()-ით არის შევსებული)
        await update.message.reply_text(TIER_DESCRIPTIONS, parse_mode='Markdown')

    async def cmd_mystatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """✅ მომხმარებლის სტატუსი"""
        user_id = update.effective_user.id
        if self.is_active_subscriber(user_id):
            expires = self.subscriptions[user_id]['expires_at']
            activated = self.subscriptions[user_id].get('activated_at', 'N/A')

            # დარჩენილი დღების გამოთვლა
            from datetime import datetime
            expires_date = datetime.strptime(expires, '%Y-%m-%d').date()
            today = datetime.now().date()
            days_left = (expires_date - today).days

            status_msg = (
                f"✅ **სტატუსი: აქტიური Premium**\n\n"
                f"📅 გააქტიურდა: `{activated}`\n"
                f"📅 იწურება: `{expires}`\n"
                f"⏳ დარჩენილია: **{days_left} დღე**\n\n"
                f"📊 სიგნალები: ჩართულია ✅\n"
                f"🔔 შეტყობინებები: აქტიური"
            )
        else:
            status_msg = (
                "⚠️ **არ გაქვთ აქტიური პაკეტი**\n\n"
                "💰 ფასი: 150₾ / თვე\n\n"
                "📌 გამოწერისთვის: /subscribe"
            )
        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """✅ FIXED: გამოიყენებს PAYMENT_INSTRUCTIONS config-დან"""
        await update.message.reply_text(PAYMENT_INSTRUCTIONS, parse_mode='Markdown')

    # ════════════════════════════════════════════════════════════
    # ✅ NEW: ANALYTICS COMMANDS (ADMIN ONLY)
    # ════════════════════════════════════════════════════════════

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /stats - სრული Analytics Dashboard (მხოლოდ ადმინისთვის)
        """
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ არ ხართ ავტორიზებული.")
            return

        try:
            # Generate dashboard
            dashboard_text = self.dashboard.generate_text_dashboard()
            await update.message.reply_text(dashboard_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"❌ Error generating stats: {e}")
            await update.message.reply_text(f"❌ შეცდომა სტატისტიკის გენერაციისას: {e}")

    async def cmd_active(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /active - აქტიური სიგნალები (მხოლოდ ადმინისთვის)
        """
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ არ ხართ ავტორიზებული.")
            return

        try:
            active_signals = self.analytics_db.get_active_signals()

            if not active_signals:
                await update.message.reply_text("📭 **ამ მომენტში არ არის აქტიური სიგნალები**")
                return

            text = "📊 **ACTIVE SIGNALS:**\n\n"

            for sig in active_signals:
                # Calculate current profit if we have price data
                text += f"**{sig['symbol']}** ({sig['strategy']})\n"
                text += f"├─ Entry: ${sig['entry_price']:.4f}\n"
                text += f"├─ Target: ${sig['target_price']:.4f}\n"
                text += f"├─ Stop: ${sig['stop_loss']:.4f}\n"
                text += f"├─ Confidence: {sig['confidence']:.0f}%\n"
                text += f"└─ Expected: +{sig['expected_profit']:.1f}%\n\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Error in /active: {e}")
            await update.message.reply_text(f"❌ შეცდომა: {e}")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /history SYMBOL - კონკრეტული აქტივის ისტორია (მხოლოდ ადმინისთვის)
        """
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ არ ხართ ავტორიზებული.")
            return

        if not context.args:
            await update.message.reply_text("📝 გამოყენება: /history SYMBOL\n\nმაგალითი: /history BTCUSDT")
            return

        try:
            symbol = context.args[0].upper()
            history = self.analytics_db.get_symbol_history(symbol)

            if history['total_signals'] == 0:
                await update.message.reply_text(f"📭 **{symbol}** - ისტორია ცარიელია")
                return

            text = f"📜 **{symbol} TRADING HISTORY:**\n\n"
            text += f"📊 სულ სიგნალები: {history['total_signals']}\n"
            text += f"✅ წარმატებული: {history['wins']}\n"
            text += f"📈 Win Rate: {history['win_rate']:.1f}%\n"
            text += f"💰 საშუალო მოგება: {history['avg_profit']:+.2f}%\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Error in /history: {e}")
            await update.message.reply_text(f"❌ შეცდომა: {e}")

    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /performance - სტრატეგიების შედარება (მხოლოდ ადმინისთვის)
        """
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ არ ხართ ავტორიზებული.")
            return

        try:
            text = "🎯 **STRATEGY PERFORMANCE COMPARISON:**\n\n"

            for strategy in ['long_term', 'scalping', 'opportunistic']:
                perf = self.analytics_db.get_strategy_performance(strategy)

                if perf['total_signals'] == 0:
                    text += f"**{strategy.upper()}:** მონაცემები არ არის\n\n"
                    continue

                text += f"**{strategy.upper()}:**\n"
                text += f"├─ სიგნალები: {perf['total_signals']}\n"
                text += f"├─ Win Rate: {perf['success_rate']:.1f}%\n"
                text += f"├─ Avg Profit: {perf['avg_profit']:+.2f}%\n"
                text += f"├─ საუკეთესო: {perf['best_trade']:+.2f}%\n"
                text += f"├─ უარესი: {perf['worst_trade']:+.2f}%\n"
                text += f"└─ Avg Hold: {perf['avg_hold_hours']:.1f}h\n\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Error in /performance: {e}")
            await update.message.reply_text(f"❌ შეცდომა: {e}")

    async def cmd_recent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /recent - ბოლო სიგნალები (მხოლოდ ადმინისთვის)
        """
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ არ ხართ ავტორიზებული.")
            return

        try:
            limit = 10
            if context.args:
                try:
                    limit = int(context.args[0])
                    limit = min(max(limit, 1), 20)  # 1-20 range
                except:
                    pass

            recent = self.analytics_db.get_recent_signals(limit)

            if not recent:
                await update.message.reply_text("📭 **სიგნალები ჯერ არ არის**")
                return

            text = f"📝 **ბოლო {len(recent)} სიგნალი:**\n\n"

            for sig in recent:
                # Status emoji
                if sig['outcome'] == 'SUCCESS':
                    emoji = "✅"
                elif sig['outcome'] == 'FAILURE':
                    emoji = "❌"
                else:
                    emoji = "⏳"

                # Profit display
                if sig['profit'] is not None:
                    profit_str = f"{sig['profit']:+.2f}%"
                else:
                    profit_str = "Pending"

                text += f"{emoji} **{sig['symbol']}** ({sig['strategy']})\n"
                text += f"   └─ {profit_str} | Conf: {sig['confidence']:.0f}%\n"

            await update.message.reply_text(text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Error in /recent: {e}")
            await update.message.reply_text(f"❌ შეცდომა: {e}")

    # ========================
    # ადმინისტრატორის ფუნქციები
    # ========================
    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: 
            await update.message.reply_text("❌ არ ხართ ავტორიზებული.")
            return

        msg = (
            "👑 **ადმინ პანელი**\n\n"
            "**მომხმარებლის მართვა:**\n"
            "/adduser [user_id] [days] - პრემიუმის მინიჭება\n"
            "/removeuser [user_id] - პრემიუმის გაუქმება\n"
            "/listusers - ყველა მომხმარებელი\n\n"
            "**სტატისტიკა:**\n"
            "/botstats - ბოტის სტატისტიკა\n"
            "/stats - სრული Analytics Dashboard 📊\n"
            "/active - აქტიური სიგნალები\n"
            "/performance - სტრატეგიების შედარება\n"
            "/history [SYMBOL] - აქტივის ისტორია\n"
            "/recent [N] - ბოლო N სიგნალი"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def cmd_adduser(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ადმინი: მომხმარებლის დამატება"""
        if update.effective_user.id != ADMIN_ID: return

        try:
            user_id = int(context.args[0])
            days = int(context.args[1]) if len(context.args) > 1 else 30

            self.add_subscription(user_id, days)
            await update.message.reply_text(
                f"✅ მომხმარებელს `{user_id}` დაემატა {days} დღე.",
                parse_mode='Markdown'
            )

            # შეტყობინება მომხმარებელს
            try:
                await self.bot.send_message(
                    user_id, 
                    f"🎉 თქვენი Premium აქტივირებულია {days} დღით!\n\n"
                    "📊 AI სიგნალები ჩართულია. წარმატებებს! 🚀"
                )
            except:
                pass

        except (IndexError, ValueError):
            await update.message.reply_text("❌ გამოყენება: /adduser [user_id] [days]")

    async def cmd_listusers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ადმინი: მომხმარებლების სია"""
        if update.effective_user.id != ADMIN_ID: return

        active = self.get_active_subscribers()
        inactive = [uid for uid in self.subscriptions.keys() if uid not in active]

        msg = (
            f"👥 **მომხმარებლების სია**\n\n"
            f"✅ აქტიური: {len(active)}\n"
            f"❌ არააქტიური: {len(inactive)}\n"
            f"📊 სულ: {len(self.subscriptions)}\n\n"
        )

        if active:
            msg += "**აქტიური მომხმარებლები:**\n"
            for uid in active[:10]:  # First 10
                expires = self.subscriptions[uid]['expires_at']
                msg += f"• `{uid}` - {expires}\n"

        await update.message.reply_text(msg, parse_mode='Markdown')

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """✅ FIXED: გაფართოებული სტატისტიკა"""
        if update.effective_user.id != ADMIN_ID: return

        stats = getattr(self.trading_engine, 'stats', {})

        # Tier-ების სტატისტიკა
        tier_stats = stats.get('signals_by_tier', {})
        tier_text = "\n".join([
            f"• {tier}: {count}" 
            for tier, count in tier_stats.items() 
            if count > 0
        ]) or "არ არის მონაცემები"

        msg = (
            f"📊 **ბოტის სტატისტიკა**\n\n"
            f"**მომხმარებლები:**\n"
            f"• სულ: {len(self.subscriptions)}\n"
            f"• აქტიური: {len(self.get_active_subscribers())}\n\n"
            f"**სიგნალები:**\n"
            f"• სულ გაგზავნილი: {stats.get('total_signals', 0)}\n"
            f"• წარმატებული: {stats.get('successful_trades', 0)}\n"
            f"• წარუმატებელი: {stats.get('failed_trades', 0)}\n\n"
            f"**Tier-ების მიხედვით:**\n{tier_text}\n\n"
            f"**სისტემა:**\n"
            f"• კრიპტო: {len(CRYPTO)}\n"
            f"• AI Threshold: {AI_ENTRY_THRESHOLD}"
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

        await update.message.reply_text(
            "📸 ფოტო მიღებულია! ადმინისტრატორი განიხილავს უმოკლეს დროში.\n\n"
            "⏳ დაელოდეთ დადასტურებას (ჩვეულებრივ 1-24 საათში)."
        )

        # ადმინთან გაგზავნა დასადასტურებლად
        keyboard = [[
            InlineKeyboardButton("✅ დადასტურება", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ უარყოფა", callback_data=f"reject_{user_id}")
        ]]
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=f"🔄 **გადახდის მოთხოვნა**\n\n👤 @{username} (`{user_id}`)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if update.effective_user.id != ADMIN_ID: 
            await query.answer("❌ არ ხართ ავტორიზებული.")
            return

        action, target_id = query.data.split("_")
        target_id = int(target_id)

        if action == "approve":
            self.add_subscription(target_id)
            await query.edit_message_caption(
                caption=f"✅ **დადასტურებულია**\n\nUser ID: `{target_id}`",
                parse_mode='Markdown'
            )
            await self.bot.send_message(
                target_id, 
                "🎉 **გადახდა დადასტურდა!**\n\n"
                "✅ Premium აქტივირებულია 30 დღით.\n"
                "📊 AI სიგნალები ჩართულია.\n\n"
                "📖 დახმარებისთვის: /guide"
            )
        else:
            await query.edit_message_caption(
                caption=f"❌ **უარყოფილია**\n\nUser ID: `{target_id}`",
                parse_mode='Markdown'
            )
            await self.bot.send_message(
                target_id, 
                "❌ გადახდა უარყოფილია.\n\n"
                "ხარვეზის შემთხვევაში დაგვიკავშირდით: https://t.me/Kagurashinakami"
            )

        await query.answer()

    # ========================
    # სიგნალების დაგზავნა (Broadcasting)
    # ========================
    async def broadcast_signal(self, message, asset):
        """✅ FIXED: იყენებს GUIDE_FOOTER-ს config-დან"""
        import time
        now = time.time()

        # Cooldown დაცვა (config-დან)
        if now - self.last_notifications.get(asset, 0) < NOTIFICATION_COOLDOWN:
            logger.debug(f"⏸️ Cooldown active for {asset}")
            return

        self.last_notifications[asset] = now

        # ✅ დაემატება GUIDE_FOOTER config-დან
        full_message = message + GUIDE_FOOTER

        active_users = self.get_active_subscribers()
        logger.info(f"📤 Broadcasting signal to {len(active_users)} users: {asset}")

        success_count = 0
        fail_count = 0

        for user_id in active_users:
            try:
                await self.bot.send_message(
                    chat_id=user_id, 
                    text=full_message, 
                    parse_mode='Markdown'
                )
                success_count += 1
                await asyncio.sleep(0.05)  # Flood protection
            except Exception as e:
                fail_count += 1
                logger.debug(f"შეცდომა გაგზავნისას {user_id}: {e}")

        logger.info(f"✅ Broadcast complete: {success_count} OK, {fail_count} FAIL")

    # ========================
    # LIFECYCLE მენეჯმენტი
    # ========================
    def setup_handlers(self):
        """✅ ყველა ბრძანების რეგისტრაცია"""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("guide", self.cmd_guide))
        self.application.add_handler(CommandHandler("tiers", self.cmd_tiers))
        self.application.add_handler(CommandHandler("mystatus", self.cmd_mystatus))
        self.application.add_handler(CommandHandler("subscribe", self.cmd_subscribe))

        # ✅ NEW: Analytics commands (Admin only)
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("active", self.cmd_active))
        self.application.add_handler(CommandHandler("history", self.cmd_history))
        self.application.add_handler(CommandHandler("performance", self.cmd_performance))
        self.application.add_handler(CommandHandler("recent", self.cmd_recent))

        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.cmd_admin))
        self.application.add_handler(CommandHandler("adduser", self.cmd_adduser))
        self.application.add_handler(CommandHandler("listusers", self.cmd_listusers))
        self.application.add_handler(CommandHandler("botstats", self.cmd_botstats))

        # Payment handling
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