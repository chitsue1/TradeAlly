import os
import asyncio
import aiohttp
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
from collections import defaultdict
import logging

try:
    import PyPDF2
except ImportError:
    print("PyPDF2 not installed - PDF features disabled")

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- კონფიგურაცია ---
TELEGRAM_TOKEN = "8247808058:AAGBsRWw8UOoZHMoulK6dGv-QI5L6A9f9rA"
ADMIN_ID = 6564836899
SUBSCRIPTIONS_FILE = "subscriptions.json"
PAYMENT_REQUESTS_FILE = "payment_requests.json"
KNOWLEDGE_BASE_FILE = "trading_knowledge.json"
PDF_FOLDER = "My-AI-Agent_needs"
CACHE_FILE = "market_cache.json"

# --- განახლებული აქტივები (გადამოწმებული Yahoo Finance) ---
CRYPTO = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
    "ADA-USD", "DOGE-USD", "DOT-USD", "LINK-USD",
    "AVAX-USD", "SHIB-USD", "LTC-USD", "BCH-USD",
    "UNI-USD", "NEAR-USD", "ICP-USD", "HBAR-USD",
    "ARB-USD", "OP-USD"
]

STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "BRK-B", "V", "JPM", "UNH", "MA", "PG", "HD",
    "AVGO", "ORCL", "COST", "NFLX", "ADBE", "AMD",
    "CRM", "WMT", "LLY", "BAC", "XOM", "PFE", "DIS"
]

COMMODITIES = [
    "GC=F", "SI=F", "CL=F", "NG=F", "ZC=F", "ZW=F", 
    "ES=F", "NQ=F", "DX=F", "HG=F"
]

ASSETS = CRYPTO + STOCKS + COMMODITIES

# --- კონფიგურაცია - გამართული ---
INTERVAL = "1h"
SCAN_INTERVAL = 300  # 5 წუთი
ASSET_DELAY = 2  # Yahoo delay შემცირებული
NOTIFICATION_COOLDOWN = 7200  # 2 საათი
STOP_LOSS_PERCENT = 5.0
TAKE_PROFIT_PERCENT = 10.0
MAX_HOLD_HOURS = 72
RSS_CACHE_TIME = 1800  # 30 წუთი RSS cache

# Rate limiting
MAX_YAHOO_REQUESTS_PER_MINUTE = 30
MAX_SENTIMENT_REQUESTS_PER_HOUR = 40

