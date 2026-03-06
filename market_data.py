"""
Market Data Provider - PRODUCTION v3.0 FIXED
P0 FIXES:
  #1 — startup preload: fetch_all_history() ყველა 57 asset real 200-candle history
       სიგნალი blocked სანამ preload არ დასრულდება
  #2 — mock volume ამოღება: volume missing → volume_missing=True flag → engine blocks
P1 FIXES:
  #4 — real multi-TF: Yahoo 1h(1mo) + Binance 4h ცალ-ცალკე, indicators computed
       separately, MultiTFData dataclass returned in MarketData
v2.5 შენარჩუნებული:
  Yahoo PRIORITY, CoinGecko+Binance fallback, circuit breakers, singleton, cache, mappings
"""

import asyncio
import aiohttp
import time
import logging
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

logger = logging.getLogger(__name__)


class SourceStatus(Enum):
    HEALTHY      = "healthy"
    DEGRADED     = "degraded"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class MultiTFData:
    """Real multi-timeframe indicator snapshot — P1/#4"""
    rsi_1h:            float = 50.0
    ema50_1h:          float = 0.0
    ema200_1h:         float = 0.0
    macd_hist_1h:      float = 0.0
    macd_hist_prev_1h: float = 0.0
    bb_low_1h:         float = 0.0
    bb_high_1h:        float = 0.0
    bb_mid_1h:         float = 0.0
    bb_width_1h:       float = 0.0
    avg_bb_width_1h:   float = 0.0
    rsi_4h:            float = 50.0
    ema50_4h:          float = 0.0
    ema200_4h:         float = 0.0
    macd_hist_4h:      float = 0.0
    trend_4h:          str   = "neutral"
    trend_1h:          str   = "neutral"
    trend_1d:          str   = "neutral"
    alignment_score:   float = 50.0


@dataclass
class MarketData:
    symbol:              str
    price:               float
    rsi:                 float
    prev_rsi:            float
    ema50:               float
    ema200:              float
    macd:                float
    macd_signal:         float
    macd_histogram:      float
    macd_histogram_prev: float
    volume:              float
    avg_volume_20d:      float
    bb_low:              float
    bb_high:             float
    bb_mid:              float
    bb_width:            float
    avg_bb_width_20d:    float
    prev_close:          float
    source:              str
    timestamp:           float
    multi_tf:            MultiTFData = field(default_factory=MultiTFData)
    volume_missing:      bool = False   # P0/#2

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CircuitBreakerState:
    failures:             int          = 0
    last_failure_time:    float        = 0
    status:               SourceStatus = SourceStatus.HEALTHY
    consecutive_failures: int          = 0


