"""
AI Trading Bot - Trading Engine (Twelve Data Optimized)
ბაზრის მონაცემების მოპოვება, ანალიზი და სიგნალების გენერაცია
"""

import asyncio
import aiohttp
import time
import json
import os
import logging
import pandas as pd
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
# RATE LIMITER (Twelve Data Optimized)
# ========================
class RateLimiter:
    def __init__(self, max_per_minute=8):
        self.max_per_minute = max_per_minute
        self.requests = []
        self.backoff_until = 0

    async def wait_if_needed(self):
        now = time.time()
        if now < self.backoff_until:
            wait_time = self.backoff_until - now
            await asyncio.sleep(wait_time)
            return

        self.requests = [t for t in self.requests if now - t < 60]
        if len(self.requests) >= self.max_per_minute:
            wait_time = 60 - (now - self.requests[0]) + 1
            logger.info(f"⏱️ API ლიმიტი: ველოდებით {wait_time:.1f} წამს...")
            await asyncio.sleep(wait_time)
            self.requests = []
        self.requests.append(now)

    def trigger_backoff(self, seconds=300):
        self.backoff_until = time.time() + seconds
        logger.error(f"🚨 API ბლოკი - პაუზა {seconds} წამი")

# ========================
# TRADING ENGINE (The Brain)
# ========================
class TradingEngine:
    def __init__(self):
        self.td_limiter = RateLimiter(MAX_TD_REQUESTS_PER_MINUTE)
        self.knowledge = self.load_trading_knowledge()
        self.active_positions = {}

    def load_trading_knowledge(self):
        """PDF-ებიდან ამოღებული სავაჭრო ცოდნის ჩატვირთვა"""
        if os.path.exists(KNOWLEDGE_BASE_FILE):
            try:
                with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"patterns": [], "strategies": []}

    async def fetch_data(self, symbol):
        """მონაცემების წამოღება Twelve Data-დან"""
        try:
            await self.td_limiter.wait_if_needed()
            async with aiohttp.ClientSession() as session:
                url = "https://api.twelvedata.com/time_series"
                params = {
                    "symbol": symbol,
                    "interval": INTERVAL,
                    "apikey": TWELVE_DATA_API_KEY,
                    "outputsize": 200
                }
                async with session.get(url, params=params) as resp:
                    if resp.status == 429:
                        self.td_limiter.trigger_backoff()
                        return None

                    data = await resp.json()
                    if data.get('status') == 'error':
                        logger.error(f"API Error {symbol}: {data.get('message')}")
                        return None

                    df = pd.DataFrame(data.get('values'))
                    df['close'] = pd.to_numeric(df['close'])
                    close = df['close'].iloc[::-1]

                    # ინდიკატორების გამოთვლა
                    rsi = RSIIndicator(close).rsi().iloc[-1]
                    ema200 = EMAIndicator(close, window=200).ema_indicator().iloc[-1]
                    bb = BollingerBands(close)

                    return {
                        "price": close.iloc[-1],
                        "rsi": rsi,
                        "ema200": ema200,
                        "bb_low": bb.bollinger_lband().iloc[-1],
                        "bb_high": bb.bollinger_hband().iloc[-1]
                    }
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None

    async def ai_analyze_signal(self, symbol, data, sentiment):
        """სიგნალის კომპლექსური ანალიზი"""
        score = 0
        reasons = []

        # 1. RSI ანალიზი
        if data['rsi'] < 30:
            score += 40
            reasons.append(f"📉 გადაყიდულია (RSI: {data['rsi']:.1f})")

        # 2. ტრენდის ანალიზი (EMA200)
        if data['price'] > data['ema200']:
            score += 20
            reasons.append("📈 გრძელვადიანი ტრენდი აღმავალია")

        # 3. Bollinger Bands
        if data['price'] <= data['bb_low']:
            score += 25
            reasons.append("🎯 ფასი ქვედა ბოინჯერზეა")

        # 4. ბაზრის ზოგადი განწყობა (Fear & Greed)
        if sentiment['fg_index'] < 30:
            score += 15
            reasons.append(f"😱 ბაზარზე პანიკაა ({sentiment['fg_index']})")

        # 5. PDF ცოდნის შემოწმება (Bonus Score)
        if any(p in str(reasons).lower() for p in self.knowledge.get('patterns', [])):
            score += 10
            reasons.append("🧠 PDF ცოდნამ დაადასტურა ნიმუში")

        return score, reasons