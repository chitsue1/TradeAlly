"""
AI Trading Bot - Trading Engine
ბაზრის მონაცემების მოპოვება, ანალიზი და სიგნალების გენერაცია
"""

import asyncio
import aiohttp
import time
import json
import os
import logging
import feedparser
from datetime import datetime
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from config import *

logger = logging.getLogger(__name__)


# ========================
# RATE LIMITER
# ========================
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


# ========================
# MARKET CACHE
# ========================
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
        if asset in self.news_cache:
            if time.time() - self.news_cache[asset]["timestamp"] < RSS_CACHE_TIME:
                return self.news_cache[asset]["data"]
        return None

    def set_news(self, asset, is_clean):
        self.news_cache[asset] = {"data": is_clean, "timestamp": time.time()}


# ========================
# TRADING ENGINE
# ========================
class TradingEngine:
    """Main trading engine - data fetching, analysis, signals"""

    def __init__(self):
        self.coingecko_limiter = RateLimiter(MAX_COINGECKO_REQUESTS_PER_MINUTE)
        self.sentiment_limiter = RateLimiter(MAX_SENTIMENT_REQUESTS_PER_HOUR // 60)
        self.cache = MarketCache()
        self.trading_knowledge = self.load_trading_knowledge()
        self.active_positions = {}
        self.stats = {
            "total_signals": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_profit_percent": 0.0
        }

    # ========================
    # PDF KNOWLEDGE BASE
    # ========================
    def load_trading_knowledge(self):
        """Load trading knowledge from PDFs"""
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

        if not PyPDF2:
            logger.warning("PyPDF2 not installed - skipping PDF loading")
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

            logger.info(f"🧠 სულ: {len(knowledge['patterns'])} ნიმუში")
        except Exception as e:
            logger.error(f"PDF შეცდომა: {e}")

        return knowledge

    def extract_knowledge_enhanced(self, text, knowledge):
        """Enhanced keyword extraction"""
        text_lower = text.lower()

        # Patterns
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

        # Strategies
        strategy_keywords = [
            "entry strategy", "exit strategy", "risk reward ratio",
            "position sizing", "stop loss placement", "take profit target",
            "trend following", "mean reversion", "momentum trading"
        ]

        for kw in strategy_keywords:
            if kw in text_lower:
                context = self.get_context(text, kw, 250)
                if context and "not recommended" not in context.lower():
                    if context not in knowledge["strategies"]:
                        knowledge["strategies"].append(context)

        return knowledge

    def validate_context(self, context, category):
        """Validate context to avoid negative patterns"""
        context_lower = context.lower()
        negative_words = ["not reliable", "avoid", "don't use", "failed", "poor", "weak signal"]

        if any(neg in context_lower for neg in negative_words):
            return False

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

    # ========================
    # MARKET SENTIMENT
    # ========================
    async def get_market_sentiment(self):
        """Get market sentiment with caching"""
        cached = self.cache.get_sentiment()
        if cached:
            return cached

        await self.sentiment_limiter.wait_if_needed()

        try:
            async with aiohttp.ClientSession() as session:
                # Fear & Greed
                try:
                    async with session.get(
                        "https://api.alternative.me/fng/",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        fg_data = await response.json()
                        fg_val = int(fg_data['data'][0]['value'])
                        fg_class = fg_data['data'][0]['value_classification']
                except:
                    fg_val, fg_class = 50, "ნეიტრალური"

                # CoinGecko
                try:
                    async with session.get(
                        "https://api.coingecko.com/api/v3/global",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        cg_data = await response.json()
                        mcap_change = cg_data['data']['market_cap_change_percentage_24h_usd']
                except:
                    mcap_change = 0

                sentiment = {
                    "fg_index": fg_val,
                    "fg_class": fg_class,
                    "market_trend": mcap_change
                }

                self.cache.set_sentiment(sentiment)
                return sentiment
        except Exception as e:
            logger.error(f"Sentiment error: {e}")
            return {"fg_index": 50, "fg_class": "ნეიტრალური", "market_trend": 0}

    # ========================
    # DATA FETCHING - COINGECKO ONLY
    # ========================
    async def fetch_data(self, symbol):
        """Fetch data using CoinGecko API (Yahoo-ს ნაცვლად)"""
        try:
            await self.coingecko_limiter.wait_if_needed()

            # Convert symbol
            if symbol not in CRYPTO:
                logger.warning(f"⚠️ მხოლოდ crypto: {symbol}")
                return None

            coin_id = symbol.replace("-USD", "").lower()
            coin_id = COINGECKO_MAP.get(coin_id, coin_id)

            async with aiohttp.ClientSession() as session:
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
                params = {"vs_currency": "usd", "days": "30", "interval": "hourly"}

                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status != 200:
                        logger.error(f"CoinGecko error {symbol}: {response.status}")
                        return None

                    data = await response.json()
                    prices = [p[1] for p in data['prices']]

                    if len(prices) < 200:
                        logger.warning(f"არასაკმარისი მონაცემები: {symbol}")
                        return None

                    # Calculate indicators
                    import pandas as pd
                    df = pd.DataFrame({'Close': prices})
                    close = df['Close']

                    ema200 = EMAIndicator(close, window=200).ema_indicator().iloc[-1]
                    rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
                    bb = BollingerBands(close, window=20, window_dev=2)

                    return {
                        "price": close.iloc[-1],
                        "ema200": ema200,
                        "rsi": rsi,
                        "bb_low": bb.bollinger_lband().iloc[-1],
                        "bb_high": bb.bollinger_hband().iloc[-1],
                        "volume": 0
                    }
        except Exception as e:
            logger.error(f"❌ Fetch error {symbol}: {e}")
            return None

    # ========================
    # NEWS ANALYSIS
    # ========================
    async def get_comprehensive_news(self, asset_name):
        """News analysis with caching"""
        cached = self.cache.get_news(asset_name)
        if cached is not None:
            return cached

        negative_impact = 0
        positive_signals = 0

        negative_keywords = [
            'crash', 'hacked', 'scam', 'fraud', 'lawsuit', 'bankruptcy',
            'bearish', 'plunge', 'collapse', 'ban', 'regulation crackdown'
        ]

        positive_keywords = [
            'recovers', 'surge', 'bullish', 'adoption', 'partnership',
            'upgrade', 'innovation', 'growth', 'rally', 'breakthrough'
        ]

        for url in RSS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    title = entry.get('title', '').lower()
                    summary = entry.get('summary', '').lower()
                    content = title + ' ' + summary

                    if asset_name.lower() in content or asset_name.replace('-USD', '').lower() in content:
                        if any(word in content for word in negative_keywords):
                            negative_impact += 1
                        if any(word in content for word in positive_keywords):
                            positive_signals += 1
            except:
                continue

        is_clean = negative_impact == 0 or positive_signals > negative_impact
        self.cache.set_news(asset_name, is_clean)
        return is_clean

    # ========================
    # AI ANALYSIS
    # ========================
    async def ai_analyze_signal(self, symbol, data, sentiment):
        """Enhanced AI analysis"""
        score = 0
        reasons = []

        # RSI Analysis
        if data['rsi'] < 25:
            score += 40
            reasons.append(f"🔴 RSI ძალიან დაბალი ({data['rsi']:.1f})")
        elif data['rsi'] < 35:
            score += 25
            reasons.append(f"📉 RSI დაბალი ({data['rsi']:.1f})")
        elif data['rsi'] < 45:
            score += 10
            reasons.append(f"📊 RSI ნეიტრალური-დაბალი ({data['rsi']:.1f})")

        # Trend Analysis
        if data['price'] > data['ema200']:
            price_above_ema = ((data['price'] - data['ema200']) / data['ema200']) * 100
            if price_above_ema > 10:
                score += 30
                reasons.append(f"📈 ძლიერი ტრენდი (+{price_above_ema:.1f}%)")
            elif price_above_ema > 5:
                score += 20
                reasons.append(f"📈 აღმავალი ტრენდი (+{price_above_ema:.1f}%)")
            else:
                score += 15
                reasons.append("📈 ტრენდი აღმავალია")
        else:
            score -= 10

        # Bollinger Bands
        if data['price'] <= data['bb_low']:
            score += 20
            reasons.append("🎯 Bollinger ქვედა ზოლს ეხება")

        # Market Sentiment
        if sentiment['fg_index'] < 25:
            score += 20
            reasons.append(f"😨 ექსტრემალური შიში ({sentiment['fg_index']})")
        elif sentiment['fg_index'] < 35:
            score += 15
            reasons.append(f"😰 მაღალი შიში ({sentiment['fg_index']})")
        elif sentiment['fg_index'] > 75:
            score -= 25
            reasons.append(f"🚨 ზედმეტი სიხარბე ({sentiment['fg_index']})")

        if sentiment['market_trend'] > 2:
            score += 15
            reasons.append(f"🌍 ბაზარი ბულიშია (+{sentiment['market_trend']:.1f}%)")

        # PDF Knowledge
        for p in self.trading_knowledge.get("patterns", []):
            if "bullish" in p.lower() and "reversal" in p.lower():
                if data['rsi'] < 35 and data['price'] > data['ema200']:
                    score += 15
                    reasons.append("🧠 AI: Bullish Reversal ნიმუში")
                    break

        return score, reasons

    def calculate_dynamic_tp(self, data, sentiment):
        """Calculate dynamic take profit"""
        base_tp = TAKE_PROFIT_PERCENT

        if data['rsi'] < 25 and sentiment['fg_index'] < 30:
            return base_tp + 5
        elif data['rsi'] < 30 and sentiment['market_trend'] > 3:
            return base_tp + 3
        elif data['price'] <= data['bb_low'] and data['rsi'] < 35:
            return base_tp + 2

        return base_tp

    def get_asset_type(self, symbol):
        """Get asset type emoji"""
        if symbol in CRYPTO:
            return "💎 CRYPTO"
        elif symbol in STOCKS:
            return "📈 STOCK"
        elif symbol in COMMODITIES:
            return "🏆 COMMODITY"
        return "📊 ASSET"