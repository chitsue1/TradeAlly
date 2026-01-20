"""
Market Data Provider - Simplified Version
მხოლოდ უფასო წყაროები: Binance (crypto) + Yahoo (stocks/commodities)
NO API KEYS NEEDED - 100% FREE
"""

import asyncio
import aiohttp
import time
import logging
from typing import Optional
from dataclasses import dataclass
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

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

class MultiSourceDataProvider:
    """
    უმარტივესი multi-source provider
    - Binance: კრიპტოსთვის (უფასო, unlimited)
    - Yahoo Finance: აქციებისთვის (უფასო, ~2000/საათში)
    """

    def __init__(self, twelve_data_key: str = None, alpaca_key=None, alpaca_secret=None):
        # ეს არგუმენტები არ გვჭირდება, მაგრამ compatibility-სთვის ვტოვებთ
        self.cache = {}
        self.cache_ttl = 300  # 5 წუთი

        self.stats = {
            "binance": {"success": 0, "fail": 0},
            "yahoo": {"success": 0, "fail": 0}
        }

    def _is_crypto(self, symbol: str) -> bool:
        """კრიპტოს დეტექტი"""
        crypto_list = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", 
                       "DOT", "LINK", "AVAX", "LTC", "BCH", "UNI", 
                       "NEAR", "ICP", "HBAR"]
        return any(c in symbol.upper() for c in crypto_list)

    async def _fetch_binance(self, symbol: str) -> Optional[pd.Series]:
        """Binance-დან მონაცემები (კრიპტო)"""
        try:
            # BTC/USD → BTCUSDT
            clean_symbol = symbol.upper().replace("/", "").replace("USD", "USDT")

            async with aiohttp.ClientSession() as session:
                url = "https://api.binance.com/api/v3/klines"
                params = {
                    "symbol": clean_symbol,
                    "interval": "1h",
                    "limit": 200
                }

                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.debug(f"Binance failed for {symbol}: status {resp.status}")
                        return None

                    data = await resp.json()
                    closes = [float(candle[4]) for candle in data]

                    self.stats["binance"]["success"] += 1
                    logger.debug(f"✅ Binance: {symbol}")
                    return pd.Series(closes)

        except Exception as e:
            self.stats["binance"]["fail"] += 1
            logger.debug(f"Binance error for {symbol}: {e}")
            return None

    async def _fetch_yahoo(self, symbol: str) -> Optional[pd.Series]:
        """Yahoo Finance-დან მონაცემები (აქციები/კრიპტო)"""
        try:
            # Format: BTC/USD → BTC-USD, AAPL → AAPL
            if "/" in symbol:
                yahoo_symbol = symbol.replace("/", "-")
            else:
                yahoo_symbol = symbol

            async with aiohttp.ClientSession() as session:
                # Yahoo v8 API (უფასო, no key needed)
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
                params = {
                    "interval": "1h",
                    "range": "1mo"  # 1 თვე = ~200+ hourly candles
                }

                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.debug(f"Yahoo failed for {symbol}: status {resp.status}")
                        return None

                    data = await resp.json()

                    # Parse Yahoo response
                    result = data.get("chart", {}).get("result", [])
                    if not result:
                        return None

                    indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])

                    # Remove None values
                    closes = [c for c in closes if c is not None]

                    if len(closes) < 200:
                        logger.debug(f"Yahoo: not enough data for {symbol} ({len(closes)} candles)")
                        return None

                    self.stats["yahoo"]["success"] += 1
                    logger.debug(f"✅ Yahoo: {symbol}")
                    return pd.Series(closes[-200:])  # ბოლო 200

        except Exception as e:
            self.stats["yahoo"]["fail"] += 1
            logger.debug(f"Yahoo error for {symbol}: {e}")
            return None

    async def fetch_with_fallback(self, symbol: str) -> Optional[MarketData]:
        """
        Multi-source fetch with fallback
        Crypto: Binance → Yahoo
        Stocks: Yahoo → Binance (some stocks on Binance)
        """

        # Check cache
        if symbol in self.cache:
            cached_data, cached_time = self.cache[symbol]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug(f"💾 Cache hit: {symbol}")
                return cached_data

        # Determine source priority
        is_crypto = self._is_crypto(symbol)

        if is_crypto:
            # კრიპტო: Binance → Yahoo
            sources = [
                ("binance", self._fetch_binance),
                ("yahoo", self._fetch_yahoo)
            ]
        else:
            # აქციები: Yahoo → Binance
            sources = [
                ("yahoo", self._fetch_yahoo),
                ("binance", self._fetch_binance)  # ზოგიერთი აქცია Binance-ზეც არის
            ]

        # Try each source
        for source_name, fetch_func in sources:
            logger.debug(f"🔍 Trying {source_name} for {symbol}")

            close_series = await fetch_func(symbol)

            if close_series is not None and len(close_series) >= 200:
                try:
                    # Calculate indicators
                    rsi = RSIIndicator(close_series).rsi().iloc[-1]
                    ema200 = EMAIndicator(close_series, window=200).ema_indicator().iloc[-1]
                    bb = BollingerBands(close_series)

                    market_data = MarketData(
                        symbol=symbol,
                        price=close_series.iloc[-1],
                        rsi=rsi,
                        ema200=ema200,
                        bb_low=bb.bollinger_lband().iloc[-1],
                        bb_high=bb.bollinger_hband().iloc[-1],
                        source=source_name,
                        timestamp=time.time()
                    )

                    # Cache
                    self.cache[symbol] = (market_data, time.time())

                    logger.info(f"✅ {symbol} fetched from {source_name}")
                    return market_data

                except Exception as e:
                    logger.error(f"Indicator calculation failed for {symbol}: {e}")
                    continue

        # All sources failed
        logger.error(f"❌ All sources failed for {symbol}")
        return None

    def get_stats(self):
        """სტატისტიკა"""
        total_binance = self.stats["binance"]["success"] + self.stats["binance"]["fail"]
        total_yahoo = self.stats["yahoo"]["success"] + self.stats["yahoo"]["fail"]

        return {
            "sources": {
                "binance": {
                    "success": self.stats["binance"]["success"],
                    "fail": self.stats["binance"]["fail"],
                    "rate": (self.stats["binance"]["success"] / max(1, total_binance)) * 100
                },
                "yahoo": {
                    "success": self.stats["yahoo"]["success"],
                    "fail": self.stats["yahoo"]["fail"],
                    "rate": (self.stats["yahoo"]["success"] / max(1, total_yahoo)) * 100
                }
            },
            "cache_size": len(self.cache)
        }