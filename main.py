import os
import asyncio
import yfinance as yf
import feedparser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import time
from datetime import datetime, timedelta
import json
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

try:
    import PyPDF2
except ImportError:
    print("PyPDF2 not installed - PDF features disabled")

TELEGRAM_TOKEN = "8247808058:AAG9ZxIatcq7vGfgn10EWxvW5NYgInB8ok8"
ADMIN_ID = 6564836899
SUBSCRIPTIONS_FILE = "subscriptions.json"
PAYMENT_REQUESTS_FILE = "payment_requests.json"
KNOWLEDGE_BASE_FILE = "trading_knowledge.json"
PDF_FOLDER = "My-AI-Agent_needs"

CRYPTO = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "DOT-USD", "AVAX-USD", "MATIC-USD", "LINK-USD", "UNI-USD", "ATOM-USD", "LTC-USD", "XLM-USD", "BCH-USD", "ALGO-USD", "VET-USD", "ICP-USD", "FIL-USD", "HBAR-USD", "APT-USD", "TRX-USD", "NEAR-USD", "INJ-USD", "ARB-USD", "OP-USD", "RNDR-USD", "IMX-USD", "PEPE-USD", "TIA-USD", "SEI-USD", "SUI-USD", "KAS-USD", "JTO-USD", "PYTH-USD", "BLUR-USD", "LDO-USD", "RUNE-USD", "FET-USD"]
STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "TSM", "JPM", "BAC", "UNH", "JNJ", "WMT", "HD", "XOM", "CVX", "AMD", "INTC", "ASML", "SMCI", "AVGO", "ARM", "LLY", "NVO", "COST", "PANW", "CRWD", "UBER"]
COMMODITIES = ["GC=F", "SI=F", "CL=F", "NG=F", "ZC=F", "ZW=F", "ZS=F", "ES=F", "NQ=F", "DX=F", "6E=F", "HG=F", "ZN=F", "ZF=F", "VX=F", "RTY=F", "YM=F", "PL=F", "PA=F", "KC=F", "SB=F", "USO"]
ASSETS = CRYPTO + STOCKS + COMMODITIES

INTERVAL = "1h"
SCAN_INTERVAL = 180
ASSET_DELAY = 3
NOTIFICATION_COOLDOWN = 3600
STOP_LOSS_PERCENT = 5.0
TAKE_PROFIT_PERCENT = 10.0
MAX_HOLD_HOURS = 72
RSS_FEEDS = ["https://cryptopanic.com/news/rss/", "https://cointelegraph.com/rss", "https://www.investing.com/rss/news.rss"]

class AITradingBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.bot = self.application.bot
        self.active_positions = {}
        self.last_notifications = {}
        self.request_count = 0
        self.start_time = time.time()
        self.subscriptions = self.load_json(SUBSCRIPTIONS_FILE)
        self.payment_requests = self.load_json(PAYMENT_REQUESTS_FILE)
        self.trading_knowledge = self.load_trading_knowledge()
        self.setup_handlers()

    def load_trading_knowledge(self):
        if os.path.exists(KNOWLEDGE_BASE_FILE):
            try:
                with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
                    kb = json.load(f)
                    print(f"Knowledge loaded: {len(kb.get('patterns', []))} patterns")
                    return kb
            except:
                pass
        knowledge = {"patterns": [], "strategies": [], "indicators": []}
        if not os.path.exists(PDF_FOLDER):
            print(f"PDF folder not found: {PDF_FOLDER}")
            return knowledge
        try:
            pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith('.pdf')]
            print(f"Loading {len(pdf_files)} PDFs...")
            for pdf_file in pdf_files:
                pdf_path = os.path.join(PDF_FOLDER, pdf_file)
                try:
                    with open(pdf_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        text = ""
                        for page in pdf_reader.pages:
                            text += page.extract_text()
                        knowledge = self.extract_knowledge(text, knowledge)
                        print(f"Loaded: {pdf_file}")
                except Exception as e:
                    print(f"Error {pdf_file}: {e}")
            with open(KNOWLEDGE_BASE_FILE, 'w', encoding='utf-8') as f:
                json.dump(knowledge, f, indent=2, ensure_ascii=False)
            print(f"Total: {len(knowledge['patterns'])} patterns, {len(knowledge['strategies'])} strategies")
        except Exception as e:
            print(f"PDF error: {e}")
        return knowledge

    def extract_knowledge(self, text, knowledge):
        text_lower = text.lower()
        patterns_kw = ["head and shoulders", "double top", "double bottom", "triangle", "flag", "wedge", "bullish", "bearish", "reversal", "breakout", "support", "resistance"]
        for kw in patterns_kw:
            if kw in text_lower:
                context = self.get_context(text, kw, 200)
                if context and context not in knowledge["patterns"]:
                    knowledge["patterns"].append(context)
        strategies_kw = ["strategy", "approach", "buy when", "sell when", "entry point", "exit point", "risk management", "position sizing"]
        for kw in strategies_kw:
            if kw in text_lower:
                context = self.get_context(text, kw, 200)
                if context and context not in knowledge["strategies"]:
                    knowledge["strategies"].append(context)
        indicators_kw = ["rsi", "relative strength", "moving average", "ema", "sma", "macd", "bollinger", "volume", "stochastic", "fibonacci"]
        for kw in indicators_kw:
            if kw in text_lower:
                context = self.get_context(text, kw, 150)
                if context and context not in knowledge["indicators"]:
                    knowledge["indicators"].append(context)
        return knowledge

    def get_context(self, text, keyword, chars=200):
        try:
            index = text.lower().find(keyword)
            if index == -1:
                return None
            start = max(0, index - chars // 2)
            end = min(len(text), index + chars // 2)
            return text[start:end].strip()
        except:
            return None

    def ai_analyze_signal(self, symbol, data):
        score = 0
        reasons = []
        if data['rsi'] < 30:
            score += 30
            reasons.append("RSI oversold (<30)")
            for k in self.trading_knowledge.get("indicators", []):
                if "rsi" in k.lower() and ("oversold" in k.lower() or "below 30" in k.lower()):
                    score += 10
                    reasons.append("AI: RSI oversold strategy")
                    break
        elif data['rsi'] < 40:
            score += 15
            reasons.append("RSI low (<40)")
        if data['price'] > data['ema200']:
            score += 25
            reasons.append("Uptrend (price > EMA200)")
            for k in self.trading_knowledge.get("strategies", []):
                if "trend" in k.lower() or "moving average" in k.lower():
                    score += 15
                    reasons.append("AI: Trend following")
                    break
        if data['price'] <= data['bb_low']:
            score += 20
            reasons.append("Bollinger lower band touch")
            for k in self.trading_knowledge.get("patterns", []):
                if "bollinger" in k.lower() or "bounce" in k.lower():
                    score += 10
                    reasons.append("AI: Bollinger bounce pattern")
                    break
        for p in self.trading_knowledge.get("patterns", []):
            if "bullish" in p.lower() and "reversal" in p.lower():
                if data['rsi'] < 35 and data['price'] > data['ema200']:
                    score += 15
                    reasons.append("AI: Bullish reversal pattern")
                    break
        return score, reasons

    def setup_handlers(self):
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

    def load_json(self, filename):
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                    if filename == SUBSCRIPTIONS_FILE:
                        return {int(k): v for k, v in data.items()}
                    return data
            return {}
        except:
            return {}

    def save_json(self, data, filename):
        try:
            if filename == SUBSCRIPTIONS_FILE:
                data = {str(k): v for k, v in data.items()}
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving {filename}: {e}")

    def is_active_subscriber(self, user_id):
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
        expires = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        self.subscriptions[user_id] = {'expires_at': expires, 'activated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'plan': 'premium'}
        self.save_json(self.subscriptions, SUBSCRIPTIONS_FILE)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.effective_user.username or "მომხმარებელი"
        ai_info = f"🧠 AI: {len(self.trading_knowledge.get('patterns', []))} patterns" if self.trading_knowledge.get('patterns') else "🤖"
        welcome_msg = f"👋 გამარჯობა @{username}!\n\n{ai_info} AI Trading Bot\n\n📊 მონიტორინგი:\n• {len(CRYPTO)} კრიპტოვალუტა\n• {len(STOCKS)} აქცია\n• {len(COMMODITIES)} საქონელი\n\n💰 ფასი: 150₾ / თვე\n\n📌 ბრძანებები:\n/subscribe - გამოწერა\n/mystatus - სტატუსი\n/stop - გაუქმება\n\n❓ კითხვები? https://t.me/Kagurashinakami"
        await update.message.reply_text(welcome_msg)

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if self.is_active_subscriber(user_id):
            expires = self.subscriptions[user_id]['expires_at']
            await update.message.reply_text(f"✅ უკვე გაქვთ აქტიური subscription!\n📅 იწურება: {expires}")
            return
        payment_msg = "💳 გამოწერის ინსტრუქცია:\n\n1️⃣ გადაიხადეთ 150₾\n🏦 ბანკი: საქართველოს ბანკი\n📋 IBAN: GE95BG0000000528102311\n👤 მიმღები: ლ.გ\n\n2️⃣ გადახდის შემდეგ:\n• გამოაგზავნეთ screenshot ამ ჩატში\n• ან პირადში: https://t.me/Kagurashinakami\n\n3️⃣ ჩვენ გავააქტიურებთ subscription-ს\n⏱️ პროცესი: 24 საათში\n\n❓ კითხვები? https://t.me/Kagurashinakami"
        await update.message.reply_text(payment_msg)

    async def cmd_mystatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if self.is_active_subscriber(user_id):
            expires = self.subscriptions[user_id]['expires_at']
            days_left = (datetime.strptime(expires, '%Y-%m-%d').date() - datetime.now().date()).days
            status_msg = f"✅ აქტიური subscription\n\n📅 იწურება: {expires}\n⏳ დარჩენილი: {days_left} დღე\n📊 სტატუსი: Active\n🧠 AI: აქტიური\n\n🤖 მიიღებთ ყველა სიგნალს!"
        else:
            status_msg = "⚠️ არააქტიური subscription\n\nგააქტიურება: /subscribe"
        await update.message.reply_text(status_msg)

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
            self.save_json(self.subscriptions, SUBSCRIPTIONS_FILE)
            await update.message.reply_text("👋 subscription გაუქმებულია.\n\nმადლობა! /subscribe - ხელახალი გააქტიურება")
        else:
            await update.message.reply_text("ℹ️ არ გაქვთ აქტიური subscription.")

    async def handle_payment_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "No username"
        self.payment_requests[str(user_id)] = {'username': username, 'timestamp': datetime.now().isoformat(), 'status': 'pending', 'photo_id': update.message.photo[-1].file_id if update.message.photo else None}
        self.save_json(self.payment_requests, PAYMENT_REQUESTS_FILE)
        await update.message.reply_text("📸 გადახდის ფოტო მიღებულია!\n\nადმინისტრატორი გადაამოწმებს და გაააქტიურებს subscription-ს.\n⏱️ პროცესი: 24 საათში.\n\n❓ კითხვები? https://t.me/Kagurashinakami")
        keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            if update.message.photo:
                await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=f"🔄 ახალი გადახდის მოთხოვნა\n\n👤 @{username}\n🆔 {user_id}\n⏰ {datetime.now().strftime('%H:%M:%S')}", reply_markup=reply_markup)
        except Exception as e:
            print(f"Failed to forward to admin: {e}")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        self.add_subscription(user_id, days=30)
        if str(user_id) in self.payment_requests:
            self.payment_requests[str(user_id)]['status'] = 'approved'
            self.save_json(self.payment_requests, PAYMENT_REQUESTS_FILE)
        await query.edit_message_text(f"✅ გადახდა დადასტურებულია!\n\n👤 {user_id}\n⏰ {datetime.now().strftime('%H:%M:%S')}\n\nSubscription გააქტიურდა 30 დღით.")
        try:
            await self.bot.send_message(chat_id=user_id, text="🎉 თქვენი გადახდა დადასტურდა!\n\n✅ Subscription გააქტიურდა 30 დღით.\n🤖 ახლა მიიღებთ ყველა AI სიგნალს.\n\n/mystatus - სტატუსი")
        except:
            pass

    async def reject_payment(self, query, user_id):
        if str(user_id) in self.payment_requests:
            self.payment_requests[str(user_id)]['status'] = 'rejected'
            self.save_json(self.payment_requests, PAYMENT_REQUESTS_FILE)
        await query.edit_message_text(f"❌ გადახდა უარყოფილია\n\n👤 {user_id}\n⏰ {datetime.now().strftime('%H:%M:%S')}")
        try:
            await self.bot.send_message(chat_id=user_id, text="❌ თქვენი გადახდა უარყოფილია\n\nდაუკავშირდით: https://t.me/Kagurashinakami")
        except:
            pass

    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("🚫 არ გაქვთ უფლება!")
            return
        ai_stats = f"• ნიმუშები: {len(self.trading_knowledge.get('patterns', []))}\n• სტრატეგიები: {len(self.trading_knowledge.get('strategies', []))}" if self.trading_knowledge else "• AI არ არის ჩატვირთული"
        admin_msg = f"👑 ადმინის პანელი\n\n📋 ბრძანებები:\n/adduser [ID] [დღეები] - ახალი user\n/listusers - ყველა user\n/botstats - სტატისტიკა\n\n🧠 AI სტატუსი:\n{ai_stats}\n\n💳 გადახდის ფოტოებზე:\nგამოიყენეთ ღილაკები"
        await update.message.reply_text(admin_msg)

    async def cmd_adduser(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await update.message.reply_text(f"✅ მომხმარებელი დაემატა!\n🆔 {target_id}\n📅 {days} დღე")
        except Exception as e:
            await update.message.reply_text(f"❌ შეცდომა: {e}")

    async def cmd_listusers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        users_list += f"👥 სულ: {len(self.subscriptions)}\n✅ აქტიური: {active_count}\n💰 შემოსავალი: {active_count * 150}₾/თვე"
        await update.message.reply_text(users_list)

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.message.reply_text("🚫 არ გაქვთ უფლება!")
            return
        active_users = sum(1 for uid in self.subscriptions if self.is_active_subscriber(uid))
        pending_payments = sum(1 for req in self.payment_requests.values() if req.get('status') == 'pending')
        ai_info = f"🧠 AI ცოდნა:\n• ნიმუშები: {len(self.trading_knowledge.get('patterns', []))}\n• სტრატეგიები: {len(self.trading_knowledge.get('strategies', []))}\n\n" if self.trading_knowledge.get('patterns') else ""
        stats_msg = f"📊 ბოტის სტატისტიკა\n\n👥 მომხმარებლები: {len(self.subscriptions)}\n✅ აქტიური: {active_users}\n💳 გადახდის მოთხოვნები: {pending_payments}\n📈 აქტიური პოზიციები: {len(self.active_positions)}\n📡 მონიტორინგი: {len(ASSETS)} აქტივი\n⏱️ ციკლი: ~{len(ASSETS) * ASSET_DELAY / 60:.1f}წთ\n\n{ai_info}💰 შემოსავალი: {active_users * 150}₾/თვე"
        await update.message.reply_text(stats_msg)

    def get_asset_type(self, symbol):
        if symbol in CRYPTO:
            return "💎 CRYPTO"
        elif symbol in STOCKS:
            return "📈 STOCK"
        elif symbol in COMMODITIES:
            return "🏆 COMMODITY"
        return "📊 ASSET"

    async def get_comprehensive_news(self, asset_name):
        negative_impact = 0
        keywords = ['crash', 'hacked', 'scam', 'fraud', 'lawsuit', 'bankruptcy', 'bearish', 'plunge', 'collapse', 'ban']
        for url in RSS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    title = entry.get('title', '').lower()
                    summary = entry.get('summary', '').lower()
                    content = title + ' ' + summary
                    if asset_name.lower() in content:
                        if any(word in content for word in keywords):
                            negative_impact += 1
            except:
                continue
        return negative_impact == 0

    async def fetch_data(self, symbol):
        try:
            self.request_count += 1
            if self.request_count > 50 and (time.time() - self.start_time) < 60:
                await asyncio.sleep(10)
                self.request_count = 0
                self.start_time = time.time()
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1mo", interval=INTERVAL)
            if len(df) < 200:
                return None
            close = df['Close']
            ema200 = EMAIndicator(close, window=200).ema_indicator().iloc[-1]
            rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
            bb = BollingerBands(close, window=20, window_dev=2)
            return {"price": close.iloc[-1], "ema200": ema200, "rsi": rsi, "bb_low": bb.bollinger_lband().iloc[-1], "bb_high": bb.bollinger_hband().iloc[-1]}
        except Exception as e:
            print(f"Error {symbol}: {e}")
            return None

    async def analyze_and_notify(self):
        active_count = sum(1 for uid in self.subscriptions if self.is_active_subscriber(uid))
        if active_count == 0:
            print("⏸️ No subscribers - scanning paused")
            return
        print(f"\n🧠 AI Scan: {len(ASSETS)} assets, Subscribers: {active_count}")
        for asset in ASSETS:
            data = await self.fetch_data(asset)
            if not data:
                await asyncio.sleep(ASSET_DELAY)
                continue
            if asset in self.active_positions:
                await self.check_exit_conditions(asset, data)
            else:
                ai_score, ai_reasons = self.ai_analyze_signal(asset, data)
                if ai_score >= 50:
                    is_clean = await self.get_comprehensive_news(asset)
                    if is_clean:
                        self.active_positions[asset] = {"entry_price": data['price'], "entry_time": time.time()}
                        asset_type = self.get_asset_type(asset)
                        reasons_text = "\n".join([f"• {r}" for r in ai_reasons[:4]])
                        msg = f"🟢 AI იყიდე: {asset} [{asset_type}]\n\n💵 ფასი: ${data['price']:.2f}\n📊 RSI: {data['rsi']:.1f}\n📈 EMA200: ${data['ema200']:.2f}\n🧠 AI Score: {ai_score}/100\n\n📌 AI მიზეზები:\n{reasons_text}\n\n🎯 Risk:\n🔴 Stop-Loss: -{STOP_LOSS_PERCENT}%\n🟢 Take-Profit: +{TAKE_PROFIT_PERCENT}%"
                        await self.broadcast_signal(msg, asset)
            await asyncio.sleep(ASSET_DELAY)
        print(f"Cycle complete")

    async def check_exit_conditions(self, asset, data):
        position = self.active_positions[asset]
        entry_price = position['entry_price']
        current_price = data['price']
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        hours_held = (time.time() - position['entry_time']) / 3600

        should_exit = False
        exit_reason = ""

        # Stop loss check
        if profit_percent <= -STOP_LOSS_PERCENT:
            should_exit = True
            exit_reason = f"🔴 STOP-LOSS (-{abs(profit_percent):.2f}%)"

        # Take profit check
        if not should_exit and profit_percent >= TAKE_PROFIT_PERCENT:
            should_exit = True
            exit_reason = f"🟢 TAKE-PROFIT (+{profit_percent:.2f}%)"

        elif not should_exit and profit_percent < -3 and data["rsi"] < 30:
            should_exit = True
            exit_reason = f"⚠️ გადაჭარბებული ვარდნა (-{abs(profit_percent):.2f}%, RSI: {data['rsi']:.1f})"

        elif not should_exit and hours_held >= MAX_HOLD_HOURS:
            should_exit = True
            exit_reason = f"⏰ დროის ლიმიტი ({MAX_HOLD_HOURS}ს)"

        elif not should_exit and data["rsi"] > 70:
            should_exit = True
            exit_reason = "📈 RSI ძალიან overbought (>70)"

        elif not should_exit and data["price"] >= data["bb_high"] and data["rsi"] > 60:
            should_exit = True
            exit_reason = "📈 ბოლინჯერი + RSI (გაყიდვის სიგნალი)"

        if not should_exit:
            for k in self.trading_knowledge.get("patterns", []):
                if "bearish" in k.lower() and "reversal" in k.lower():
                    if data["rsi"] > 65:
                        should_exit = True
                        exit_reason = "🧠 AI: Bearish reversal pattern"
                        break

        if not should_exit and profit_percent > 15:
            trailing_stop = entry_price * 1.10
            if current_price < trailing_stop:
                should_exit = True
                exit_reason = "📊 Trailing stop (10% from peak)"

        if should_exit:
            balance_1usd = 1.0 * (1 + (profit_percent / 100))
            asset_type = self.get_asset_type(asset)
            emoji = "🔴" if profit_percent < 0 else "🟢"

            msg = (
                f"{emoji} გაყიდე: {asset} [{asset_type}]\n\n"
                f"📊 შესვლა: ${entry_price:.2f}\n"
                f"📊 გასვლა: ${current_price:.2f}\n"
                f"💰 მოგება: {profit_percent:+.2f}%\n"
                f"💵 1$-ის ბალანსი: ${balance_1usd:.4f}\n\n"
                f"📌 მიზეზი: {exit_reason}"
            )

            del self.active_positions[asset]
            await self.broadcast_signal(msg, asset)
            print(f"SELL signal - profit: {profit_percent:.2f}%")

    async def broadcast_signal(self, message, asset):
        now = time.time()
        if now - self.last_notifications.get(asset, 0) < NOTIFICATION_COOLDOWN:
            return

        self.last_notifications[asset] = now
        success_count = 0
        failed_count = 0

        for user_id in list(self.subscriptions.keys()):
            if not self.is_active_subscriber(user_id):
                continue
            try:
                await self.bot.send_message(chat_id=user_id, text=message)
                success_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                failed_count += 1
                print(f"Failed to send to {user_id}: {e}")

        print(f"Broadcast: {success_count} sent, {failed_count} failed")

    async def start(self):
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        ai_info = (
            f"{len(self.trading_knowledge.get('patterns', []))} patterns"
            if self.trading_knowledge.get("patterns")
            else "base"
        )

        startup_msg = (
            "💎 AI Trading Bot active\n"
            f"🧠 AI: {ai_info}\n\n"
            "📊 Monitoring:\n"
            f"🔸 {len(CRYPTO)} crypto\n"
            f"🔸 {len(STOCKS)} stocks\n"
            f"🔸 {len(COMMODITIES)} commodities\n"
            "━━━━━━━━━━━━━━━━\n"
            f"📡 Total: {len(ASSETS)} assets\n"
            f"⏱️ Cycle: ~{len(ASSETS) * ASSET_DELAY / 60:.0f}min\n"
            f"👥 Subscribers: {len(self.subscriptions)}\n\n"
            "🚀 AI-powered analysis active!"
        )

        for user_id in self.subscriptions:
            try:
                await self.bot.send_message(chat_id=user_id, text=startup_msg)
            except:
                pass

        print(startup_msg)
        print("\n" + "=" * 50 + "\n")

        while True:
            await self.analyze_and_notify()
            print(f"Pause {SCAN_INTERVAL}s...\n")
            await asyncio.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    print("🚀 AI Trading Bot starting...\n")
    bot = AITradingBot()
    asyncio.run(bot.start())