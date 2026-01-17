import os
import asyncio
import yfinance as yf
import feedparser
import requests
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

# --- კონფიგურაცია ---
TELEGRAM_TOKEN = "8247808058:AAGBsRWw8UOoZHMoulK6dGv-QI5L6A9f9rA"
ADMIN_ID = 6564836899
SUBSCRIPTIONS_FILE = "subscriptions.json"
PAYMENT_REQUESTS_FILE = "payment_requests.json"
KNOWLEDGE_BASE_FILE = "trading_knowledge.json"
PDF_FOLDER = "My-AI-Agent_needs"

# --- ოპტიმიზირებული აქტივები (Yahoo Finance 2026-სთვის) ---
CRYPTO = [
    'BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'XRP-USD', 
    'ADA-USD', 'DOGE-USD', 'TRX-USD', 'DOT-USD', 'LINK-USD',
    'AVAX-USD', 'SHIB-USD', 'LTC-USD', 'BCH-USD', 'UNI-USD',
    'NEAR-USD', 'ICP-USD', 'HBAR-USD', 'ARB-USD', 'OP-USD'
]

STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 
    'BRK-B', 'V', 'JPM', 'UNH', 'MA', 'PG', 'HD', 'AVGO', 
    'ORCL', 'COST', 'NFLX', 'ADBE', 'AMD', 'CRM', 'WMT'
]

