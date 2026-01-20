"""
AI Trading Bot - Trading Engine (Multi-Source Optimized)
"""

import asyncio
import time
import json
import os
import logging
import aiohttp
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from config import *
from market_data import MultiSourceDataProvider

logger = logging.getLogger(__name__)

class MarketCache:
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        self.sentiment_cache = {"data": None, "timestamp": 0}
        self.news_cache = {}

    def get_sentiment(self):
        if time.time() - self.sentiment_cache["timestamp"] < 1800:
            return self.sentiment_cache["data"]
        return None

    def set_sentiment(self, data):
        self.sentiment_cache = {"data": data, "timestamp": time.time()}

    def get_news(self, asset):
        if asset in self.news_cache:
            if time.time() - self.news_cache[asset]["timestamp"] < 1800:
                return self.news_cache[asset]["data"]
        return None

    def set_news(self, asset, is_clean):
        self.news_cache[asset] = {"data": is_clean, "timestamp": time.time()}

class TradingEngine:
    def __init__(self):
        self.data_provider = MultiSourceDataProvider(twelve_data_key=TWELVE_DATA_API_KEY)
        self.cache = MarketCache()
        self.knowledge = self.load_trading_knowledge()
        self.active_positions = {}
        self.stats = {"total_signals": 0, "successful_trades": 0, "failed_trades": 0}

    def load_trading_knowledge(self):
        if os.path.exists(KNOWLEDGE_BASE_FILE):
            try:
                with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {"patterns": [], "strategies": []}

    async def fetch_data(self, symbol):
        data = await self.data_provider.fetch_with_fallback(symbol)
        if not data: return None
        return {
            "price": data.price, "rsi": data.rsi, "ema200": data.ema200,
            "bb_low": data.bb_low, "bb_high": data.bb_high, "source": data.source
        }

    async def get_market_sentiment(self):
        cached = self.cache.get_sentiment()
        if cached: return cached
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.alternative.me/fng/", timeout=10) as resp:
                    data = await resp.json()
                    sentiment = {"fg_index": int(data['data'][0]['value']), "fg_class": data['data'][0]['value_classification']}
                    self.cache.set_sentiment(sentiment)
                    return sentiment
        except: return {"fg_index": 50, "fg_class": "ნეიტრალური"}

    async def ai_analyze_signal(self, symbol, data, sentiment):
        score = 0
        reasons = []
        if data['rsi'] < 30:
            score += 40
            reasons.append(f"📉 გადაყიდულია (RSI: {data['rsi']:.1f})")
        if data['price'] > data['ema200']:
            score += 20
            reasons.append("📈 აღმავალი ტრენდი")
        if data['price'] <= data['bb_low']:
            score += 25
            reasons.append("🎯 ქვედა ბოინჯერზეა")
        if sentiment['fg_index'] < 30:
            score += 15
            reasons.append("😱 პანიკაა")
        return score, reasons

    async def get_comprehensive_news(self, asset):
        cached = self.cache.get_news(asset)
        if cached is not None: return cached
        self.cache.set_news(asset, True)
        return True

    def calculate_dynamic_tp(self, data, sentiment): return TAKE_PROFIT_PERCENT
    def get_asset_type(self, symbol):
        if symbol in CRYPTO: return "Crypto"
        if symbol in STOCKS: return "Stock"
        return "Commodity"
    async def cleanup(self): pass