class RateLimiter:
    """Smart rate limiter with exponential backoff"""
    def __init__(self, max_per_minute=30):
        self.max_per_minute = max_per_minute
        self.requests = []
        self.backoff_until = 0

    async def wait_if_needed(self):
        now = time.time()

        # Backoff mode
        if now < self.backoff_until:
            wait_time = self.backoff_until - now
            logger.warning(f"⏸️ Rate limit backoff: {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            return

        # Clean old requests
        self.requests = [t for t in self.requests if now - t < 60]

        if len(self.requests) >= self.max_per_minute:
            wait_time = 60 - (now - self.requests[0]) + 1
            logger.info(f"⏱️ Rate limit: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            self.requests = []

        self.requests.append(now)

    def trigger_backoff(self, seconds=300):
        """Trigger exponential backoff on API errors"""
        self.backoff_until = time.time() + seconds
        logger.error(f"🚨 API Error - Backoff {seconds}s")

class MarketCache:
    """Cache system for reducing API calls"""
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        self.cache = self.load_cache()
        self.sentiment_cache = {"data": None, "timestamp": 0}
        self.news_cache = {}

    def load_cache(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def save_cache(self):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            logger.error(f"Cache save error: {e}")

    def get_sentiment(self):
        """Get cached sentiment (30min TTL)"""
        if time.time() - self.sentiment_cache["timestamp"] < 1800:
            return self.sentiment_cache["data"]
        return None

    def set_sentiment(self, data):
        self.sentiment_cache = {"data": data, "timestamp": time.time()}

    def get_news(self, asset):
        """Get cached news (30min TTL)"""
        cache_key = asset
        if cache_key in self.news_cache:
            if time.time() - self.news_cache[cache_key]["timestamp"] < RSS_CACHE_TIME:
                return self.news_cache[cache_key]["data"]
        return None

    def set_news(self, asset, is_clean):
        self.news_cache[asset] = {"data": is_clean, "timestamp": time.time()}

class AITradingBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.bot = self.application.bot
        self.active_positions = {}
        self.last_notifications = {}
        self.subscriptions = self.load_json(SUBSCRIPTIONS_FILE)
        self.payment_requests = self.load_json(PAYMENT_REQUESTS_FILE)
        self.trading_knowledge = self.load_trading_knowledge()

        # Rate limiters
        self.yahoo_limiter = RateLimiter(MAX_YAHOO_REQUESTS_PER_MINUTE)
        self.sentiment_limiter = RateLimiter(MAX_SENTIMENT_REQUESTS_PER_HOUR // 60)

        # Cache system
        self.cache = MarketCache()

        # Stats
        self.stats = {
            "total_signals": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_profit_percent": 0.0
        }

        self.setup_handlers()

    def get_json_with_headers(self, url, proxy=None, timeout=30):
        """Custom JSON fetcher with proper headers"""
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(url, headers=headers, proxies=proxy, timeout=timeout)
        return response.json()

    # --- ბაზრის სენტიმენტი (async + cache + retry) ---
    async def get_market_sentiment(self):
        """Async sentiment with caching and error handling"""
        # Check cache first
        cached = self.cache.get_sentiment()
        if cached:
            return cached

        await self.sentiment_limiter.wait_if_needed()

        try:
            async with aiohttp.ClientSession() as session:
                # Fear & Greed with timeout
                try:
                    async with session.get(
                        "https://api.alternative.me/fng/",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        fg_data = await response.json()
                        fg_val = int(fg_data['data'][0]['value'])
                        fg_class = fg_data['data'][0]['value_classification']
                except Exception as e:
                    logger.warning(f"Fear & Greed API error: {e}")
                    fg_val, fg_class = 50, "ნეიტრალური"

                # CoinGecko with timeout
                try:
                    async with session.get(
                        "https://api.coingecko.com/api/v3/global",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        cg_data = await response.json()
                        mcap_change = cg_data['data']['market_cap_change_percentage_24h_usd']
                except Exception as e:
                    logger.warning(f"CoinGecko API error: {e}")
                    mcap_change = 0

                sentiment = {
                    "fg_index": fg_val,
                    "fg_class": fg_class,
                    "market_trend": mcap_change
                }

                # Cache the result
                self.cache.set_sentiment(sentiment)
                return sentiment

        except Exception as e:
            logger.error(f"Sentiment error: {e}")
            return {"fg_index": 50, "fg_class": "ნეიტრალური", "market_trend": 0}

    def load_trading_knowledge(self):
        """Load knowledge with enhanced extraction"""
        if os.path.exists(KNOWLEDGE_BASE_FILE):
            try:
                with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
                    kb = json.load(f)
                    logger.info(f"✅ ცოდნა ჩატვირთულია: {len(kb.get('patterns', []))} ნიმუში")
                    return kb
            except:
                pass

        knowledge = {"patterns": [], "strategies": [], "indicators": []}

        if not os.path.exists(PDF_FOLDER):
            logger.warning(f"📁 PDF საქაღალდე არ მოიძებნა: {PDF_FOLDER}")
            return knowledge

        try:
            pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith('.pdf')]
            logger.info(f"📚 იტვირთება {len(pdf_files)} PDF...")

            for pdf_file in pdf_files:
                pdf_path = os.path.join(PDF_FOLDER, pdf_file)
                try:
                    with open(pdf_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        text = ""
                        for page in pdf_reader.pages:
                            text += page.extract_text()
                        knowledge = self.extract_knowledge_enhanced(text, knowledge)
                        logger.info(f"✅ ჩატვირთულია: {pdf_file}")
                except Exception as e:
                    logger.error(f"❌ შეცდომა {pdf_file}: {e}")

            with open(KNOWLEDGE_BASE_FILE, 'w', encoding='utf-8') as f:
                json.dump(knowledge, f, indent=2, ensure_ascii=False)

            logger.info(f"🧠 სულ: {len(knowledge['patterns'])} ნიმუში, {len(knowledge['strategies'])} სტრატეგია")
        except Exception as e:
            logger.error(f"PDF შეცდომა: {e}")

        return knowledge

    def extract_knowledge_enhanced(self, text, knowledge):
        """Enhanced keyword extraction with context analysis"""
        text_lower = text.lower()

        # Patterns - მოწინავე keywords
        pattern_keywords = {
            "bullish_signals": ["bullish engulfing", "morning star", "hammer", "inverse head and shoulders"],
            "bearish_signals": ["bearish engulfing", "evening star", "shooting star", "head and shoulders top"],
            "reversal": ["trend reversal", "reversal pattern", "double bottom", "double top"],
            "continuation": ["flag pattern", "pennant", "ascending triangle", "descending triangle"],
            "support_resistance": ["support level", "resistance level", "breakout", "breakdown"]
        }

        for category, keywords in pattern_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    context = self.get_context(text, kw, 300)
                    if context and self.validate_context(context, category):
                        if context not in knowledge["patterns"]:
                            knowledge["patterns"].append(context)

        # Strategies - გაზრდილი სიზუსტე
        strategy_keywords = [
            "entry strategy", "exit strategy", "risk reward ratio",
            "position sizing", "stop loss placement", "take profit target",
            "trend following", "mean reversion", "momentum trading",
            "buy the dip", "sell the rally", "breakout strategy"
        ]

        for kw in strategy_keywords:
            if kw in text_lower:
                context = self.get_context(text, kw, 250)
                if context and "not recommended" not in context.lower():
                    if context not in knowledge["strategies"]:
                        knowledge["strategies"].append(context)

        # Indicators - ტექნიკური ანალიზი
        indicator_keywords = [
            "rsi divergence", "rsi oversold", "rsi overbought",
            "ema crossover", "golden cross", "death cross",
            "bollinger squeeze", "bollinger breakout",
            "macd crossover", "macd histogram", "volume spike"
        ]

        for kw in indicator_keywords:
            if kw in text_lower:
                context = self.get_context(text, kw, 200)
                if context and "avoid" not in context.lower():
                    if context not in knowledge["indicators"]:
                        knowledge["indicators"].append(context)

        return knowledge

    def validate_context(self, context, category):
        """Validate context to avoid negative patterns"""
        context_lower = context.lower()
        negative_words = ["not reliable", "avoid", "don't use", "failed", "poor", "weak signal"]

        if any(neg in context_lower for neg in negative_words):
            return False

        # Category specific validation
        if category == "bullish_signals":
            return "bullish" in context_lower and "not" not in context_lower.split("bullish")[0][-20:]
        elif category == "bearish_signals":
            return "bearish" in context_lower and "avoid" not in context_lower

        return True

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

    # --- AI ანალიზი (გაუმჯობესებული) ---
    async def ai_analyze_signal(self, symbol, data, sentiment):
        """Enhanced AI analysis with dynamic thresholds"""
        score = 0
        reasons = []

        # 1. RSI ანალიზი (დინამიური)
        if data['rsi'] < 25:  # ძალიან oversold
            score += 40
            reasons.append(f"🔴 RSI ძალიან დაბალი ({data['rsi']:.1f})")

            for k in self.trading_knowledge.get("indicators", []):
                if "rsi oversold" in k.lower() or "rsi divergence" in k.lower():
                    score += 15
                    reasons.append("🧠 AI: RSI Oversold სტრატეგია")
                    break
        elif data['rsi'] < 35:
            score += 25
            reasons.append(f"📉 RSI დაბალი ({data['rsi']:.1f})")
        elif data['rsi'] < 45:
            score += 10
            reasons.append(f"📊 RSI ნეიტრალური-დაბალი ({data['rsi']:.1f})")

        # 2. ტრენდის ანალიზი (EMA200)
        if data['price'] > data['ema200']:
            price_above_ema = ((data['price'] - data['ema200']) / data['ema200']) * 100

            if price_above_ema > 10:
                score += 30
                reasons.append(f"📈 ძლიერი ტრენდი (+{price_above_ema:.1f}% EMA200-ზე)")
            elif price_above_ema > 5:
                score += 20
                reasons.append(f"📈 აღმავალი ტრენდი (+{price_above_ema:.1f}% EMA200-ზე)")
            else:
                score += 15
                reasons.append("📈 ტრენდი აღმავალია")

            for k in self.trading_knowledge.get("strategies", []):
                if "trend following" in k.lower() or "moving average" in k.lower():
                    score += 10
                    reasons.append("🧠 AI: Trend Following სტრატეგია")
                    break
        else:
            score -= 10  # ქვემოთაა EMA200-ზე = სუსტი

        # 3. Bollinger Bands
        if data['price'] <= data['bb_low']:
            distance_from_low = ((data['bb_low'] - data['price']) / data['price']) * 100

            if distance_from_low > 2:
                score += 25
                reasons.append(f"🎯 Bollinger ქვედა ზოლთან ძალიან ახლოს (-{distance_from_low:.1f}%)")
            else:
                score += 15
                reasons.append("🎯 Bollinger ქვედა ზოლს ეხება")

            for k in self.trading_knowledge.get("patterns", []):
                if "bollinger" in k.lower() and "bounce" in k.lower():
                    score += 10
                    reasons.append("🧠 AI: Bollinger Bounce ნიმუში")
                    break

        # 4. ბაზრის გლობალური სენტიმენტი
        if sentiment['fg_index'] < 25:
            score += 20
            reasons.append(f"😨 ექსტრემალური შიში ({sentiment['fg_index']}) - შესყიდვის შანსი")
        elif sentiment['fg_index'] < 35:
            score += 15
            reasons.append(f"😰 მაღალი შიში ({sentiment['fg_index']}) - კარგი შესაძლებლობა")
        elif sentiment['fg_index'] > 75:
            score -= 25  # ზედმეტი ეიფორია - საშიში
            reasons.append(f"🚨 ზედმეტი სიხარბე ({sentiment['fg_index']})")

        if sentiment['market_trend'] > 2:
            score += 15
            reasons.append(f"🌍 ბაზარი ბულიშია (+{sentiment['market_trend']:.1f}%)")
        elif sentiment['market_trend'] > 0:
            score += 8
            reasons.append(f"🌍 ბაზარი დადებითია (+{sentiment['market_trend']:.1f}%)")

        # 5. PDF ცოდნა - გაუმჯობესებული
        for p in self.trading_knowledge.get("patterns", []):
            if "bullish" in p.lower() and "reversal" in p.lower():
                if data['rsi'] < 35 and data['price'] > data['ema200']:
                    score += 15
                    reasons.append("🧠 AI: Bullish Reversal ნიმუში")
                    break

        for p in self.trading_knowledge.get("patterns", []):
            if "double bottom" in p.lower() or "hammer" in p.lower():
                if data['rsi'] < 30:
                    score += 12
                    reasons.append("🧠 AI: Double Bottom/Hammer ნიმუში")
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
            logger.error(f"შენახვის შეცდომა {filename}: {e}")

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
        self.subscriptions[user_id] = {
            'expires_at': expires,
            'activated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'plan': 'premium'
        }
        self.save_json(self.subscriptions, SUBSCRIPTIONS_FILE)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.effective_user.username or "მომხმარებელი"
        ai_info = f"🧠 AI: {len(self.trading_knowledge.get('patterns', []))} ნიმუში" if self.trading_knowledge.get('patterns') else "🤖"

        welcome_msg = (
            f"👋 გამარჯობა @{username}!\n\n"
            f"{ai_info} AI Trading Bot\n\n"
            f"📊 მონიტორინგი:\n"
            f"• {len(CRYPTO)} კრიპტოვალუტა\n"
            f"• {len(STOCKS)} აქცია\n"
            f"• {len(COMMODITIES)} საქონელი\n\n"
            f"💰 ფასი: 150₾ / თვე\n\n"
            f"📌 ბრძანებები:\n"
            f"/subscribe - გამოწერა\n"
            f"/mystatus - სტატუსი\n"
            f"/stop - გაუქმება\n\n"
            f"❓ კითხვები? https://t.me/Kagurashinakami"
        )
        await update.message.reply_text(welcome_msg)

    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if self.is_active_subscriber(user_id):
            expires = self.subscriptions[user_id]['expires_at']
            await update.message.reply_text(
                f"✅ უკვე გაქვთ აქტიური subscription!\n"
                f"📅 იწურება: {expires}"
            )
            return

        payment_msg = (
            "💳 გამოწერის ინსტრუქცია:\n\n"
            "1️⃣ გადაიხადეთ 150₾\n"
            "🏦 ბანკი: საქართველოს ბანკი\n"
            "📋 IBAN: GE95BG0000000528102311\n"
            "👤 მიმღები: ლ.გ\n\n"
            "2️⃣ გადახდის შემდეგ:\n"
            "• გამოაგზავნეთ screenshot ამ ჩატში\n"
            "• ან პირადში: https://t.me/Kagurashinakami\n\n"
            "3️⃣ ჩვენ გავააქტიურებთ subscription-ს\n"
            "⏱️ პროცესი: 24 საათში\n\n"
            "❓ კითხვები? https://t.me/Kagurashinakami"
        )
        await update.message.reply_text(payment_msg)

    async def cmd_mystatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def handle_payment_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def cmd_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if user_id != ADMIN_ID:
            await update.message.reply_text("🚫 არ გაქვთ უფლება!")
            return

        ai_stats = (
            f"• ნიმუშები: {len(self.trading_knowledge.get('patterns', []))}\n"
            f"• სტრატეგიები: {len(self.trading_knowledge.get('strategies', []))}"
        ) if self.trading_knowledge else "• AI არ არის ჩატვირთული"

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
        user_id = update.effective_user.id

        if user_id != ADMIN_ID:
            await update.message.reply_text("🚫 არ გაქვთ უფლება!")
            return

        active_users = sum(1 for uid in self.subscriptions if self.is_active_subscriber(uid))
        pending_payments = sum(1 for req in self.payment_requests.values() if req.get('status') == 'pending')

        ai_info = (
            f"🧠 AI ცოდნა:\n"
            f"• ნიმუშები: {len(self.trading_knowledge.get('patterns', []))}\n"
            f"• სტრატეგიები: {len(self.trading_knowledge.get('strategies', []))}\n\n"
        ) if self.trading_knowledge.get('patterns') else ""

        win_rate = (
            (self.stats['successful_trades'] / self.stats['total_signals'] * 100)
            if self.stats['total_signals'] > 0 else 0
        )

        stats_msg = (
            f"📊 ბოტის სტატისტიკა\n\n"
            f"👥 მომხმარებლები: {len(self.subscriptions)}\n"
            f"✅ აქტიური: {active_users}\n"
            f"💳 გადახდის მოთხოვნები: {pending_payments}\n"
            f"📈 აქტიური პოზიციები: {len(self.active_positions)}\n"
            f"📡 მონიტორინგი: {len(ASSETS)} აქტივი\n"
            f"⏱️ ციკლი: ~{len(ASSETS) * ASSET_DELAY / 60:.1f}წთ\n\n"
            f"{ai_info}"
            f"📊 ტრეიდინგის სტატისტიკა:\n"
            f"• სულ სიგნალები: {self.stats['total_signals']}\n"
            f"• წარმატებული: {self.stats['successful_trades']}\n"
            f"• წაგებული: {self.stats['failed_trades']}\n"
            f"• Win Rate: {win_rate:.1f}%\n"
            f"• საშუალო მოგება: {self.stats['total_profit_percent']:.2f}%\n\n"
            f"💰 შემოსავალი: {active_users * 150}₾/თვე"
        )
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
        """News analysis with caching"""
        # Check cache first
        cached = self.cache.get_news(asset_name)
        if cached is not None:
            return cached

        negative_impact = 0
        positive_signals = 0

        # Enhanced keyword lists
        negative_keywords = [
            'crash', 'hacked', 'scam', 'fraud', 'lawsuit', 'bankruptcy',
            'bearish', 'plunge', 'collapse', 'ban', 'regulation crackdown',
            'investigation', 'shutdown', 'exploit', 'vulnerability'
        ]

        positive_keywords = [
            'recovers', 'surge', 'bullish', 'adoption', 'partnership',
            'upgrade', 'innovation', 'growth', 'rally', 'breakthrough'
        ]

        rss_feeds = [
            "https://cryptopanic.com/news/rss/",
            "https://cointelegraph.com/rss"
        ]

        for url in rss_feeds:
            try:
                # Async RSS parsing would be better, but feedparser is sync
                feed = feedparser.parse(url)

                for entry in feed.entries[:5]:
                    title = entry.get('title', '').lower()
                    summary = entry.get('summary', '').lower()
                    content = title + ' ' + summary

                    if asset_name.lower() in content or asset_name.replace('-USD', '').lower() in content:
                        # Check negative
                        if any(word in content for word in negative_keywords):
                            negative_impact += 1

                        # Check positive
                        if any(word in content for word in positive_keywords):
                            positive_signals += 1
            except Exception as e:
                logger.warning(f"RSS feed error {url}: {e}")
                continue

        # Decision logic
        is_clean = negative_impact == 0 or positive_signals > negative_impact

        # Cache result
        self.cache.set_news(asset_name, is_clean)

        return is_clean

    async def fetch_data(self, symbol):
        """Fetch market data with fallback sources"""
        try:
            await self.yahoo_limiter.wait_if_needed()

            # Try Yahoo Finance first
            try:
                ticker = yf.Ticker(symbol)
                # Add headers to bypass rate limit
                ticker.session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                })

                df = ticker.history(period="1mo", interval=INTERVAL)

                if df.empty or len(df) < 200:
                    logger.warning(f"⚠️ Yahoo არასაკმარისი data: {symbol} - ვცდით CoinGecko")
                    return await self.fetch_data_coingecko(symbol)

            except Exception as yahoo_error:
                logger.warning(f"Yahoo error {symbol}: {yahoo_error} - fallback to CoinGecko")
                return await self.fetch_data_coingecko(symbol)

            # Check if data is valid
            if df.empty or len(df) < 200:
                logger.warning(f"⚠️ არასაკმარისი მონაცემები: {symbol}")
                return None

            close = df['Close']

            # Calculate indicators
            ema200 = EMAIndicator(close, window=200).ema_indicator().iloc[-1]
            rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
            bb = BollingerBands(close, window=20, window_dev=2)

            return {
                "price": close.iloc[-1],
                "ema200": ema200,
                "rsi": rsi,
                "bb_low": bb.bollinger_lband().iloc[-1],
                "bb_high": bb.bollinger_hband().iloc[-1],
                "volume": df['Volume'].iloc[-1] if 'Volume' in df.columns else 0
            }

        except Exception as e:
            logger.error(f"❌ შეცდომა {symbol}: {e}")

            # Trigger backoff on repeated errors
            if "429" in str(e) or "rate" in str(e).lower():
                self.yahoo_limiter.trigger_backoff(300)

            return None

    async def analyze_and_notify(self):
        """Main analysis loop with enhanced logic"""
        active_count = sum(1 for uid in self.subscriptions if self.is_active_subscriber(uid))

        if active_count == 0:
            logger.info("⏸️ არ არის გამომწერები - სკანირება შეჩერებულია")
            return

        # Get global sentiment once per cycle
        sentiment_data = await self.get_market_sentiment()
        logger.info(
            f"\n🧠 AI სკანირება: {len(ASSETS)} აქტივი | "
            f"Fear&Greed: {sentiment_data['fg_index']} ({sentiment_data['fg_class']})"
        )

        for asset in ASSETS:
            try:
                data = await self.fetch_data(asset)

                if not data:
                    await asyncio.sleep(ASSET_DELAY)
                    continue

                # Check existing positions for exit
                if asset in self.active_positions:
                    await self.check_exit_conditions(asset, data, sentiment_data)
                else:
                    # Analyze for entry
                    ai_score, ai_reasons = await self.ai_analyze_signal(asset, data, sentiment_data)

                    # Entry threshold: 60+ score
                    if ai_score >= 60:
                        # News validation
                        is_clean = await self.get_comprehensive_news(asset)

                        if is_clean:
                            # Create position
                            self.active_positions[asset] = {
                                "entry_price": data['price'],
                                "entry_time": time.time(),
                                "entry_rsi": data['rsi'],
                                "ai_score": ai_score
                            }

                            asset_type = self.get_asset_type(asset)
                            reasons_text = "\n".join([f"• {r}" for r in ai_reasons[:6]])

                            # Calculate dynamic take profit
                            estimated_tp = self.calculate_dynamic_tp(data, sentiment_data)

                            msg = (
                                f"🟢 AI იყიდე: {asset} [{asset_type}]\n\n"
                                f"💵 ფასი: ${data['price']:.2f}\n"
                                f"📊 RSI: {data['rsi']:.1f}\n"
                                f"📈 EMA200: ${data['ema200']:.2f}\n"
                                f"🧠 AI Score: {ai_score}/100\n"
                                f"📊 Fear&Greed: {sentiment_data['fg_index']} ({sentiment_data['fg_class']})\n\n"
                                f"📌 AI მიზეზები:\n{reasons_text}\n\n"
                                f"🎯 რისკ მენეჯმენტი:\n"
                                f"🔴 Stop-Loss: -{STOP_LOSS_PERCENT}%\n"
                                f"🟢 Take-Profit: +{TAKE_PROFIT_PERCENT}%\n"
                                f"💰 ესთიმეიტი TP: +{estimated_tp:.1f}% (პოტენციური)"
                            )

                            await self.broadcast_signal(msg, asset)
                            self.stats['total_signals'] += 1
                        else:
                            logger.info(f"📰 უარყოფითი სიახლეები: {asset} - სიგნალი გამოტოვებულია")

                await asyncio.sleep(ASSET_DELAY)

            except Exception as e:
                logger.error(f"ანალიზის შეცდომა {asset}: {e}")
                continue

        logger.info(f"ციკლი დასრულდა - პაუზა {SCAN_INTERVAL}s")

    def calculate_dynamic_tp(self, data, sentiment):
        """Calculate dynamic take profit based on conditions"""
        base_tp = TAKE_PROFIT_PERCENT

        # If RSI very low + bullish sentiment = higher potential
        if data['rsi'] < 25 and sentiment['fg_index'] < 30:
            return base_tp + 5  # 15% potential
        elif data['rsi'] < 30 and sentiment['market_trend'] > 3:
            return base_tp + 3  # 13% potential
        elif data['price'] <= data['bb_low'] and data['rsi'] < 35:
            return base_tp + 2  # 12% potential

        return base_tp

    async def check_exit_conditions(self, asset, data, sentiment):
        """Enhanced exit logic with dynamic thresholds"""
        position = self.active_positions[asset]
        entry_price = position['entry_price']
        current_price = data['price']
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        hours_held = (time.time() - position['entry_time']) / 3600

        should_exit = False
        exit_reason = ""

        # 1. Stop Loss
        if profit_percent <= -STOP_LOSS_PERCENT:
            should_exit = True
            exit_reason = f"🔴 STOP-LOSS (-{abs(profit_percent):.2f}%)"

        # 2. Take Profit
        elif profit_percent >= TAKE_PROFIT_PERCENT:
            should_exit = True
            exit_reason = f"🟢 TAKE-PROFIT (+{profit_percent:.2f}%)"

        # 3. Enhanced dynamic exits
        elif profit_percent < -3 and data["rsi"] < 25:
            should_exit = True
            exit_reason = f"⚠️ ძლიერი ვარდნა + RSI ({data['rsi']:.1f}) - გასვლა"

        elif hours_held >= MAX_HOLD_HOURS:
            should_exit = True
            exit_reason = f"⏰ დროის ლიმიტი ({MAX_HOLD_HOURS}სთ)"

        elif data["rsi"] > 75:  # Extreme overbought
            should_exit = True
            exit_reason = f"📈 RSI ძალიან overbought ({data['rsi']:.1f})"

        elif data["price"] >= data["bb_high"] and data["rsi"] > 65:
            should_exit = True
            exit_reason = "📈 Bollinger ზედა ზოლი + RSI - გასვლა"

        # 4. AI pattern recognition for exits
        elif not should_exit:
            for k in self.trading_knowledge.get("patterns", []):
                if "bearish" in k.lower() and ("reversal" in k.lower() or "top" in k.lower()):
                    if data["rsi"] > 70:
                        should_exit = True
                        exit_reason = "🧠 AI: Bearish Reversal ნიმუში"
                        break

        # 5. Trailing stop for big profits
        elif not should_exit and profit_percent > 15:
            trailing_stop = entry_price * 1.12  # 12% from entry
            if current_price < trailing_stop:
                should_exit = True
                exit_reason = f"📊 Trailing Stop (+{profit_percent:.2f}% → დაცვა)"

        # 6. Market sentiment turned very negative
        elif not should_exit and sentiment['fg_index'] > 85 and profit_percent > 5:
            should_exit = True
            exit_reason = f"🚨 ექსტრემალური სიხარბე ({sentiment['fg_index']}) - გასვლა მოგებაზე"

        if should_exit:
            balance_1usd = 1.0 * (1 + (profit_percent / 100))
            asset_type = self.get_asset_type(asset)
            emoji = "🔴" if profit_percent < 0 else "🟢"

            msg = (
                f"{emoji} გაყიდე: {asset} [{asset_type}]\n\n"
                f"📊 შესვლა: ${entry_price:.2f}\n"
                f"📊 გასვლა: ${current_price:.2f}\n"
                f"💰 მოგება/ზარალი: {profit_percent:+.2f}%\n"
                f"💵 1$-ის ბალანსი: ${balance_1usd:.4f}\n"
                f"⏱️ ხანგრძლივობა: {hours_held:.1f}სთ\n\n"
                f"📌 მიზეზი: {exit_reason}"
            )

            # Update stats
            if profit_percent > 0:
                self.stats['successful_trades'] += 1
            else:
                self.stats['failed_trades'] += 1

            self.stats['total_profit_percent'] += profit_percent

            del self.active_positions[asset]
            await self.broadcast_signal(msg, asset)

            logger.info(f"🔔 SELL სიგნალი - {asset}: {profit_percent:+.2f}%")

    async def broadcast_signal(self, message, asset):
        """Broadcast with cooldown and rate limiting"""
        now = time.time()

        # Cooldown check
        if now - self.last_notifications.get(asset, 0) < NOTIFICATION_COOLDOWN:
            logger.info(f"⏸️ Cooldown აქტიური: {asset}")
            return

        self.last_notifications[asset] = now
        success_count = 0
        failed_count = 0

        # Batch sending with delays
        for user_id in list(self.subscriptions.keys()):
            if not self.is_active_subscriber(user_id):
                continue

            try:
                await self.bot.send_message(chat_id=user_id, text=message)
                success_count += 1
                await asyncio.sleep(0.05)  # 20 msg/sec limit
            except Exception as e:
                failed_count += 1
                logger.warning(f"გაგზავნის შეცდომა {user_id}: {e}")

        logger.info(f"📨 Broadcast: {success_count} წარმატებული, {failed_count} წარუმატებელი")

    async def start(self):
        """Start the bot"""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        ai_info = (
            f"{len(self.trading_knowledge.get('patterns', []))} ნიმუში"
            if self.trading_knowledge.get("patterns")
            else "ბაზა"
        )

        startup_msg = (
            "💎 AI Trading Bot აქტიურია\n"
            f"🧠 AI: {ai_info}\n\n"
            "📊 მონიტორინგი:\n"
            f"🔸 {len(CRYPTO)} კრიპტო\n"
            f"🔸 {len(STOCKS)} აქცია\n"
            f"🔸 {len(COMMODITIES)} საქონელი\n"
            "━━━━━━━━━━━━━━━━\n"
            f"📡 სულ: {len(ASSETS)} აქტივი\n"
            f"⏱️ ციკლი: ~{len(ASSETS) * ASSET_DELAY / 60:.0f}წთ\n"
            f"👥 გამომწერები: {len(self.subscriptions)}\n\n"
            "🚀 AI-powered ანალიზი აქტიურია!"
        )

        # Notify all subscribers
        for user_id in self.subscriptions:
            try:
                await self.bot.send_message(chat_id=user_id, text=startup_msg)
            except:
                pass

        logger.info(startup_msg)
        logger.info("\n" + "=" * 50 + "\n")

        # Main loop
        while True:
            try:
                await self.analyze_and_notify()
                await asyncio.sleep(SCAN_INTERVAL)
            except Exception as e:
                logger.error(f"🚨 მთავარი loop შეცდომა: {e}")
                await asyncio.sleep(60)


if __name__ == "__main__":
    print("🚀 AI Trading Bot იწყება...\n")
    bot = AITradingBot()
    asyncio.run(bot.start())