COMMODITIES = [
    "GC=F", "SI=F", "CL=F", "NG=F", "DX=F", "HG=F"
]

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

    # --- გაუმჯობესებული სენტიმენტის ფუნქცია (ერორების გარეშე) ---
    async def get_market_sentiment(self):
        sentiment_data = {"fg_index": 50, "fg_class": "Neutral", "market_trend": 0}
        try:
            # Fear & Greed Index
            fg_res = requests.get("https://api.alternative.me/fng/", timeout=7).json()
            if 'data' in fg_res and len(fg_res['data']) > 0:
                sentiment_data["fg_index"] = int(fg_res['data'][0]['value'])
                sentiment_data["fg_class"] = fg_res['data'][0]['value_classification']
        except Exception as e:
            print(f"F&G Index error: {e}")

        try:
            # CoinGecko Global Market (დამატებულია 'data' შემოწმება)
            cg_res = requests.get("https://api.coingecko.com/api/v3/global", timeout=7).json()
            if 'data' in cg_res:
                sentiment_data["market_trend"] = cg_res['data'].get('market_cap_change_percentage_24h_usd', 0)
        except Exception as e:
            print(f"CoinGecko error: {e}")

        return sentiment_data

    def load_trading_knowledge(self):
        knowledge = {"patterns": [], "strategies": [], "indicators": []}
        if os.path.exists(KNOWLEDGE_BASE_FILE):
            try:
                with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
                    kb = json.load(f)
                    print(f"ცოდნა ჩაიტვირთა: {len(kb.get('patterns', []))} პატერნი")
                    return kb
            except: pass

        if not os.path.exists(PDF_FOLDER):
            print(f"საქაღალდე ვერ მოიძებნა: {PDF_FOLDER}")
            return knowledge

        try:
            pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith('.pdf')]
            for pdf_file in pdf_files:
                pdf_path = os.path.join(PDF_FOLDER, pdf_file)
                try:
                    with open(pdf_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        text = "".join([page.extract_text() for page in pdf_reader.pages])
                        knowledge = self.extract_knowledge(text, knowledge)
                except Exception as e:
                    print(f"შეცდომა PDF კითხვისას {pdf_file}: {e}")

            with open(KNOWLEDGE_BASE_FILE, 'w', encoding='utf-8') as f:
                json.dump(knowledge, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"PDF პროცესის შეცდომა: {e}")
        return knowledge

    def extract_knowledge(self, text, knowledge):
        # პატერნების ამოცნობის გამარტივებული ლოგიკა
        keywords = {
            "patterns": ["head and shoulders", "double top", "double bottom", "triangle", "flag", "bullish", "bearish"],
            "strategies": ["strategy", "buy when", "risk management", "entry point"],
            "indicators": ["rsi", "ema", "macd", "bollinger", "fibonacci"]
        }
        for category, kws in keywords.items():
            for kw in kws:
                if kw in text.lower():
                    ctx = self.get_context(text, kw)
                    if ctx and ctx not in knowledge[category]:
                        knowledge[category].append(ctx)
        return knowledge

    def get_context(self, text, keyword, chars=200):
        try:
            idx = text.lower().find(keyword)
            if idx == -1: return None
            return text[max(0, idx-chars//2):min(len(text), idx+chars//2)].strip()
        except: return None

    async def ai_analyze_signal(self, symbol, data):
        score = 0
        reasons = []
        sentiment = await self.get_market_sentiment()

        if data['rsi'] < 30:
            score += 30
            reasons.append("RSI გადაყიდულია (<30)")
        elif data['rsi'] < 40:
            score += 15
            reasons.append("RSI დაბალია (<40)")

        if data['price'] > data['ema200']:
            score += 25
            reasons.append("აღმავალი ტრენდი (Price > EMA200)")

        if data['price'] <= data['bb_low']:
            score += 20
            reasons.append("Bollinger-ის ქვედა ხაზთან შეხება")

        if sentiment['fg_index'] < 30:
            score += 15
            reasons.append(f"ბაზრის შიში ({sentiment['fg_index']}) - ყიდვის შანსი")

        # PDF ცოდნის შემოწმება
        for p in self.trading_knowledge.get("patterns", []):
            if "bullish" in p.lower() and data['rsi'] < 35:
                score += 15
                reasons.append("AI ცოდნა: Bullish Reversal")
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
                    return {int(k): v for k, v in data.items()} if filename == SUBSCRIPTIONS_FILE else data
            return {}
        except: return {}

    def save_json(self, data, filename):
        try:
            save_data = {str(k): v for k, v in data.items()} if filename == SUBSCRIPTIONS_FILE else data
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
        except Exception as e: print(f"შენახვის შეცდომა {filename}: {e}")

    def is_active_subscriber(self, user_id):
        if user_id not in self.subscriptions: return False
        try:
            expires = datetime.strptime(self.subscriptions[user_id]['expires_at'], '%Y-%m-%d').date()
            return datetime.now().date() <= expires
        except: return False

    def add_subscription(self, user_id, days=30):
        expires = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        self.subscriptions[user_id] = {'expires_at': expires, 'activated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        self.save_json(self.subscriptions, SUBSCRIPTIONS_FILE)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.effective_user.username or "მომხმარებელი"
        msg = (
            f"👋 გამარჯობა @{username}!\n\n"
            f"🤖 AI Trading Bot მზად არის.\n"
            f"📊 ვაკონტროლებ {len(ASSETS)} აქტივს.\n\n"
            f"📌 ბრძანებები:\n"
            f"/subscribe - გამოწერა (150₾)\n"
            f"/mystatus - სტატუსის შემოწმება\n"
            f"/stop - შეტყობინებების გათიშვა\n\n"
            f"❓ დახმარება: @Kagurashinakami"
        )
        await update.message.reply_text(msg)

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if self.is_active_subscriber(user_id):
            await update.message.reply_text(f"✅ თქვენ უკვე გაქვთ აქტიური გამოწერა!\n📅 ვადა: {self.subscriptions[user_id]['expires_at']}")
            return

        msg = (
            "💳 გამოწერის ინსტრუქცია:\n\n"
            "1️⃣ გადაიხადეთ 150₾\n"
            "🏦 ბანკი: საქართველოს ბანკი\n"
            "📋 IBAN: GE95BG0000000528102311\n"
            "👤 მიმღები: ლ.გ\n\n"
            "2️⃣ გამოაგზავნეთ ჩეკის ფოტო ამ ჩატში.\n"
            "⏱️ ადმინისტრატორი გააქტიურებს 24 საათში."
        )
        await update.message.reply_text(msg)

    async def cmd_mystatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if self.is_active_subscriber(user_id):
            expires = self.subscriptions[user_id]['expires_at']
            await update.message.reply_text(f"✅ სტატუსი: აქტიური\n📅 ვადა: {expires}\n🤖 AI ანალიზი ჩართულია.")
        else:
            await update.message.reply_text("⚠️ სტატუსი: არააქტიური\nგააქტიურებისთვის: /subscribe")

    async def handle_payment_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "NoName"
        self.payment_requests[str(user_id)] = {'status': 'pending', 'at': datetime.now().isoformat()}
        self.save_json(self.payment_requests, PAYMENT_REQUESTS_FILE)

        await update.message.reply_text("📸 ფოტო მიღებულია. ადმინისტრატორი განიხილავს თქვენს მოთხოვნას.")

        keyboard = [[InlineKeyboardButton("✅ დადასტურება", callback_data=f"approve_{user_id}"), 
                     InlineKeyboardButton("❌ უარყოფა", callback_data=f"reject_{user_id}")]]
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, 
                                   caption=f"🔄 გადახდის მოთხოვნა:\n👤 @{username}\n🆔 `{user_id}`", 
                                   reply_markup=InlineKeyboardMarkup(keyboard))

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if update.effective_user.id != ADMIN_ID: return

        action, target_id = query.data.split("_")
        target_id = int(target_id)

        if action == "approve":
            self.add_subscription(target_id)
            await query.edit_message_caption("✅ გადახდა დადასტურდა. მომხმარებელი გააქტიურდა.")
            await self.bot.send_message(target_id, "🎉 მილოცავთ! თქვენი გამოწერა გააქტიურდა 30 დღით.\n🤖 ახლა თქვენ მიიღებთ ყველა AI სიგნალს.")
        else:
            await query.edit_message_caption("❌ გადახდა უარყოფილია.")
            await self.bot.send_message(target_id, "❌ თქვენი გადახდა ვერ დადასტურდა. დაუკავშირდით @Kagurashinakami")

    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        await update.message.reply_text("👑 ადმინ პანელი:\n/listusers - სიის ნახვა\n/adduser [ID] - დამატება\n/botstats - სტატისტიკა")

    async def cmd_adduser(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        try:
            tid = int(context.args[0])
            self.add_subscription(tid)
            await update.message.reply_text(f"✅ მომხმარებელი {tid} დამატებულია.")
        except: await update.message.reply_text("❌ ფორმატი: /adduser [ID]")

    async def cmd_listusers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        msg = "👥 მომხმარებლები:\n"
        for uid, d in self.subscriptions.items():
            msg += f"🆔 {uid} | 📅 {d['expires_at']}\n"
        await update.message.reply_text(msg or "სია ცარიელია")

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID: return
        active = sum(1 for u in self.subscriptions if self.is_active_subscriber(u))
        msg = f"📊 სტატისტიკა:\n✅ აქტიური: {active}\n📡 მონიტორინგი: {len(ASSETS)} აქტივი\n📈 პოზიციები: {len(self.active_positions)}"
        await update.message.reply_text(msg)

    async def fetch_data(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1mo", interval=INTERVAL)
            if len(df) < 50: return None # მინიმალური მონაცემები ანალიზისთვის

            close = df['Close']
            return {
                "price": close.iloc[-1],
                "ema200": EMAIndicator(close, window=200 if len(close)>=200 else len(close)).ema_indicator().iloc[-1],
                "rsi": RSIIndicator(close).rsi().iloc[-1],
                "bb_low": BollingerBands(close).bollinger_lband().iloc[-1],
                "bb_high": BollingerBands(close).bollinger_hband().iloc[-1]
            }
        except: return None

    async def analyze_and_notify(self):
        active_users = [u for u in self.subscriptions if self.is_active_subscriber(u)]
        if not active_users: return

        sentiment = await self.get_market_sentiment()
        print(f"--- ციკლი დაიწყო: {datetime.now().strftime('%H:%M')} | F&G: {sentiment['fg_index']} ---")

        for asset in ASSETS:
            data = await self.fetch_data(asset)
            if not data: continue

            if asset in self.active_positions:
                await self.check_exit(asset, data)
            else:
                score, reasons = await self.ai_analyze_signal(asset, data)
                if score >= 50:
                    self.active_positions[asset] = {"entry": data['price'], "time": time.time()}
                    reason_str = "\n".join([f"• {r}" for r in reasons])
                    msg = (
                        f"🟢 AI ყიდვის სიგნალი: {asset}\n\n"
                        f"💵 ფასი: ${data['price']:.2f}\n"
                        f"📊 RSI: {data['rsi']:.1f}\n"
                        f"🧠 AI ქულა: {score}/100\n\n"
                        f"📌 მიზეზები:\n{reason_str}\n\n"
                        f"🎯 მიზანი: +{TAKE_PROFIT_PERCENT}%\n"
                        f"🛑 სტოპი: -{STOP_LOSS_PERCENT}%"
                    )
                    await self.broadcast(msg, asset)
            await asyncio.sleep(ASSET_DELAY)

    async def check_exit(self, asset, data):
        entry = self.active_positions[asset]['entry']
        curr = data['price']
        profit = ((curr - entry) / entry) * 100

        exit_now = False
        reason = ""

        if profit >= TAKE_PROFIT_PERCENT:
            exit_now, reason = True, f"✅ Take Profit (+{profit:.2f}%)"
        elif profit <= -STOP_LOSS_PERCENT:
            exit_now, reason = True, f"🛑 Stop Loss ({profit:.2f}%)"
        elif data['rsi'] > 75:
            exit_now, reason = True, "📈 RSI გადამეტებული ყიდვა (>75)"

        if exit_now:
            msg = (
                f"🔴 AI გაყიდვის სიგნალი: {asset}\n\n"
                f"💰 მოგება/ზარალი: {profit:+.2f}%\n"
                f"💵 გასვლის ფასი: ${curr:.2f}\n"
                f"📌 მიზეზი: {reason}"
            )
            del self.active_positions[asset]
            await self.broadcast(msg, asset)

    async def broadcast(self, msg, asset):
        now = time.time()
        if now - self.last_notifications.get(asset, 0) < NOTIFICATION_COOLDOWN: return
        self.last_notifications[asset] = now

        for uid in list(self.subscriptions.keys()):
            if self.is_active_subscriber(uid):
                try: 
                    await self.bot.send_message(chat_id=uid, text=msg)
                    await asyncio.sleep(0.1)
                except: pass

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
            self.save_json(self.subscriptions, SUBSCRIPTIONS_FILE)
            await update.message.reply_text("👋 შეტყობინებები გაუქმებულია. დაბრუნებისთვის გამოიყენეთ /subscribe")

    async def start(self):
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        print("🚀 ბოტი გაშვებულია!")

        while True:
            await self.analyze_and_notify()
            await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    bot = AITradingBot()
    asyncio.run(bot.start())