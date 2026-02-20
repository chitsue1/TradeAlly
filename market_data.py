"""
Market Data Provider - PRODUCTION VERSION v2.5 FINAL
✅ Yahoo Finance PRIORITY #1 (ყველაზე სანდო)
✅ CoinGecko & Binance ფიქსირებული (fallback)
✅ COMPLETE INDICATOR SET (15 indicators)
✅ 57 კრიპტო სრული მხარდაჭერა
"""

import asyncio
import aiohttp
import time
import logging
import numpy as np
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd
from ta.trend import EMAIndicator, MACD
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

    # RSI
    rsi: float
    prev_rsi: float

    # EMAs
    ema50: float
    ema200: float

    # MACD
    macd: float
    macd_signal: float
    macd_histogram: float
    macd_histogram_prev: float

    # Bollinger Bands
    bb_low: float
    bb_high: float
    bb_mid: float
    bb_width: float
    avg_bb_width_20d: float

    # Previous price
    prev_close: float

    # Metadata
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
# SINGLETON DATA PROVIDER
# ═══════════════════════════════════════════════════════════════════

class MultiSourceDataProvider:
    """
    🚀 PRODUCTION-GRADE DATA PROVIDER - v2.5 FINAL

    ✅ Yahoo Finance PRIORITY (ყველაზე სანდო და სწრაფი)
    ✅ CoinGecko fallback (fixed)
    ✅ Binance fallback (fixed)
    ✅ COMPLETE INDICATOR SET
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

        # Circuit breakers
        self.circuit_breakers = {
            "yahoo": CircuitBreakerState(),      # ✅ Yahoo first
            "coingecko": CircuitBreakerState(),
            "binance": CircuitBreakerState()
        }

        # Statistics
        self.stats = {
            "yahoo": {"success": 0, "fail": 0, "rate_limits": 0},
            "coingecko": {"success": 0, "fail": 0, "rate_limits": 0},
            "binance": {"success": 0, "fail": 0, "rate_limits": 0}
        }

        # Configuration
        self.CIRCUIT_BREAKER_THRESHOLD = 3
        self.CIRCUIT_BREAKER_TIMEOUT = 300
        self.MAX_RETRIES = 2  # ✅ Reduced to 2 (faster)
        self.BASE_DELAY = 0.5  # ✅ Faster backoff

        # Initialize ALL 57 crypto mappings
        self._init_symbol_mappings()

        logger.info("🟢 MultiSourceDataProvider v2.5 FINAL - Yahoo Priority")

    def _init_symbol_mappings(self):
        """Initialize all symbol mappings - 57 კრიპტო"""

        # ✅ Yahoo Finance symbols (PRIORITY #1)
        self.yahoo_symbols = {
            # Tier 1 (14)
            "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "BNB/USD": "BNB-USD",
            "SOL/USD": "SOL-USD", "XRP/USD": "XRP-USD", "ADA/USD": "ADA-USD",
            "AVAX/USD": "AVAX-USD", "LINK/USD": "LINK-USD", "MATIC/USD": "MATIC-USD",
            "DOT/USD": "DOT-USD", "TRX/USD": "TRX-USD", "LTC/USD": "LTC-USD",
            "XLM/USD": "XLM-USD", "ETC/USD": "ETC-USD",

            # Tier 2 (13)
            "NEAR/USD": "NEAR-USD", "ARB/USD": "ARB-USD", "OP/USD": "OP-USD",
            "SUI/USD": "SUI-USD", "INJ/USD": "INJ-USD", "APT/USD": "APT-USD",
            "UNI/USD": "UNI-USD", "ATOM/USD": "ATOM-USD", "FTM/USD": "FTM-USD",
            "KAS/USD": "KAS-USD", "RUNE/USD": "RUNE-USD", "EGLD/USD": "EGLD-USD",
            "MINA/USD": "MINA-USD",

            # Tier 3 (9)
            "DOGE/USD": "DOGE-USD", "PEPE/USD": "PEPE-USD", "WIF/USD": "WIF-USD",
            "BONK/USD": "BONK-USD", "FLOKI/USD": "FLOKI-USD", "BRETT/USD": "BRETT-USD",
            "POPCAT/USD": "POPCAT-USD", "BOME/USD": "BOME-USD", "MYRO/USD": "MYRO-USD",

            # Tier 4 (10)
            "RNDR/USD": "RNDR-USD", "FET/USD": "FET-USD", "AGIX/USD": "AGIX-USD",
            "GALA/USD": "GALA-USD", "IMX/USD": "IMX-USD", "ONDO/USD": "ONDO-USD",
            "CFG/USD": "CFG-USD", "AKT/USD": "AKT-USD", "TAO/USD": "TAO-USD",
            "PIXEL/USD": "PIXEL-USD",

            # Tier 5 (11)
            "SEI/USD": "SEI-USD", "TIA/USD": "TIA-USD", "STRK/USD": "STRK-USD",
            "BCH/USD": "BCH-USD", "TON/USD": "TON-USD", "PYTH/USD": "PYTH-USD",
            "JTO/USD": "JTO-USD", "DYM/USD": "DYM-USD", "ZK/USD": "ZK-USD",
            "AEVO/USD": "AEVO-USD",
        }

        # CoinGecko IDs (Fallback #2)
        self.coingecko_ids = {
            "BTC/USD": "bitcoin", "ETH/USD": "ethereum", "BNB/USD": "binancecoin",
            "SOL/USD": "solana", "XRP/USD": "ripple", "ADA/USD": "cardano",
            "AVAX/USD": "avalanche-2", "LINK/USD": "chainlink", "MATIC/USD": "matic-network",
            "DOT/USD": "polkadot", "TRX/USD": "tron", "LTC/USD": "litecoin",
            "XLM/USD": "stellar", "ETC/USD": "ethereum-classic",
            "NEAR/USD": "near", "ARB/USD": "arbitrum", "OP/USD": "optimism",
            "SUI/USD": "sui", "INJ/USD": "injective-protocol", "APT/USD": "aptos",
            "UNI/USD": "uniswap", "ATOM/USD": "cosmos", "FTM/USD": "fantom",
            "KAS/USD": "kaspa", "RUNE/USD": "thorchain", "EGLD/USD": "elrond-erd-2",
            "MINA/USD": "mina-protocol",
            "DOGE/USD": "dogecoin", "PEPE/USD": "pepe", "WIF/USD": "dogwifcoin",
            "BONK/USD": "bonk", "FLOKI/USD": "floki", "BRETT/USD": "brett",
            "POPCAT/USD": "popcat", "BOME/USD": "book-of-meme", "MYRO/USD": "myro",
            "RNDR/USD": "render-token", "FET/USD": "fetch-ai", "AGIX/USD": "singularitynet",
            "GALA/USD": "gala", "IMX/USD": "immutable-x", "ONDO/USD": "ondo-finance",
            "CFG/USD": "centrifuge", "AKT/USD": "akash-network", "TAO/USD": "bittensor",
            "PIXEL/USD": "pixels",
            "SEI/USD": "sei-network", "TIA/USD": "celestia", "STRK/USD": "starknet",
            "BCH/USD": "bitcoin-cash", "TON/USD": "the-open-network", "PYTH/USD": "pyth-network",
            "JTO/USD": "jito-governance-token", "DYM/USD": "dymension", "ZK/USD": "zksync",
            "AEVO/USD": "aevo",
        }

        # Binance symbols (Fallback #3)
        self.binance_symbols = {
            "BTC/USD": "BTCUSDT", "ETH/USD": "ETHUSDT", "BNB/USD": "BNBUSDT",
            "SOL/USD": "SOLUSDT", "XRP/USD": "XRPUSDT", "ADA/USD": "ADAUSDT",
            "AVAX/USD": "AVAXUSDT", "LINK/USD": "LINKUSDT", "MATIC/USD": "MATICUSDT",
            "DOT/USD": "DOTUSDT", "TRX/USD": "TRXUSDT", "LTC/USD": "LTCUSDT",
            "XLM/USD": "XLMUSDT", "ETC/USD": "ETCUSDT",
            "NEAR/USD": "NEARUSDT", "ARB/USD": "ARBUSDT", "OP/USD": "OPUSDT",
            "SUI/USD": "SUIUSDT", "INJ/USD": "INJUSDT", "APT/USD": "APTUSDT",
            "UNI/USD": "UNIUSDT", "ATOM/USD": "ATOMUSDT", "FTM/USD": "FTMUSDT",
            "KAS/USD": "KASUSDT", "RUNE/USD": "RUNEUSDT", "EGLD/USD": "EGLDUSDT",
            "MINA/USD": "MINAUSDT",
            "DOGE/USD": "DOGEUSDT", "PEPE/USD": "PEPEUSDT", "WIF/USD": "WIFUSDT",
            "BONK/USD": "BONKUSDT", "FLOKI/USD": "FLOKIUSDT", "BRETT/USD": "BRETTUSDT",
            "POPCAT/USD": "POPCATUSDT", "BOME/USD": "BOMEUSDT", "MYRO/USD": "MYROUSDT",
            "RNDR/USD": "RNDRUSDT", "FET/USD": "FETUSDT", "AGIX/USD": "AGIXUSDT",
            "GALA/USD": "GALAUSDT", "IMX/USD": "IMXUSDT", "ONDO/USD": "ONDOUSDT",
            "CFG/USD": "CFGUSDT", "AKT/USD": "AKTUSDT", "TAO/USD": "TAOUSDT",
            "PIXEL/USD": "PIXELUSDT",
            "SEI/USD": "SEIUSDT", "TIA/USD": "TIAUSDT", "STRK/USD": "STRKUSDT",
            "BCH/USD": "BCHUSDT", "TON/USD": "TONUSDT", "PYTH/USD": "PYTHUSDT",
            "JTO/USD": "JTOUSDT", "DYM/USD": "DYMUSDT", "ZK/USD": "ZKUSDT",
            "AEVO/USD": "AEVOUSDT",
        }

    def _is_crypto(self, symbol: str) -> bool:
        return symbol in self.yahoo_symbols

    # ═══════════════════════════════════════════════════════════════
    # CIRCUIT BREAKER LOGIC
    # ═══════════════════════════════════════════════════════════════

    def _is_circuit_open(self, source: str) -> bool:
        breaker = self.circuit_breakers[source]
        if breaker.status == SourceStatus.CIRCUIT_OPEN:
            if time.time() - breaker.last_failure_time > self.CIRCUIT_BREAKER_TIMEOUT:
                logger.info(f"🔄 Circuit reset: {source}")
                breaker.status = SourceStatus.HEALTHY
                breaker.consecutive_failures = 0
                return False
            return True
        return False

    def _record_success(self, source: str):
        self.circuit_breakers[source].consecutive_failures = 0
        self.circuit_breakers[source].status = SourceStatus.HEALTHY
        self.stats[source]["success"] += 1

    def _record_failure(self, source: str, is_rate_limit: bool = False):
        breaker = self.circuit_breakers[source]
        breaker.failures += 1
        breaker.consecutive_failures += 1
        breaker.last_failure_time = time.time()
        self.stats[source]["fail"] += 1
        if is_rate_limit:
            self.stats[source]["rate_limits"] += 1
        if breaker.consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            breaker.status = SourceStatus.CIRCUIT_OPEN
            logger.warning(f"⚠️  CIRCUIT OPEN: {source}")

    async def _exponential_backoff(self, attempt: int, source: str):
        delay = min(self.BASE_DELAY * (2 ** attempt), 30)
        await asyncio.sleep(delay)

    # ═══════════════════════════════════════════════════════════════
    # ✅ YAHOO FINANCE (PRIORITY #1)
    # ═══════════════════════════════════════════════════════════════

    async def _fetch_yahoo(self, symbol: str) -> Optional[pd.Series]:
        """
        ✅ Yahoo Finance - PRIORITY #1

        ყველაზე სანდო და სწრაფი წყარო
        """
        if self._is_circuit_open("yahoo"):
            return None

        yahoo_symbol = self.yahoo_symbols.get(symbol)
        if not yahoo_symbol:
            return None

        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
                    params = {"interval": "1h", "range": "1mo"}
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

                    async with session.get(url, params=params, headers=headers,
                                          timeout=aiohttp.ClientTimeout(total=10)) as resp:

                        if resp.status == 429:
                            self._record_failure("yahoo", True)
                            await self._exponential_backoff(attempt, "yahoo")
                            continue

                        if resp.status != 200:
                            logger.debug(f"Yahoo HTTP {resp.status} for {symbol}")
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

                        last_price = closes[-1]
                        if last_price <= 0 or not np.isfinite(last_price):
                            self._record_failure("yahoo")
                            return None

                        self._record_success("yahoo")
                        logger.info(f"✅ Yahoo: {symbol} @ ${last_price:.8f}")
                        return pd.Series(closes[-200:])

            except asyncio.TimeoutError:
                self._record_failure("yahoo")
                if attempt < self.MAX_RETRIES - 1:
                    await self._exponential_backoff(attempt, "yahoo")
            except Exception as e:
                logger.debug(f"Yahoo error ({symbol}): {str(e)[:100]}")
                self._record_failure("yahoo")
                break

        return None

    # ═══════════════════════════════════════════════════════════════
    # ✅ COINGECKO (FALLBACK #2) - FIXED
    # ═══════════════════════════════════════════════════════════════

    async def _fetch_coingecko(self, symbol: str) -> Optional[pd.Series]:
        """
        ✅ CoinGecko - FALLBACK #2

        ფიქსირებული რეიტ-ლიმიტებისთვის
        """
        if self._is_circuit_open("coingecko"):
            return None

        coingecko_id = self.coingecko_ids.get(symbol)
        if not coingecko_id:
            return None

        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    # ✅ Use public API endpoint (no key needed)
                    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart"
                    params = {
                        "vs_currency": "usd",
                        "days": "30",
                        "interval": "hourly"
                    }
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json"
                    }

                    async with session.get(url, params=params, headers=headers,
                                          timeout=aiohttp.ClientTimeout(total=10)) as resp:

                        if resp.status == 429:
                            logger.warning(f"🚫 CoinGecko rate limit ({symbol}) - switching to next source")
                            self._record_failure("coingecko", True)
                            return None  # ✅ Don't retry, just skip to next source

                        if resp.status != 200:
                            self._record_failure("coingecko")
                            return None

                        data = await resp.json()
                        prices = data.get("prices", [])

                        if len(prices) < 200:
                            return None

                        closes = [float(price[1]) for price in prices[-200:]]
                        last_price = closes[-1]

                        if last_price <= 0 or not np.isfinite(last_price):
                            self._record_failure("coingecko")
                            return None

                        self._record_success("coingecko")
                        logger.info(f"✅ CoinGecko: {symbol} @ ${last_price:.8f}")
                        return pd.Series(closes)

            except asyncio.TimeoutError:
                self._record_failure("coingecko")
                return None  # ✅ Fast fail on timeout
            except Exception as e:
                logger.debug(f"CoinGecko error ({symbol}): {str(e)[:100]}")
                self._record_failure("coingecko")
                break

        return None

    # ═══════════════════════════════════════════════════════════════
    # ✅ BINANCE (FALLBACK #3) - FIXED
    # ═══════════════════════════════════════════════════════════════

    async def _fetch_binance(self, symbol: str) -> Optional[pd.Series]:
        """
        ✅ Binance - FALLBACK #3

        ფიქსირებული სიმბოლოებისთვის
        """
        if self._is_circuit_open("binance"):
            return None

        binance_symbol = self.binance_symbols.get(symbol)
        if not binance_symbol:
            return None

        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://api.binance.com/api/v3/klines"
                    params = {
                        "symbol": binance_symbol,
                        "interval": "1h",
                        "limit": 200
                    }

                    async with session.get(url, params=params,
                                          timeout=aiohttp.ClientTimeout(total=10)) as resp:

                        if resp.status == 429:
                            logger.warning(f"🚫 Binance rate limit ({symbol})")
                            self._record_failure("binance", True)
                            return None  # ✅ Fast skip

                        if resp.status != 200:
                            self._record_failure("binance")
                            return None

                        data = await resp.json()
                        if len(data) < 200:
                            return None

                        # ✅ Close price is index 4
                        closes = [float(candle[4]) for candle in data]
                        last_price = closes[-1]

                        if last_price <= 0 or not np.isfinite(last_price):
                            self._record_failure("binance")
                            return None

                        self._record_success("binance")
                        logger.info(f"✅ Binance: {symbol} @ ${last_price:.8f}")
                        return pd.Series(closes)

            except asyncio.TimeoutError:
                self._record_failure("binance")
                return None  # ✅ Fast fail
            except Exception as e:
                logger.debug(f"Binance error ({symbol}): {str(e)[:100]}")
                self._record_failure("binance")
                break

        return None

    # ═══════════════════════════════════════════════════════════════
    # ✅ COMPLETE INDICATOR CALCULATION
    # ═══════════════════════════════════════════════════════════════

    def _calculate_indicators(
        self, 
        close_series: pd.Series, 
        symbol: str
    ) -> Optional[Dict[str, float]]:
        """
        ✅ COMPLETE INDICATOR SET - All strategies supported
        """
        try:
            current_price = float(close_series.iloc[-1])
            if current_price <= 0 or not np.isfinite(current_price):
                return None

            prev_close = float(close_series.iloc[-2]) if len(close_series) > 1 else current_price

            # RSI
            rsi_indicator = RSIIndicator(close_series, window=14)
            rsi_series = rsi_indicator.rsi()
            rsi_value = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0
            prev_rsi = float(rsi_series.iloc[-2]) if len(rsi_series) > 1 and not pd.isna(rsi_series.iloc[-2]) else rsi_value

            # EMA50
            if len(close_series) >= 50:
                ema50_indicator = EMAIndicator(close_series, window=50)
                ema50_value = ema50_indicator.ema_indicator().iloc[-1]
                ema50_value = float(ema50_value) if not pd.isna(ema50_value) else current_price
            else:
                ema50_value = current_price

            # EMA200
            ema200_indicator = EMAIndicator(close_series, window=200)
            ema200_value = ema200_indicator.ema_indicator().iloc[-1]
            ema200_value = float(ema200_value) if not pd.isna(ema200_value) else current_price

            # MACD
            try:
                macd_indicator = MACD(close_series)
                macd_line = float(macd_indicator.macd().iloc[-1]) if not pd.isna(macd_indicator.macd().iloc[-1]) else 0.0
                macd_signal = float(macd_indicator.macd_signal().iloc[-1]) if not pd.isna(macd_indicator.macd_signal().iloc[-1]) else 0.0
                macd_histogram = float(macd_indicator.macd_diff().iloc[-1]) if not pd.isna(macd_indicator.macd_diff().iloc[-1]) else 0.0

                if len(close_series) > 26:
                    prev_macd_hist = macd_indicator.macd_diff().iloc[-2]
                    prev_macd_hist = float(prev_macd_hist) if not pd.isna(prev_macd_hist) else macd_histogram
                else:
                    prev_macd_hist = macd_histogram
            except:
                macd_line = macd_signal = macd_histogram = prev_macd_hist = 0.0

            # Bollinger Bands
            bb = BollingerBands(close_series)
            bb_low = float(bb.bollinger_lband().iloc[-1]) if not pd.isna(bb.bollinger_lband().iloc[-1]) else current_price * 0.9
            bb_high = float(bb.bollinger_hband().iloc[-1]) if not pd.isna(bb.bollinger_hband().iloc[-1]) else current_price * 1.1
            bb_mid = float(bb.bollinger_mavg().iloc[-1]) if not pd.isna(bb.bollinger_mavg().iloc[-1]) else current_price

            bb_width = bb_high - bb_low
            bb_width_series = bb.bollinger_hband() - bb.bollinger_lband()

            if len(bb_width_series) >= 20:
                valid_widths = bb_width_series[-20:].dropna()
                avg_bb_width_20d = float(valid_widths.mean()) if len(valid_widths) > 0 else bb_width
            else:
                avg_bb_width_20d = bb_width

            result = {
                "price": float(current_price),
                "prev_close": float(prev_close),
                "rsi": float(rsi_value),
                "prev_rsi": float(prev_rsi),
                "ema50": float(ema50_value),
                "ema200": float(ema200_value),
                "macd": float(macd_line),
                "macd_signal": float(macd_signal),
                "macd_histogram": float(macd_histogram),
                "macd_histogram_prev": float(prev_macd_hist),
                "bb_low": float(bb_low),
                "bb_high": float(bb_high),
                "bb_mid": float(bb_mid),
                "bb_width": float(bb_width),
                "avg_bb_width_20d": float(avg_bb_width_20d),
            }

            logger.info(
                f"✅ {symbol}: ${result['price']:.6f} | "
                f"RSI:{result['rsi']:.1f}({result['prev_rsi']:.1f}) | "
                f"EMA50:${result['ema50']:.4f}"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Indicators failed ({symbol}): {e}")
            return None

    # ═══════════════════════════════════════════════════════════════
    # ✅ MAIN FETCH METHOD - YAHOO PRIORITY
    # ═══════════════════════════════════════════════════════════════

    async def fetch_with_fallback(self, symbol: str) -> Optional[MarketData]:
        """
        ✅ INTELLIGENT FALLBACK CASCADE

        Priority: Yahoo → CoinGecko → Binance
        """

        # Check cache
        if symbol in self.cache:
            cached_data, cached_time = self.cache[symbol]
            if time.time() - cached_time < self.cache_ttl:
                return cached_data

        # ✅ PRIORITY ORDER: Yahoo first!
        sources = [
            ("yahoo", self._fetch_yahoo),
            ("coingecko", self._fetch_coingecko),
            ("binance", self._fetch_binance)
        ]

        for source_name, fetch_func in sources:
            close_series = await fetch_func(symbol)

            if close_series is not None and len(close_series) >= 200:
                indicators = self._calculate_indicators(close_series, symbol)

                if indicators:
                    market_data = MarketData(
                        symbol=symbol,
                        price=indicators["price"],
                        prev_close=indicators["prev_close"],
                        rsi=indicators["rsi"],
                        prev_rsi=indicators["prev_rsi"],
                        ema50=indicators["ema50"],
                        ema200=indicators["ema200"],
                        macd=indicators["macd"],
                        macd_signal=indicators["macd_signal"],
                        macd_histogram=indicators["macd_histogram"],
                        macd_histogram_prev=indicators.get("macd_histogram_prev", indicators["macd_histogram"]),
                        bb_low=indicators["bb_low"],
                        bb_high=indicators["bb_high"],
                        bb_mid=indicators["bb_mid"],
                        bb_width=indicators["bb_width"],
                        avg_bb_width_20d=indicators["avg_bb_width_20d"],
                        source=source_name,
                        timestamp=time.time()
                    )

                    self.cache[symbol] = (market_data, time.time())
                    return market_data

        logger.error(f"❌ All sources failed: {symbol}")
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Statistics"""
        stats_data = {}
        for source in ["yahoo", "coingecko", "binance"]:
            total = self.stats[source]["success"] + self.stats[source]["fail"]
            success_rate = (self.stats[source]["success"] / max(1, total)) * 100
            breaker = self.circuit_breakers[source]
            stats_data[source] = {
                "success": self.stats[source]["success"],
                "fail": self.stats[source]["fail"],
                "rate_limits": self.stats[source]["rate_limits"],
                "success_rate": f"{success_rate:.1f}%",
                "circuit_status": breaker.status.value,
            }
        return {
            "sources": stats_data,
            "cache_size": len(self.cache),
            "total_requests": sum(s["success"] + s["fail"] for s in self.stats.values())
        }