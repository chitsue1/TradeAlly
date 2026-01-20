"""
AI Trading Bot - Market Data Provider (Multi-Source with Intelligent Fallback)
"""

import asyncio
import aiohttp
import time
import logging
import pandas as pd
from typing import Optional
from dataclasses import dataclass
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from config import *

logger = logging.getLogger(__name__)

@dataclass
class MarketData:
    symbol: str
    price: float
    rsi: float
    ema200: float
    bb_low: float
    bb_high: float
    source: str
    timestamp: float

class SmartRateLimiter:
    def __init__(self, requests_per_minute: int = 8):
        self.rpm = requests_per_minute
        self.requests = []
        self.backoff_until = 0

    async def acquire(self):
        now = time.time()
        if now < self.backoff_until:
            await asyncio.sleep(self.backoff_until - now)
            now = time.time()

        self.requests = [t for t in self.requests if now - t < 60]
        if len(self.requests) >= self.rpm:
            wait_time = 60 - (now - self.requests[0]) + 1
            await asyncio.sleep(wait_time)
            self.requests = []
        self.requests.append(time.time())

    def trigger_backoff(self, duration=300):
        self.backoff_until = time.time() + duration

class MultiSourceDataProvider:
    def __init__(self, twelve_data_key: str):
        self.twelve_data_key = twelve_data_key
        self.td_limiter = SmartRateLimiter(8)
        self.cache = {}
        self.cache_ttl = 300
        self.stats = {
            "TwelveData": {"success": 0, "fail": 0},
            "YahooFinance": {"success": 0, "fail": 0}
        }

    async def fetch_with_fallback(self, symbol: str) -> Optional[MarketData]:
        if symbol in self.cache:
            data, ts = self.cache[symbol]
            if time.time() - ts < self.cache_ttl:
                return data

        # 1. Try Twelve Data
        data = await self._fetch_twelvedata(symbol)
        if data:
            self.stats["TwelveData"]["success"] += 1
            self.cache[symbol] = (data, time.time())
            return data
        self.stats["TwelveData"]["fail"] += 1

        # 2. Try Yahoo Finance (via direct API endpoint)
        data = await self._fetch_yahoo_direct(symbol)
        if data:
            self.stats["YahooFinance"]["success"] += 1
            self.cache[symbol] = (data, time.time())
            return data
        self.stats["YahooFinance"]["fail"] += 1

        return None

    async def _fetch_twelvedata(self, symbol: str) -> Optional[MarketData]:
        try:
            await self.td_limiter.acquire()
            async with aiohttp.ClientSession() as session:
                url = "https://api.twelvedata.com/time_series"
                params = {"symbol": symbol, "interval": INTERVAL, "apikey": self.twelve_data_key, "outputsize": 200}
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 429:
                        self.td_limiter.trigger_backoff()
                        return None
                    data = await resp.json()
                    if data.get('status') == 'error': return None
                    values = data.get('values', [])
                    if len(values) < 20: return None
                    df = pd.DataFrame(values)
                    df['close'] = pd.to_numeric(df['close'])
                    return self._calculate(df['close'].iloc[::-1], symbol, "TwelveData")
        except: return None

    async def _fetch_yahoo_direct(self, symbol: str) -> Optional[MarketData]:
        """Direct fetch from Yahoo Finance to avoid yfinance library issues"""
        try:
            ticker = symbol.replace("/", "-")
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            params = {"interval": "1h", "range": "1mo"}
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                    if resp.status != 200: return None
                    data = await resp.json()
                    result = data.get('chart', {}).get('result', [])
                    if not result: return None
                    
                    indicators = result[0].get('indicators', {})
                    adjclose = indicators.get('adjclose', [{}])[0].get('adjclose')
                    if not adjclose:
                        quotes = indicators.get('quote', [{}])[0]
                        closes = quotes.get('close', [])
                    else:
                        closes = adjclose
                        
                    valid_closes = [c for c in closes if c is not None]
                    if len(valid_closes) < 20: return None
                    
                    return self._calculate(pd.Series(valid_closes), symbol, "YahooFinance")
        except Exception as e:
            logger.error(f"Yahoo direct fetch error for {symbol}: {e}")
            return None

    def _calculate(self, close_series, symbol, source) -> Optional[MarketData]:
        try:
            rsi = RSIIndicator(close_series).rsi().iloc[-1]
            ema200 = EMAIndicator(close_series, window=min(200, len(close_series))).ema_indicator().iloc[-1]
            bb = BollingerBands(close_series)
            return MarketData(
                symbol=symbol, price=float(close_series.iloc[-1]), rsi=float(rsi),
                ema200=float(ema200), bb_low=float(bb.bollinger_lband().iloc[-1]),
                bb_high=float(bb.bollinger_hband().iloc[-1]), source=source, timestamp=time.time()
            )
        except: return None

    def get_stats(self):
        return {"sources": self.stats, "cache_size": len(self.cache)}
