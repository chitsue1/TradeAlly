"""
Market Data Provider - PRODUCTION VERSION v2.0
✅ Integrated with existing Trading Engine
✅ Sources: CoinGecko → Binance → Yahoo Finance
✅ Circuit Breaker + Exponential Backoff
✅ Singleton Pattern
✅ Compatible with config.py settings
"""

import asyncio
import aiohttp
import time
import logging
import numpy as np
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════

class SourceStatus(Enum):
    """API Source health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CIRCUIT_OPEN = "circuit_open"

@dataclass
class MarketData:
    """Market data with indicators"""
    symbol: str
    price: float
    rsi: float
    ema200: float
    bb_low: float
    bb_high: float
    source: str
    timestamp: float

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class CircuitBreakerState:
    """Circuit breaker state for each API source"""
    failures: int = 0
    last_failure_time: float = 0
    status: SourceStatus = SourceStatus.HEALTHY
    consecutive_failures: int = 0

# ═══════════════════════════════════════════════════════════════════
# SINGLETON DATA PROVIDER WITH CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════

class MultiSourceDataProvider:
    """
    🚀 PRODUCTION-GRADE DATA PROVIDER

    Features:
    - Singleton pattern (one instance across app)
    - Circuit breaker for each API source
    - Exponential backoff on rate limits
    - Intelligent fallback cascade: CoinGecko → Binance → Yahoo
    - Professional logging
    - Compatible with existing Trading Engine
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, twelve_data_key: str = None, alpaca_key=None, alpaca_secret=None):
        if self._initialized:
            return

        self._initialized = True
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

        # Circuit breaker states per source
        self.circuit_breakers = {
            "coingecko": CircuitBreakerState(),
            "binance": CircuitBreakerState(),
            "yahoo": CircuitBreakerState()
        }

        # Statistics
        self.stats = {
            "coingecko": {"success": 0, "fail": 0, "rate_limits": 0},
            "binance": {"success": 0, "fail": 0, "rate_limits": 0},
            "yahoo": {"success": 0, "fail": 0, "rate_limits": 0}
        }

        # Configuration
        self.CIRCUIT_BREAKER_THRESHOLD = 3  # Open after 3 consecutive failures
        self.CIRCUIT_BREAKER_TIMEOUT = 300  # 5 minutes
        self.MAX_RETRIES = 3
        self.BASE_DELAY = 1  # Base delay for exponential backoff

        # Symbol mappings
        self._init_symbol_mappings()

        logger.info("🟢 MultiSourceDataProvider initialized (Singleton)")

    def _init_symbol_mappings(self):
        """Initialize all symbol mappings"""

        # CoinGecko IDs
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
            "MATIC/USD": "matic-network",
            "ARB/USD": "arbitrum",
            "OP/USD": "optimism",
            "SUI/USD": "sui"
        }

        # Binance symbols
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
            "MATIC/USD": "MATICUSDT",
            "ARB/USD": "ARBUSDT",
            "OP/USD": "OPUSDT",
            "SUI/USD": "SUIUSDT"
        }

        # Yahoo Finance symbols
        self.yahoo_symbols = {
            "BTC/USD": "BTC-USD",
            "ETH/USD": "ETH-USD",
            "BNB/USD": "BNB-USD",
            "SOL/USD": "SOL-USD",
            "XRP/USD": "XRP-USD",
            "ADA/USD": "ADA-USD",
            "DOGE/USD": "DOGE-USD",
            "DOT/USD": "DOT-USD",
            "LINK/USD": "LINK-USD",
            "AVAX/USD": "AVAX-USD",
            "LTC/USD": "LTC-USD",
            "BCH/USD": "BCH-USD",
            "UNI/USD": "UNI-USD",
            "NEAR/USD": "NEAR-USD",
            "ICP/USD": "ICP-USD",
            "HBAR/USD": "HBAR-USD",
            "MATIC/USD": "MATIC-USD",
            "ARB/USD": "ARB-USD",
            "OP/USD": "OP-USD",
            "SUI/USD": "SUI-USD"
        }

    def _is_crypto(self, symbol: str) -> bool:
        """Detect if symbol is crypto"""
        return symbol in self.coingecko_ids or "/" in symbol

    # ═══════════════════════════════════════════════════════════════
    # CIRCUIT BREAKER LOGIC
    # ═══════════════════════════════════════════════════════════════

    def _is_circuit_open(self, source: str) -> bool:
        """Check if circuit breaker is open for a source"""
        breaker = self.circuit_breakers[source]

        if breaker.status == SourceStatus.CIRCUIT_OPEN:
            # Check if timeout has passed
            if time.time() - breaker.last_failure_time > self.CIRCUIT_BREAKER_TIMEOUT:
                logger.info(f"🔄 Circuit breaker reset for {source}")
                breaker.status = SourceStatus.HEALTHY
                breaker.consecutive_failures = 0
                return False
            return True

        return False

    def _record_success(self, source: str):
        """Record successful API call"""
        breaker = self.circuit_breakers[source]
        breaker.consecutive_failures = 0
        breaker.status = SourceStatus.HEALTHY
        self.stats[source]["success"] += 1

    def _record_failure(self, source: str, is_rate_limit: bool = False):
        """Record failed API call and manage circuit breaker"""
        breaker = self.circuit_breakers[source]
        breaker.failures += 1
        breaker.consecutive_failures += 1
        breaker.last_failure_time = time.time()

        self.stats[source]["fail"] += 1
        if is_rate_limit:
            self.stats[source]["rate_limits"] += 1

        # Open circuit if threshold exceeded
        if breaker.consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            breaker.status = SourceStatus.CIRCUIT_OPEN
            logger.warning(
                f"⚠️  CIRCUIT BREAKER OPEN for {source} "
                f"({breaker.consecutive_failures} consecutive failures)"
            )

    # ═══════════════════════════════════════════════════════════════
    # EXPONENTIAL BACKOFF
    # ═══════════════════════════════════════════════════════════════

    async def _exponential_backoff(self, attempt: int, source: str):
        """Exponential backoff with jitter"""
        delay = min(self.BASE_DELAY * (2 ** attempt), 60)  # Max 60s
        jitter = np.random.uniform(0, 0.1 * delay)
        total_delay = delay + jitter

        logger.debug(f"⏳ Backoff {source}: attempt {attempt+1}, waiting {total_delay:.2f}s")
        await asyncio.sleep(total_delay)

    # ═══════════════════════════════════════════════════════════════
    # DATA FETCHING METHODS
    # ═══════════════════════════════════════════════════════════════

    async def _fetch_coingecko(self, symbol: str) -> Optional[pd.Series]:
        """Fetch from CoinGecko with retry logic"""

        if self._is_circuit_open("coingecko"):
            logger.debug(f"⭕ Circuit open for CoinGecko, skipping {symbol}")
            return None

        coingecko_id = self.coingecko_ids.get(symbol)
        if not coingecko_id:
            return None

        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart"
                    params = {"vs_currency": "usd", "days": "30", "interval": "hourly"}
                    headers = {"User-Agent": "Mozilla/5.0"}

                    async with session.get(
                        url, params=params, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:

                        if resp.status == 429:
                            logger.warning(f"🚫 Rate limit: CoinGecko ({symbol})")
                            self._record_failure("coingecko", is_rate_limit=True)
                            await self._exponential_backoff(attempt, "coingecko")
                            continue

                        if resp.status != 200:
                            self._record_failure("coingecko")
                            return None

                        data = await resp.json()
                        prices = data.get("prices", [])

                        if len(prices) < 200:
                            return None

                        closes = [float(price[1]) for price in prices[-200:]]
                        self._record_success("coingecko")

                        logger.debug(f"✅ CoinGecko: {symbol} (${closes[-1]:.2f})")
                        return pd.Series(closes)

            except asyncio.TimeoutError:
                logger.warning(f"⏱️  Timeout: CoinGecko ({symbol})")
                self._record_failure("coingecko")
                if attempt < self.MAX_RETRIES - 1:
                    await self._exponential_backoff(attempt, "coingecko")
            except Exception as e:
                logger.error(f"❌ CoinGecko error ({symbol}): {str(e)[:100]}")
                self._record_failure("coingecko")
                break

        return None

    async def _fetch_binance(self, symbol: str) -> Optional[pd.Series]:
        """Fetch from Binance with retry logic"""

        if self._is_circuit_open("binance"):
            logger.debug(f"⭕ Circuit open for Binance, skipping {symbol}")
            return None

        binance_symbol = self.binance_symbols.get(symbol, symbol.replace("/", ""))

        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://api.binance.com/api/v3/klines"
                    params = {"symbol": binance_symbol, "interval": "1h", "limit": 200}

                    async with session.get(
                        url, params=params,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:

                        if resp.status == 429:
                            logger.warning(f"🚫 Rate limit: Binance ({symbol})")
                            self._record_failure("binance", is_rate_limit=True)
                            await self._exponential_backoff(attempt, "binance")
                            continue

                        if resp.status != 200:
                            self._record_failure("binance")
                            return None

                        data = await resp.json()

                        if len(data) < 200:
                            return None

                        closes = [float(candle[4]) for candle in data]
                        self._record_success("binance")

                        logger.debug(f"✅ Binance: {symbol} (${closes[-1]:.2f})")
                        return pd.Series(closes)

            except asyncio.TimeoutError:
                logger.warning(f"⏱️  Timeout: Binance ({symbol})")
                self._record_failure("binance")
                if attempt < self.MAX_RETRIES - 1:
                    await self._exponential_backoff(attempt, "binance")
            except Exception as e:
                logger.error(f"❌ Binance error ({symbol}): {str(e)[:100]}")
                self._record_failure("binance")
                break

        return None

    async def _fetch_yahoo(self, symbol: str) -> Optional[pd.Series]:
        """Fetch from Yahoo Finance with retry logic"""

        if self._is_circuit_open("yahoo"):
            logger.debug(f"⭕ Circuit open for Yahoo, skipping {symbol}")
            return None

        yahoo_symbol = self.yahoo_symbols.get(symbol, symbol)

        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
                    params = {"interval": "1h", "range": "1mo"}
                    headers = {"User-Agent": "Mozilla/5.0"}

                    async with session.get(
                        url, params=params, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:

                        if resp.status == 429:
                            logger.warning(f"🚫 Rate limit: Yahoo ({symbol})")
                            self._record_failure("yahoo", is_rate_limit=True)
                            await self._exponential_backoff(attempt, "yahoo")
                            continue

                        if resp.status != 200:
                            self._record_failure("yahoo")
                            return None

                        data = await resp.json()
                        result = data.get("chart", {}).get("result", [])

                        if not result:
                            return None

                        indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
                        closes = [c for c in indicators.get("close", []) if c is not None]

                        if len(closes) < 200:
                            return None

                        self._record_success("yahoo")

                        logger.debug(f"✅ Yahoo: {symbol} (${closes[-1]:.2f})")
                        return pd.Series(closes[-200:])

            except asyncio.TimeoutError:
                logger.warning(f"⏱️  Timeout: Yahoo ({symbol})")
                self._record_failure("yahoo")
                if attempt < self.MAX_RETRIES - 1:
                    await self._exponential_backoff(attempt, "yahoo")
            except Exception as e:
                logger.error(f"❌ Yahoo error ({symbol}): {str(e)[:100]}")
                self._record_failure("yahoo")
                break

        return None

    # ═══════════════════════════════════════════════════════════════
    # INDICATOR CALCULATION (NaN-SAFE)
    # ═══════════════════════════════════════════════════════════════

    def _calculate_indicators(
        self, 
        close_series: pd.Series, 
        symbol: str
    ) -> Optional[Dict[str, float]]:
        """Calculate technical indicators with NaN safety"""
        try:
            # RSI
            rsi_indicator = RSIIndicator(close_series, window=14)
            rsi_value = rsi_indicator.rsi().iloc[-1]

            # Check for NaN/Inf
            if pd.isna(rsi_value) or not np.isfinite(rsi_value):
                logger.warning(f"⚠️  Invalid RSI for {symbol}")
                return None

            # EMA 200
            ema_indicator = EMAIndicator(close_series, window=200)
            ema_value = ema_indicator.ema_indicator().iloc[-1]

            if pd.isna(ema_value) or not np.isfinite(ema_value):
                logger.warning(f"⚠️  Invalid EMA for {symbol}")
                return None

            # Bollinger Bands
            bb = BollingerBands(close_series)
            bb_low = bb.bollinger_lband().iloc[-1]
            bb_high = bb.bollinger_hband().iloc[-1]

            if pd.isna(bb_low) or pd.isna(bb_high):
                logger.warning(f"⚠️  Invalid Bollinger Bands for {symbol}")
                return None

            return {
                "price": float(close_series.iloc[-1]),
                "rsi": float(rsi_value),
                "ema200": float(ema_value),
                "bb_low": float(bb_low),
                "bb_high": float(bb_high)
            }

        except Exception as e:
            logger.error(f"❌ Indicator calculation failed for {symbol}: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════
    # MAIN FETCH METHOD (Compatible with Trading Engine)
    # ═══════════════════════════════════════════════════════════════

    async def fetch_with_fallback(self, symbol: str) -> Optional[MarketData]:
        """
        🎯 INTELLIGENT FALLBACK CASCADE

        Crypto: CoinGecko → Binance → Yahoo
        Stocks: Yahoo only

        Returns MarketData or None
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
            sources = [
                ("coingecko", self._fetch_coingecko),
                ("binance", self._fetch_binance),
                ("yahoo", self._fetch_yahoo)
            ]
        else:
            sources = [("yahoo", self._fetch_yahoo)]

        # Try each source
        for source_name, fetch_func in sources:
            logger.debug(f"🔍 Trying {source_name} for {symbol}")

            close_series = await fetch_func(symbol)

            if close_series is not None and len(close_series) >= 200:
                indicators = self._calculate_indicators(close_series, symbol)

                if indicators:
                    market_data = MarketData(
                        symbol=symbol,
                        price=indicators["price"],
                        rsi=indicators["rsi"],
                        ema200=indicators["ema200"],
                        bb_low=indicators["bb_low"],
                        bb_high=indicators["bb_high"],
                        source=source_name,
                        timestamp=time.time()
                    )

                    # Cache result
                    self.cache[symbol] = (market_data, time.time())

                    logger.info(
                        f"✅ {symbol}: ${market_data.price:.2f} | "
                        f"RSI: {market_data.rsi:.1f} | "
                        f"[{source_name.upper()}]"
                    )
                    return market_data

        # All sources failed
        logger.error(f"❌ All sources failed for {symbol}")
        return None

    # ═══════════════════════════════════════════════════════════════
    # STATISTICS (for Trading Engine compatibility)
    # ═══════════════════════════════════════════════════════════════

    def get_stats(self) -> Dict[str, Any]:
        """Get detailed statistics"""

        stats_data = {}

        for source in ["coingecko", "binance", "yahoo"]:
            total = self.stats[source]["success"] + self.stats[source]["fail"]
            success_rate = (self.stats[source]["success"] / max(1, total)) * 100

            breaker = self.circuit_breakers[source]

            stats_data[source] = {
                "success": self.stats[source]["success"],
                "fail": self.stats[source]["fail"],
                "rate_limits": self.stats[source]["rate_limits"],
                "success_rate": f"{success_rate:.1f}%",
                "circuit_status": breaker.status.value,
                "consecutive_failures": breaker.consecutive_failures
            }

        return {
            "sources": stats_data,
            "cache_size": len(self.cache),
            "total_requests": sum(
                s["success"] + s["fail"] 
                for s in self.stats.values()
            )
        }