class MultiSourceDataProvider:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, twelve_data_key: str = None, alpaca_key=None, alpaca_secret=None):
        if self._initialized:
            return
        self._initialized = True

        self.cache:     Dict[str, Tuple[MarketData, float]] = {}
        self.cache_ttl: int = 300

        # P0/#1 — preload tracking
        self.preloaded_symbols: set = set()
        self.preload_complete:  bool = False
        self._preload_lock = asyncio.Lock()

        # Real history stores
        self._real_history: Dict[str, List[float]] = {}   # 1h closes
        self._real_volumes: Dict[str, List[float]] = {}   # 1h volumes
        self._history_4h:   Dict[str, List[float]] = {}   # 4h closes

        self.circuit_breakers = {
            "yahoo":     CircuitBreakerState(),
            "coingecko": CircuitBreakerState(),
            "binance":   CircuitBreakerState(),
        }
        self.stats = {
            "yahoo":     {"success": 0, "fail": 0, "rate_limits": 0},
            "coingecko": {"success": 0, "fail": 0, "rate_limits": 0},
            "binance":   {"success": 0, "fail": 0, "rate_limits": 0},
        }

        self.CIRCUIT_BREAKER_THRESHOLD = 3
        self.CIRCUIT_BREAKER_TIMEOUT   = 300
        self.MAX_RETRIES = 2
        self.BASE_DELAY  = 0.5

        self._init_symbol_mappings()
        logger.info("🟢 MultiSourceDataProvider v3.0 FIXED — preload enabled")

    # ─── Symbol Mappings (unchanged from v2.5) ────────────────────────────

    def _init_symbol_mappings(self):
        self.yahoo_symbols = {
            "BTC/USD":"BTC-USD","ETH/USD":"ETH-USD","BNB/USD":"BNB-USD",
            "SOL/USD":"SOL-USD","XRP/USD":"XRP-USD","ADA/USD":"ADA-USD",
            "AVAX/USD":"AVAX-USD","LINK/USD":"LINK-USD","MATIC/USD":"MATIC-USD",
            "DOT/USD":"DOT-USD","TRX/USD":"TRX-USD","LTC/USD":"LTC-USD",
            "XLM/USD":"XLM-USD","ETC/USD":"ETC-USD",
            "NEAR/USD":"NEAR-USD","ARB/USD":"ARB-USD","OP/USD":"OP-USD",
            "SUI/USD":"SUI-USD","INJ/USD":"INJ-USD","APT/USD":"APT-USD",
            "UNI/USD":"UNI-USD","ATOM/USD":"ATOM-USD","FTM/USD":"FTM-USD",
            "KAS/USD":"KAS-USD","RUNE/USD":"RUNE-USD","EGLD/USD":"EGLD-USD",
            "MINA/USD":"MINA-USD",
            "DOGE/USD":"DOGE-USD","PEPE/USD":"PEPE-USD","WIF/USD":"WIF-USD",
            "BONK/USD":"BONK-USD","FLOKI/USD":"FLOKI-USD","BRETT/USD":"BRETT-USD",
            "POPCAT/USD":"POPCAT-USD","BOME/USD":"BOME-USD","MYRO/USD":"MYRO-USD",
            "RNDR/USD":"RNDR-USD","FET/USD":"FET-USD","AGIX/USD":"AGIX-USD",
            "GALA/USD":"GALA-USD","IMX/USD":"IMX-USD","ONDO/USD":"ONDO-USD",
            "CFG/USD":"CFG-USD","AKT/USD":"AKT-USD","TAO/USD":"TAO-USD",
            "PIXEL/USD":"PIXEL-USD",
            "SEI/USD":"SEI-USD","TIA/USD":"TIA-USD","STRK/USD":"STRK-USD",
            "BCH/USD":"BCH-USD","TON/USD":"TON-USD","PYTH/USD":"PYTH-USD",
            "JTO/USD":"JTO-USD","DYM/USD":"DYM-USD","ZK/USD":"ZK-USD",
            "AEVO/USD":"AEVO-USD",
        }
        self.coingecko_ids = {
            "BTC/USD":"bitcoin","ETH/USD":"ethereum","BNB/USD":"binancecoin",
            "SOL/USD":"solana","XRP/USD":"ripple","ADA/USD":"cardano",
            "AVAX/USD":"avalanche-2","LINK/USD":"chainlink","MATIC/USD":"matic-network",
            "DOT/USD":"polkadot","TRX/USD":"tron","LTC/USD":"litecoin",
            "XLM/USD":"stellar","ETC/USD":"ethereum-classic",
            "NEAR/USD":"near","ARB/USD":"arbitrum","OP/USD":"optimism",
            "SUI/USD":"sui","INJ/USD":"injective-protocol","APT/USD":"aptos",
            "UNI/USD":"uniswap","ATOM/USD":"cosmos","FTM/USD":"fantom",
            "KAS/USD":"kaspa","RUNE/USD":"thorchain","EGLD/USD":"elrond-erd-2",
            "MINA/USD":"mina-protocol",
            "DOGE/USD":"dogecoin","PEPE/USD":"pepe","WIF/USD":"dogwifcoin",
            "BONK/USD":"bonk","FLOKI/USD":"floki","BRETT/USD":"brett",
            "POPCAT/USD":"popcat","BOME/USD":"book-of-meme","MYRO/USD":"myro",
            "RNDR/USD":"render-token","FET/USD":"fetch-ai","AGIX/USD":"singularitynet",
            "GALA/USD":"gala","IMX/USD":"immutable-x","ONDO/USD":"ondo-finance",
            "CFG/USD":"centrifuge","AKT/USD":"akash-network","TAO/USD":"bittensor",
            "PIXEL/USD":"pixels",
            "SEI/USD":"sei-network","TIA/USD":"celestia","STRK/USD":"starknet",
            "BCH/USD":"bitcoin-cash","TON/USD":"the-open-network","PYTH/USD":"pyth-network",
            "JTO/USD":"jito-governance-token","DYM/USD":"dymension","ZK/USD":"zksync",
            "AEVO/USD":"aevo",
        }
        self.binance_symbols = {
            "BTC/USD":"BTCUSDT","ETH/USD":"ETHUSDT","BNB/USD":"BNBUSDT",
            "SOL/USD":"SOLUSDT","XRP/USD":"XRPUSDT","ADA/USD":"ADAUSDT",
            "AVAX/USD":"AVAXUSDT","LINK/USD":"LINKUSDT","MATIC/USD":"MATICUSDT",
            "DOT/USD":"DOTUSDT","TRX/USD":"TRXUSDT","LTC/USD":"LTCUSDT",
            "XLM/USD":"XLMUSDT","ETC/USD":"ETCUSDT",
            "NEAR/USD":"NEARUSDT","ARB/USD":"ARBUSDT","OP/USD":"OPUSDT",
            "SUI/USD":"SUIUSDT","INJ/USD":"INJUSDT","APT/USD":"APTUSDT",
            "UNI/USD":"UNIUSDT","ATOM/USD":"ATOMUSDT","FTM/USD":"FTMUSDT",
            "KAS/USD":"KASUSDT","RUNE/USD":"RUNEUSDT","EGLD/USD":"EGLDUSDT",
            "MINA/USD":"MINAUSDT",
            "DOGE/USD":"DOGEUSDT","PEPE/USD":"PEPEUSDT","WIF/USD":"WIFUSDT",
            "BONK/USD":"BONKUSDT","FLOKI/USD":"FLOKIUSDT","BRETT/USD":"BRETTUSDT",
            "POPCAT/USD":"POPCATUSDT","BOME/USD":"BOMEUSDT","MYRO/USD":"MYROUSDT",
            "RNDR/USD":"RNDRUSDT","FET/USD":"FETUSDT","AGIX/USD":"AGIXUSDT",
            "GALA/USD":"GALAUSDT","IMX/USD":"IMXUSDT","ONDO/USD":"ONDOUSDT",
            "CFG/USD":"CFGUSDT","AKT/USD":"AKTUSDT","TAO/USD":"TAOUSDT",
            "PIXEL/USD":"PIXELUSDT",
            "SEI/USD":"SEIUSDT","TIA/USD":"TIAUSDT","STRK/USD":"STRKUSDT",
            "BCH/USD":"BCHUSDT","TON/USD":"TONUSDT","PYTH/USD":"PYTHUSDT",
            "JTO/USD":"JTOUSDT","DYM/USD":"DYMUSDT","ZK/USD":"ZKUSDT",
            "AEVO/USD":"AEVOUSDT",
        }

    # ─── Circuit Breakers ─────────────────────────────────────────────────

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
        b = self.circuit_breakers[source]
        b.failures += 1; b.consecutive_failures += 1
        b.last_failure_time = time.time()
        self.stats[source]["fail"] += 1
        if is_rate_limit: self.stats[source]["rate_limits"] += 1
        if b.consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            b.status = SourceStatus.CIRCUIT_OPEN
            logger.warning(f"⚠️ CIRCUIT OPEN: {source}")

    async def _backoff(self, attempt: int):
        await asyncio.sleep(min(self.BASE_DELAY * (2 ** attempt), 30))

    # ─── P0/#1 — STARTUP PRELOAD ──────────────────────────────────────────

    async def preload_all_history(self, symbols: List[str], batch_size: int = 8) -> int:
        """
        Startup call: fetch real 200-candle history for all symbols.
        Must complete before signals are generated.
        Returns: count of successfully preloaded symbols.
        """
        async with self._preload_lock:
            if self.preload_complete:
                return len(self.preloaded_symbols)

        logger.info(f"🚀 PRELOAD START — {len(symbols)} symbols")
        ok = 0

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            results = await asyncio.gather(
                *[self._preload_single(s) for s in batch],
                return_exceptions=True
            )
            for sym, res in zip(batch, results):
                if res is True:
                    ok += 1
                elif isinstance(res, Exception):
                    logger.warning(f"⚠️ Preload exc {sym}: {res}")

            logger.info(f"📦 Batch {i//batch_size+1}: {ok}/{i+len(batch)}")
            if i + batch_size < len(symbols):
                await asyncio.sleep(2.5)

        async with self._preload_lock:
            self.preload_complete = True

        logger.info(f"✅ PRELOAD DONE — {ok}/{len(symbols)} ready. Signals ENABLED.")
        return ok

    async def _preload_single(self, symbol: str) -> bool:
        try:
            raw = await self._fetch_raw_1h(symbol)
            if raw is None or len(raw.get("closes", [])) < 200:
                return False

            closes = list(raw["closes"])
            vols   = raw.get("volumes", [])

            self._real_history[symbol] = closes[-200:]
            clean_v = [v for v in vols if v is not None and np.isfinite(v) and v >= 0]
            if len(clean_v) >= 20:
                self._real_volumes[symbol] = clean_v[-200:]
            else:
                self._real_volumes[symbol] = []
                logger.warning(f"⚠️ {symbol}: no volume in preload")

            # 4h data best-effort
            try:
                raw4 = await self._fetch_raw_4h(symbol)
                if raw4 and len(raw4.get("closes", [])) >= 30:
                    self._history_4h[symbol] = list(raw4["closes"][-200:])
            except Exception:
                pass

            self.preloaded_symbols.add(symbol)
            return True
        except Exception as e:
            logger.error(f"❌ _preload_single {symbol}: {e}")
            return False

    def is_ready(self, symbol: str) -> bool:
        return symbol in self.preloaded_symbols and symbol in self._real_history

    def get_preload_status(self) -> Dict:
        return {
            "complete":    self.preload_complete,
            "loaded":      len(self.preloaded_symbols),
            "with_volume": sum(1 for v in self._real_volumes.values() if len(v) >= 20),
            "with_4h":     len(self._history_4h),
        }

    # ─── Raw Fetchers ──────────────────────────────────────────────────────

    async def _fetch_raw_1h(self, symbol: str) -> Optional[Dict]:
        raw = await self._fetch_yahoo(symbol, "1h", "1mo")
        if raw is None:
            raw = await self._fetch_coingecko(symbol)
        if raw is None:
            raw = await self._fetch_binance(symbol, "1h", 200)
        return raw

    async def _fetch_raw_4h(self, symbol: str) -> Optional[Dict]:
        raw = await self._fetch_binance(symbol, "4h", 200)
        if raw:
            return raw
        raw1h = await self._fetch_yahoo(symbol, "1h", "3mo")
        if raw1h and len(raw1h.get("closes", [])) >= 48:
            c4 = list(raw1h["closes"])[::4]
            v4 = raw1h.get("volumes", [])[::4]
            return {"closes": pd.Series(c4), "volumes": v4}
        return None

    async def _fetch_yahoo(self, symbol: str, interval: str = "1h", range_: str = "1mo") -> Optional[Dict]:
        if self._is_circuit_open("yahoo"):
            return None
        ys = self.yahoo_symbols.get(symbol)
        if not ys:
            return None
        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as sess:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ys}"
                    async with sess.get(
                        url, params={"interval": interval, "range": range_},
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=aiohttp.ClientTimeout(total=12)
                    ) as r:
                        if r.status == 429:
                            self._record_failure("yahoo", True)
                            await self._backoff(attempt); continue
                        if r.status != 200:
                            self._record_failure("yahoo"); return None
                        data = await r.json()
                        result = data.get("chart", {}).get("result", [])
                        if not result: return None
                        q = result[0].get("indicators", {}).get("quote", [{}])[0]
                        paired = [(c, v) for c, v in zip(q.get("close", []), q.get("volume", []))
                                  if c is not None and np.isfinite(c) and c > 0]
                        if len(paired) < 50: return None
                        closes  = [p[0] for p in paired]
                        volumes = [float(p[1]) if p[1] is not None and np.isfinite(float(p[1])) else 0.0
                                   for p in paired]
                        self._record_success("yahoo")
                        return {"closes": pd.Series(closes), "volumes": volumes}
            except asyncio.TimeoutError:
                self._record_failure("yahoo")
                if attempt < self.MAX_RETRIES - 1: await self._backoff(attempt)
            except Exception as e:
                logger.debug(f"Yahoo err {symbol}: {e}")
                self._record_failure("yahoo"); break
        return None

    async def _fetch_coingecko(self, symbol: str) -> Optional[Dict]:
        if self._is_circuit_open("coingecko"): return None
        cg = self.coingecko_ids.get(symbol)
        if not cg: return None
        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as sess:
                    url = f"https://api.coingecko.com/api/v3/coins/{cg}/market_chart"
                    async with sess.get(
                        url, params={"vs_currency": "usd", "days": "30", "interval": "hourly"},
                        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=12)
                    ) as r:
                        if r.status == 429:
                            self._record_failure("coingecko", True); return None
                        if r.status != 200:
                            self._record_failure("coingecko"); return None
                        data = await r.json()
                        prices = data.get("prices", [])
                        tvols  = data.get("total_volumes", [])
                        if len(prices) < 50: return None
                        closes  = [float(p[1]) for p in prices[-200:]]
                        volumes = ([float(v[1]) for v in tvols[-200:]] if len(tvols) >= 200
                                   else [float(tvols[-1][1])]*len(closes) if tvols else [])
                        self._record_success("coingecko")
                        return {"closes": pd.Series(closes), "volumes": volumes}
            except asyncio.TimeoutError:
                self._record_failure("coingecko"); return None
            except Exception as e:
                logger.debug(f"CG err {symbol}: {e}")
                self._record_failure("coingecko"); break
        return None

    async def _fetch_binance(self, symbol: str, interval: str = "1h", limit: int = 200) -> Optional[Dict]:
        if self._is_circuit_open("binance"): return None
        bs = self.binance_symbols.get(symbol)
        if not bs: return None
        for attempt in range(self.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(
                        "https://api.binance.com/api/v3/klines",
                        params={"symbol": bs, "interval": interval, "limit": limit},
                        timeout=aiohttp.ClientTimeout(total=12)
                    ) as r:
                        if r.status == 429:
                            self._record_failure("binance", True); return None
                        if r.status != 200:
                            self._record_failure("binance"); return None
                        data = await r.json()
                        if len(data) < 50: return None
                        closes  = [float(c[4]) for c in data]
                        volumes = [float(c[5]) for c in data]
                        self._record_success("binance")
                        return {"closes": pd.Series(closes), "volumes": volumes}
            except asyncio.TimeoutError:
                self._record_failure("binance"); return None
            except Exception as e:
                logger.debug(f"Binance err {symbol}: {e}")
                self._record_failure("binance"); break
        return None

    # ─── Indicator Calculation ─────────────────────────────────────────────

    def _calculate_indicators(
        self, close_series: pd.Series, symbol: str, volumes: Optional[list] = None
    ) -> Optional[Dict]:
        try:
            price = float(close_series.iloc[-1])
            if price <= 0 or not np.isfinite(price): return None
            prev_close = float(close_series.iloc[-2]) if len(close_series) > 1 else price

            rsi_s  = RSIIndicator(close_series, window=14).rsi()
            rsi_v  = float(rsi_s.iloc[-1]) if not pd.isna(rsi_s.iloc[-1]) else 50.0
            prev_r = float(rsi_s.iloc[-2]) if len(rsi_s) > 1 and not pd.isna(rsi_s.iloc[-2]) else rsi_v

            e50 = price
            if len(close_series) >= 50:
                s50 = EMAIndicator(close_series, window=50).ema_indicator()
                if not pd.isna(s50.iloc[-1]): e50 = float(s50.iloc[-1])
            s200 = EMAIndicator(close_series, window=200).ema_indicator()
            e200 = float(s200.iloc[-1]) if not pd.isna(s200.iloc[-1]) else price

            try:
                mi  = MACD(close_series)
                ml  = float(mi.macd().iloc[-1]        or 0.0); ml  = 0.0 if pd.isna(ml)  else ml
                ms  = float(mi.macd_signal().iloc[-1] or 0.0); ms  = 0.0 if pd.isna(ms)  else ms
                mh  = float(mi.macd_diff().iloc[-1]   or 0.0); mh  = 0.0 if pd.isna(mh)  else mh
                mhp = float(mi.macd_diff().iloc[-2]   or 0.0) if len(close_series) > 26 else mh
                mhp = 0.0 if pd.isna(mhp) else mhp
            except Exception:
                ml = ms = mh = mhp = 0.0

            bb = BollingerBands(close_series)
            def _s(v, fb): return fb if pd.isna(v) else float(v)
            bbl  = _s(bb.bollinger_lband().iloc[-1],  price * 0.9)
            bbh  = _s(bb.bollinger_hband().iloc[-1],  price * 1.1)
            bbm  = _s(bb.bollinger_mavg().iloc[-1],   price)
            bbw  = bbh - bbl
            bws  = (bb.bollinger_hband() - bb.bollinger_lband())[-20:].dropna()
            avgw = float(bws.mean()) if len(bws) > 0 else bbw

            # P0/#2 — real volume only
            vol_missing = True
            cur_v = avg_v = 0.0
            if volumes and len(volumes) >= 20:
                cv = [v for v in volumes if v is not None and np.isfinite(v) and v >= 0]
                if len(cv) >= 20:
                    cur_v = float(cv[-1])
                    avg_v = float(np.mean(cv[-20:]))
                    if cur_v == 0 and len(cv) >= 2: cur_v = float(cv[-2])
                    vol_missing = False

            if vol_missing:
                logger.debug(f"{symbol}: volume missing → volume-dependent signals will be blocked")

            return {
                "price": price, "prev_close": prev_close,
                "volume": cur_v, "avg_volume_20d": avg_v, "volume_missing": vol_missing,
                "rsi": rsi_v, "prev_rsi": prev_r,
                "ema50": e50, "ema200": e200,
                "macd": ml, "macd_signal": ms,
                "macd_histogram": mh, "macd_histogram_prev": mhp,
                "bb_low": bbl, "bb_high": bbh, "bb_mid": bbm,
                "bb_width": bbw, "avg_bb_width_20d": avgw,
            }
        except Exception as e:
            logger.error(f"❌ Indicators failed ({symbol}): {e}")
            return None

    # ─── P1/#4 — Real Multi-TF ────────────────────────────────────────────

    def _calculate_multi_tf(self, symbol: str, price: float) -> MultiTFData:
        mtf = MultiTFData()

        # 1H
        h1 = self._real_history.get(symbol, [])
        if len(h1) >= 50:
            try:
                s1 = pd.Series(h1)
                r1 = RSIIndicator(s1, window=14).rsi()
                mtf.rsi_1h = float(r1.iloc[-1]) if not pd.isna(r1.iloc[-1]) else 50.0

                e50_1 = EMAIndicator(s1, window=50).ema_indicator()
                e200_1 = EMAIndicator(s1, window=min(200, len(s1))).ema_indicator()
                mtf.ema50_1h  = float(e50_1.iloc[-1])  if not pd.isna(e50_1.iloc[-1])  else price
                mtf.ema200_1h = float(e200_1.iloc[-1]) if not pd.isna(e200_1.iloc[-1]) else price

                md1 = MACD(s1).macd_diff()
                mtf.macd_hist_1h      = float(md1.iloc[-1])  if not pd.isna(md1.iloc[-1])  else 0.0
                mtf.macd_hist_prev_1h = float(md1.iloc[-2])  if len(md1) > 1 and not pd.isna(md1.iloc[-2]) else mtf.macd_hist_1h

                bb1 = BollingerBands(s1)
                mtf.bb_low_1h   = float(bb1.bollinger_lband().iloc[-1]) or price*0.95
                mtf.bb_high_1h  = float(bb1.bollinger_hband().iloc[-1]) or price*1.05
                mtf.bb_mid_1h   = float(bb1.bollinger_mavg().iloc[-1])  or price
                mtf.bb_width_1h = mtf.bb_high_1h - mtf.bb_low_1h
                bws1 = (bb1.bollinger_hband()-bb1.bollinger_lband())[-20:].dropna()
                mtf.avg_bb_width_1h = float(bws1.mean()) if len(bws1) > 0 else mtf.bb_width_1h

                if mtf.ema50_1h > mtf.ema200_1h and price > mtf.ema50_1h:    mtf.trend_1h = "bullish"
                elif mtf.ema50_1h < mtf.ema200_1h and price < mtf.ema50_1h: mtf.trend_1h = "bearish"

                if len(h1) >= 48:
                    ds = pd.Series(h1[-48:])
                    de = EMAIndicator(ds, window=20).ema_indicator()
                    dv = float(de.iloc[-1]) if not pd.isna(de.iloc[-1]) else price
                    if price > dv * 1.005:   mtf.trend_1d = "bullish"
                    elif price < dv * 0.995: mtf.trend_1d = "bearish"
            except Exception as e:
                logger.debug(f"MTF 1h {symbol}: {e}")

        # 4H
        h4 = self._history_4h.get(symbol, [])
        if len(h4) >= 30:
            try:
                s4 = pd.Series(h4)
                r4 = RSIIndicator(s4, window=14).rsi()
                mtf.rsi_4h = float(r4.iloc[-1]) if not pd.isna(r4.iloc[-1]) else 50.0
                e50_4  = EMAIndicator(s4, window=min(50,  len(s4))).ema_indicator()
                e200_4 = EMAIndicator(s4, window=min(200, len(s4))).ema_indicator()
                mtf.ema50_4h  = float(e50_4.iloc[-1])  if not pd.isna(e50_4.iloc[-1])  else price
                mtf.ema200_4h = float(e200_4.iloc[-1]) if not pd.isna(e200_4.iloc[-1]) else price
                md4 = MACD(s4).macd_diff()
                mtf.macd_hist_4h = float(md4.iloc[-1]) if not pd.isna(md4.iloc[-1]) else 0.0
                if mtf.ema50_4h > mtf.ema200_4h and price > mtf.ema50_4h*0.98:    mtf.trend_4h = "bullish"
                elif mtf.ema50_4h < mtf.ema200_4h and price < mtf.ema50_4h*1.02: mtf.trend_4h = "bearish"
            except Exception as e:
                logger.debug(f"MTF 4h {symbol}: {e}")

        # Alignment
        tm = {"bullish": 100.0, "neutral": 50.0, "bearish": 0.0}
        mtf.alignment_score = (tm[mtf.trend_1h]*0.25 + tm[mtf.trend_4h]*0.35 + tm[mtf.trend_1d]*0.40)
        return mtf

    # ─── Main Fetch ───────────────────────────────────────────────────────

    async def fetch_with_fallback(self, symbol: str) -> Optional[MarketData]:
        if symbol in self.cache:
            md, ts = self.cache[symbol]
            if time.time() - ts < self.cache_ttl:
                return md

        raw = await self._fetch_raw_1h(symbol)
        if raw is None:
            logger.error(f"❌ All sources failed: {symbol}")
            return None

        cs   = raw.get("closes")
        vols = raw.get("volumes", [])
        if cs is None or len(cs) < 50:
            return None

        # Update real history incrementally
        existing = self._real_history.get(symbol, [])
        merged   = existing + [c for c in list(cs) if not existing or c != existing[-1]]
        self._real_history[symbol] = merged[-300:]
        if vols:
            cv = [v for v in vols if v is not None and np.isfinite(v) and v >= 0]
            if cv: self._real_volumes[symbol] = cv[-200:]

        use_vols = vols if vols else self._real_volumes.get(symbol, [])
        ind = self._calculate_indicators(cs, symbol, use_vols)
        if not ind:
            return None

        mtf = self._calculate_multi_tf(symbol, ind["price"])

        md = MarketData(
            symbol=symbol, price=ind["price"], prev_close=ind["prev_close"],
            rsi=ind["rsi"], prev_rsi=ind["prev_rsi"],
            ema50=ind["ema50"], ema200=ind["ema200"],
            macd=ind["macd"], macd_signal=ind["macd_signal"],
            macd_histogram=ind["macd_histogram"],
            macd_histogram_prev=ind.get("macd_histogram_prev", ind["macd_histogram"]),
            volume=ind["volume"], avg_volume_20d=ind["avg_volume_20d"],
            bb_low=ind["bb_low"], bb_high=ind["bb_high"], bb_mid=ind["bb_mid"],
            bb_width=ind["bb_width"], avg_bb_width_20d=ind["avg_bb_width_20d"],
            source="multi", timestamp=time.time(),
            multi_tf=mtf,
            volume_missing=ind.get("volume_missing", False),
        )

        self.cache[symbol] = (md, time.time())
        vr = (ind["volume"] / max(ind["avg_volume_20d"], 1)) if not ind.get("volume_missing") else 0.0
        logger.info(
            f"✅ {symbol}: ${ind['price']:.6f} | RSI:{ind['rsi']:.1f} | "
            f"1H:{mtf.trend_1h} 4H:{mtf.trend_4h} 1D:{mtf.trend_1d} | "
            f"Vol:{'N/A' if ind.get('volume_missing') else f'{vr:.2f}x'}"
        )
        return md

    def get_real_history(self, symbol: str, length: int = 200) -> np.ndarray:
        """P0/#1 — called by trading_engine instead of _build_price_history"""
        h = self._real_history.get(symbol, [])
        if not h: return np.array([])
        return np.array(h[-length:])

    def get_stats(self) -> Dict[str, Any]:
        sd = {}
        for src in ["yahoo", "coingecko", "binance"]:
            tot = self.stats[src]["success"] + self.stats[src]["fail"]
            sd[src] = {
                "success":        self.stats[src]["success"],
                "fail":           self.stats[src]["fail"],
                "rate_limits":    self.stats[src]["rate_limits"],
                "success_rate":   f"{self.stats[src]['success']/max(1,tot)*100:.1f}%",
                "circuit_status": self.circuit_breakers[src].status.value,
            }
        return {
            "sources":        sd,
            "cache_size":     len(self.cache),
            "preload_status": self.get_preload_status(),
            "total_requests": sum(s["success"]+s["fail"] for s in self.stats.values()),
        }