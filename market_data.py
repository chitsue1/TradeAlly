"""
Market Data Provider - FINAL PRODUCTION VERSION
✅ Sources: CoinGecko (crypto) + Binance (crypto) + Yahoo Finance (stocks)
✅ Fixed: pandas.np deprecated issue
✅ Added: New crypto assets (SOL, SEEKER, etc.)
"""

import asyncio
import aiohttp
import time
import logging
import numpy as np
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
    Production-grade multi-source provider
    - CoinGecko: crypto (free, reliable, NO API key needed)
    - Binance: crypto (free, unlimited)
    - Yahoo Finance: stocks + crypto fallback (free)
    """

    def __init__(self, twelve_data_key: str = None, alpaca_key=None, alpaca_secret=None):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

        self.stats = {
            "coingecko": {"success": 0, "fail": 0},
            "binance": {"success": 0, "fail": 0},
            "yahoo": {"success": 0, "fail": 0}
        }

        # ✅ CoinGecko symbol mappings (ID format)
        self.coingecko_ids = {
            "BTC/USD": "bitcoin",
            "ETH/USD": "ethereum",
            "BNB/USD": "binancecoin",
            "SOL/USD": "solana",
            "XRP/USD": "ripple",
            "ADA/USD": "cardano",
            "DOGE/USD": "dogecoin",
            "DOT/USD": "polkadot",
            "LINK/USD": "chainlink",
            "AVAX/USD": "avalanche-2",
            "LTC/USD": "litecoin",
            "BCH/USD": "bitcoin-cash",
            "UNI/USD": "uniswap",
            "NEAR/USD": "near",
            "ICP/USD": "internet-computer",
            "HBAR/USD": "hedera-hashgraph",
            # ✅ NEW TOP CRYPTOS
            "SEEKER/USD": "seeker",  # If exists on CoinGecko
            "MATIC/USD": "matic-network",
            "ARB/USD": "arbitrum",
            "OP/USD": "optimism",
            "SUI/USD": "sui"
        }

        # Symbol mappings for Binance
        self.binance_symbols = {
            "BTC/USD": "BTCUSDT",
            "ETH/USD": "ETHUSDT",
            "BNB/USD": "BNBUSDT",
            "SOL/USD": "SOLUSDT",
            "XRP/USD": "XRPUSDT",
            "ADA/USD": "ADAUSDT",
            "DOGE/USD": "DOGEUSDT",
            "DOT/USD": "DOTUSDT",
            "LINK/USD": "LINKUSDT",
            "AVAX/USD": "AVAXUSDT",
            "LTC/USD": "LTCUSDT",
            "BCH/USD": "BCHUSDT",
            "UNI/USD": "UNIUSDT",
            "NEAR/USD": "NEARUSDT",
            "ICP/USD": "ICPUSDT",
            "HBAR/USD": "HBARUSDT",
            # ✅ NEW
            "MATIC/USD": "MATICUSDT",
            "ARB/USD": "ARBUSDT",
            "OP/USD": "OPUSDT",
            "SUI/USD": "SUIUSDT"
        }

        # ✅ FIXED Yahoo symbols (verified working)
        self.yahoo_symbols = {
            "BTC/USD": "BTC-USD",
            "ETH/USD": "ETH-USD",
            "BNB/USD": "BNB-USD",
            "SOL/USD": "SOL-USD",
            "XRP/USD": "XRP-USD",
            "ADA/USD": "ADA-USD",
            "DOGE/USD": "DOGE-USD",
            "DOT/USD": "DOT-USD",      # ✅ Fixed: was DOT1-USD
            "LINK/USD": "LINK-USD",
            "AVAX/USD": "AVAX-USD",
            "LTC/USD": "LTC-USD",
            "BCH/USD": "BCH-USD",
            "UNI/USD": "UNI-USD",      # ✅ Simplified: UNI7083-USD also works
            "NEAR/USD": "NEAR-USD",
            "ICP/USD": "ICP-USD",
            "HBAR/USD": "HBAR-USD",
            # ✅ NEW
            "MATIC/USD": "MATIC-USD",
            "ARB/USD": "ARB-USD",
            "OP/USD": "OP-USD",
            "SUI/USD": "SUI-USD"
        }

    def _is_crypto(self, symbol: str) -> bool:
        """Detect crypto"""
        return symbol in self.coingecko_ids or "/" in symbol

    def _get_coingecko_id(self, symbol: str) -> str:
        """Convert to CoinGecko ID"""
        return self.coingecko_ids.get(symbol)

    def _get_binance_symbol(self, symbol: str) -> str:
        """Convert to Binance format"""
        return self.binance_symbols.get(symbol, symbol.replace("/", ""))

    def _get_yahoo_symbol(self, symbol: str) -> str:
        """Convert to Yahoo format"""
        if symbol in self.yahoo_symbols:
            return self.yahoo_symbols[symbol]
        return symbol

    async def _fetch_coingecko(self, symbol: str) -> Optional[pd.Series]:
        """
        ✅ NEW: Fetch from CoinGecko (free, no API key)
        Uses market_chart endpoint for historical data
        """
        try:
            coingecko_id = self._get_coingecko_id(symbol)
            if not coingecko_id:
                return None

            async with aiohttp.ClientSession() as session:
                # CoinGecko market_chart API (last 30 days, hourly)
                url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart"
                params = {
                    "vs_currency": "usd",
                    "days": "30",
                    "interval": "hourly"
                }
                headers = {
                    "User-Agent": "Mozilla/5.0"
                }

                async with session.get(url, params=params, headers=headers,
                                      timeout=aiohttp.ClientTimeout(total=15)) as resp:

                    if resp.status == 429:
                        logger.warning(f"CoinGecko rate limited for {symbol}")
                        await asyncio.sleep(2)
                        return None

                    if resp.status != 200:
                        logger.debug(f"CoinGecko failed for {symbol}: {resp.status}")
                        return None

                    data = await resp.json()

                    prices = data.get("prices", [])
                    if not prices or len(prices) < 200:
                        logger.debug(f"CoinGecko: insufficient data for {symbol} ({len(prices)} points)")
                        return None

                    # Extract close prices (prices is [[timestamp, price], ...])
                    closes = [float(price[1]) for price in prices[-200:]]

                    self.stats["coingecko"]["success"] += 1
                    logger.debug(f"✅ CoinGecko: {symbol} → {coingecko_id}")
                    return pd.Series(closes)

        except asyncio.TimeoutError:
            logger.debug(f"CoinGecko timeout for {symbol}")
            self.stats["coingecko"]["fail"] += 1
            return None
        except Exception as e:
            self.stats["coingecko"]["fail"] += 1
            logger.debug(f"CoinGecko error for {symbol}: {str(e)[:100]}")
            return None

    async def _fetch_binance(self, symbol: str) -> Optional[pd.Series]:
        """Fetch from Binance"""
        try:
            binance_symbol = self._get_binance_symbol(symbol)

            async with aiohttp.ClientSession() as session:
                url = "https://api.binance.com/api/v3/klines"
                params = {
                    "symbol": binance_symbol,
                    "interval": "1h",
                    "limit": 200
                }
                headers = {
                    "User-Agent": "Mozilla/5.0"
                }

                async with session.get(url, params=params, headers=headers,
                                      timeout=aiohttp.ClientTimeout(total=15)) as resp:

                    if resp.status == 429:
                        logger.warning(f"Binance rate limited for {symbol}")
                        await asyncio.sleep(1)
                        return None

                    if resp.status != 200:
                        logger.debug(f"Binance failed for {symbol}: {resp.status}")
                        return None

                    data = await resp.json()

                    if not data or len(data) < 200:
                        logger.debug(f"Binance: insufficient data for {symbol}")
                        return None

                    closes = [float(candle[4]) for candle in data]

                    self.stats["binance"]["success"] += 1
                    logger.debug(f"✅ Binance: {symbol} → {binance_symbol}")
                    return pd.Series(closes)

        except asyncio.TimeoutError:
            logger.debug(f"Binance timeout for {symbol}")
            self.stats["binance"]["fail"] += 1
            return None
        except Exception as e:
            self.stats["binance"]["fail"] += 1
            logger.debug(f"Binance error for {symbol}: {str(e)[:100]}")
            return None

    async def _fetch_yahoo(self, symbol: str) -> Optional[pd.Series]:
        """Fetch from Yahoo Finance"""
        try:
            yahoo_symbol = self._get_yahoo_symbol(symbol)

            async with aiohttp.ClientSession() as session:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
                params = {
                    "interval": "1h",
                    "range": "1mo"
                }
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }

                async with session.get(url, params=params, headers=headers,
                                      timeout=aiohttp.ClientTimeout(total=15)) as resp:

                    if resp.status == 429:
                        logger.warning(f"Yahoo rate limited for {symbol}")
                        await asyncio.sleep(2)
                        return None

                    if resp.status != 200:
                        logger.debug(f"Yahoo failed for {symbol}: {resp.status}")
                        return None

                    data = await resp.json()

                    chart = data.get("chart", {})
                    result = chart.get("result", [])

                    if not result:
                        error = chart.get("error")
                        if error:
                            logger.debug(f"Yahoo error for {symbol}: {error.get('description')}")
                        return None

                    indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
                    closes = indicators.get("close", [])

                    closes = [c for c in closes if c is not None]

                    if len(closes) < 200:
                        logger.debug(f"Yahoo: insufficient data for {symbol} ({len(closes)} candles)")
                        return None

                    self.stats["yahoo"]["success"] += 1
                    logger.debug(f"✅ Yahoo: {symbol} → {yahoo_symbol}")
                    return pd.Series(closes[-200:])

        except asyncio.TimeoutError:
            logger.debug(f"Yahoo timeout for {symbol}")
            self.stats["yahoo"]["fail"] += 1
            return None
        except Exception as e:
            self.stats["yahoo"]["fail"] += 1
            logger.debug(f"Yahoo error for {symbol}: {str(e)[:100]}")
            return None

    async def fetch_with_fallback(self, symbol: str) -> Optional[MarketData]:
        """
        ✅ UPDATED: Intelligent fallback with CoinGecko priority
        Crypto: CoinGecko → Binance → Yahoo
        Stocks: Yahoo only
        """

        # Check cache first
        if symbol in self.cache:
            cached_data, cached_time = self.cache[symbol]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug(f"💾 Cache hit: {symbol}")
                return cached_data

        is_crypto = self._is_crypto(symbol)

        # Define source priority
        if is_crypto:
            sources = [
                ("coingecko", self._fetch_coingecko),  # ✅ NEW: Priority #1
                ("binance", self._fetch_binance),
                ("yahoo", self._fetch_yahoo)
            ]
        else:
            sources = [
                ("yahoo", self._fetch_yahoo)
            ]

        # Try each source
        for source_name, fetch_func in sources:
            logger.debug(f"🔍 Trying {source_name} for {symbol}")

            close_series = await fetch_func(symbol)

            if close_series is not None and len(close_series) >= 200:
                try:
                    # Calculate indicators
                    rsi_indicator = RSIIndicator(close_series, window=14)
                    rsi_value = rsi_indicator.rsi().iloc[-1]

                    # ✅ FIXED: numpy instead of pandas.np
                    if pd.isna(rsi_value) or not np.isfinite(rsi_value):
                        logger.debug(f"Invalid RSI for {symbol}")
                        continue

                    ema_indicator = EMAIndicator(close_series, window=200)
                    ema_value = ema_indicator.ema_indicator().iloc[-1]

                    bb = BollingerBands(close_series)
                    bb_low = bb.bollinger_lband().iloc[-1]
                    bb_high = bb.bollinger_hband().iloc[-1]

                    market_data = MarketData(
                        symbol=symbol,
                        price=float(close_series.iloc[-1]),
                        rsi=float(rsi_value),
                        ema200=float(ema_value),
                        bb_low=float(bb_low),
                        bb_high=float(bb_high),
                        source=source_name,
                        timestamp=time.time()
                    )

                    # Cache successful result
                    self.cache[symbol] = (market_data, time.time())

                    logger.info(f"✅ {symbol}: ${market_data.price:.2f} (RSI: {market_data.rsi:.1f}) [source: {source_name}]")
                    return market_data

                except Exception as e:
                    logger.error(f"Indicator calculation failed for {symbol}: {e}")
                    continue

        # All sources failed
        logger.error(f"❌ All sources failed for {symbol}")
        return None

    def get_stats(self):
        """Get statistics"""
        total_cg = self.stats["coingecko"]["success"] + self.stats["coingecko"]["fail"]
        total_binance = self.stats["binance"]["success"] + self.stats["binance"]["fail"]
        total_yahoo = self.stats["yahoo"]["success"] + self.stats["yahoo"]["fail"]

        return {
            "sources": {
                "coingecko": {
                    "success": self.stats["coingecko"]["success"],
                    "fail": self.stats["coingecko"]["fail"],
                    "rate": (self.stats["coingecko"]["success"] / max(1, total_cg)) * 100
                },
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