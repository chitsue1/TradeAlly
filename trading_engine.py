"""
AI Trading Bot - Trading Engine (Debug Version)
ამ ვერსიაში დამატებულია verbose logging პრობლემის გამოსავლენად
"""

import asyncio
import time
import json
import os
import logging

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from config import *

# ✅ TEMPORARY: Import check
try:
    from market_data import MultiSourceDataProvider
    MULTI_SOURCE_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ market_data.py successfully imported")
except ImportError as e:
    MULTI_SOURCE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error(f"❌ Failed to import market_data.py: {e}")
    logger.error("⚠️ Falling back to TwelveData-only mode")

# ========================
# FALLBACK: Simple Rate Limiter (if market_data.py missing)
# ========================
class SimpleFallbackLimiter:
    def __init__(self, max_per_minute=8):
        self.max_per_minute = max_per_minute
        self.requests = []

    async def wait_if_needed(self):
        now = time.time()
        self.requests = [t for t in self.requests if now - t < 60]

        if len(self.requests) >= self.max_per_minute:
            wait_time = 60 - (now - self.requests[0]) + 2
            logger.info(f"⏱️ Rate limit: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            self.requests = []

        self.requests.append(now)

# ========================
# TRADING ENGINE
# ========================
class TradingEngine:
    def __init__(self):
        logger.info("🔧 Initializing TradingEngine...")

        # ✅ Try multi-source provider, fallback if not available
        if MULTI_SOURCE_AVAILABLE:
            try:
                self.data_provider = MultiSourceDataProvider(
                    twelve_data_key=TWELVE_DATA_API_KEY,
                    alpaca_key=getattr(self, 'ALPACA_API_KEY', None),
                    alpaca_secret=getattr(self, 'ALPACA_SECRET_KEY', None)
                )
                self.use_multi_source = True
                logger.info("✅ Multi-source data provider initialized")
            except Exception as e:
                logger.error(f"❌ Multi-source init failed: {e}")
                self.use_multi_source = False
                self.fallback_limiter = SimpleFallbackLimiter(8)
        else:
            self.use_multi_source = False
            self.fallback_limiter = SimpleFallbackLimiter(8)
            logger.warning("⚠️ Using fallback mode (TwelveData only)")

        self.knowledge = self.load_trading_knowledge()
        self.active_positions = {}
        self.last_scan_time = 0

        logger.info("✅ TradingEngine initialized")

    def load_trading_knowledge(self):
        """PDF-ებიდან ამოღებული სავაჭრო ცოდნის ჩატვირთვა"""
        if os.path.exists(KNOWLEDGE_BASE_FILE):
            try:
                with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"patterns": [], "strategies": []}

    async def fetch_data_multi_source(self, symbol):
        """Multi-source fetch (new method)"""
        try:
            logger.debug(f"🔍 Fetching {symbol} via multi-source...")
            market_data = await self.data_provider.fetch_with_fallback(symbol)

            if market_data is None:
                logger.warning(f"⚠️ All sources failed for {symbol}")
                return None

            logger.info(f"✅ {symbol}: ${market_data.price:.2f} [source: {market_data.source}]")

            return {
                "price": market_data.price,
                "rsi": market_data.rsi,
                "ema200": market_data.ema200,
                "bb_low": market_data.bb_low,
                "bb_high": market_data.bb_high,
                "source": market_data.source
            }

        except Exception as e:
            logger.error(f"❌ Error fetching {symbol} (multi-source): {e}")
            return None

    async def fetch_data_fallback(self, symbol):
        """Fallback: Direct TwelveData (if market_data.py unavailable)"""
        try:
            import aiohttp
            import pandas as pd
            from ta.trend import EMAIndicator
            from ta.momentum import RSIIndicator
            from ta.volatility import BollingerBands

            await self.fallback_limiter.wait_if_needed()

            logger.debug(f"🔍 Fetching {symbol} via TwelveData fallback...")

            async with aiohttp.ClientSession() as session:
                url = "https://api.twelvedata.com/time_series"
                params = {
                    "symbol": symbol,
                    "interval": INTERVAL,
                    "apikey": TWELVE_DATA_API_KEY,
                    "outputsize": 200
                }

                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 429:
                        logger.error(f"🚨 TwelveData rate limited for {symbol}")
                        return None

                    if resp.status != 200:
                        logger.error(f"❌ TwelveData returned {resp.status} for {symbol}")
                        return None

                    data = await resp.json()

                    if data.get('status') == 'error':
                        logger.error(f"❌ API Error {symbol}: {data.get('message')}")
                        return None

                    df = pd.DataFrame(data.get('values', []))
                    if df.empty:
                        logger.error(f"❌ No data for {symbol}")
                        return None

                    df['close'] = pd.to_numeric(df['close'])
                    close = df['close'].iloc[::-1]

                    # Calculate indicators
                    rsi = RSIIndicator(close).rsi().iloc[-1]
                    ema200 = EMAIndicator(close, window=200).ema_indicator().iloc[-1]
                    bb = BollingerBands(close)

                    logger.info(f"✅ {symbol}: ${close.iloc[-1]:.2f} [source: twelvedata_fallback]")

                    return {
                        "price": close.iloc[-1],
                        "rsi": rsi,
                        "ema200": ema200,
                        "bb_low": bb.bollinger_lband().iloc[-1],
                        "bb_high": bb.bollinger_hband().iloc[-1],
                        "source": "twelvedata_fallback"
                    }

        except Exception as e:
            logger.error(f"❌ Error fetching {symbol} (fallback): {e}")
            return None

    async def fetch_data(self, symbol):
        """Main fetch method with automatic routing"""
        if self.use_multi_source:
            return await self.fetch_data_multi_source(symbol)
        else:
            return await self.fetch_data_fallback(symbol)

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
        if sentiment.get('fg_index', 50) < 30:
            score += 15
            reasons.append(f"😱 ბაზარზე პანიკაა ({sentiment['fg_index']})")

        # 5. PDF ცოდნის შემოწმება
        if any(p in str(reasons).lower() for p in self.knowledge.get('patterns', [])):
            score += 10
            reasons.append("🧠 PDF ცოდნამ დაადასტურა ნიმუში")

        return score, reasons

    async def scan_market(self, all_assets):
        """
        Market scan with extensive logging for debugging
        """
        logger.info("="*60)
        logger.info(f"🔍 STARTING MARKET SCAN")
        logger.info(f"📊 Assets to scan: {len(all_assets)}")
        logger.info(f"⏱️ Scan interval: {SCAN_INTERVAL}s ({SCAN_INTERVAL/60:.1f} min)")
        logger.info(f"⏳ Delay per asset: {ASSET_DELAY}s")
        logger.info(f"🔌 Mode: {'Multi-source' if self.use_multi_source else 'TwelveData fallback'}")
        logger.info("="*60)

        scan_start = time.time()
        success_count = 0
        fail_count = 0

        for i, symbol in enumerate(all_assets, 1):
            try:
                logger.info(f"📊 [{i}/{len(all_assets)}] Scanning: {symbol}")

                # Fetch data
                data = await self.fetch_data(symbol)

                if data is None:
                    fail_count += 1
                    logger.warning(f"⚠️ [{i}/{len(all_assets)}] Failed: {symbol}")
                else:
                    success_count += 1
                    logger.info(f"✅ [{i}/{len(all_assets)}] Success: {symbol} - ${data['price']:.2f} (RSI: {data['rsi']:.1f})")

                # Delay before next asset
                logger.debug(f"⏳ Waiting {ASSET_DELAY}s before next asset...")
                await asyncio.sleep(ASSET_DELAY)

            except Exception as e:
                fail_count += 1
                logger.error(f"❌ [{i}/{len(all_assets)}] Error scanning {symbol}: {e}")

        # Summary
        scan_duration = time.time() - scan_start
        success_rate = (success_count / len(all_assets)) * 100 if len(all_assets) > 0 else 0

        logger.info("="*60)
        logger.info(f"✅ SCAN CYCLE COMPLETE")
        logger.info(f"⏱️ Duration: {scan_duration/60:.1f} minutes")
        logger.info(f"📊 Success: {success_count}/{len(all_assets)} ({success_rate:.1f}%)")
        logger.info(f"❌ Failed: {fail_count}/{len(all_assets)}")

        if self.use_multi_source:
            try:
                stats = self.data_provider.get_stats()
                logger.info(f"📈 Provider Statistics:")
                for source, data in stats['sources'].items():
                    logger.info(f"   {source:12s}: {data['success']:3d} OK, {data['fail']:3d} FAIL")
                logger.info(f"   Cache size: {stats['cache_size']}")
            except:
                pass

        logger.info("="*60)

        self.last_scan_time = time.time()

    async def run_forever(self):
        """Main loop with error recovery"""
        all_assets = CRYPTO + STOCKS + COMMODITIES

        logger.info(f"""
╔════════════════════════════════════════╗
║    TRADING ENGINE STARTED              ║
╠════════════════════════════════════════╣
║ Mode: {'Multi-Source' if self.use_multi_source else 'Fallback (TwelveData)'}
║ Assets: {len(all_assets)}
║ Scan Cycle: {SCAN_INTERVAL/60:.0f} minutes
╚════════════════════════════════════════╝
        """)

        consecutive_failures = 0
        max_failures = 3

        while True:
            try:
                logger.info(f"🚀 Starting scan cycle {consecutive_failures + 1}...")

                # Mock sentiment (replace with real API later)
                sentiment = {"fg_index": 32}

                await self.scan_market(all_assets)

                consecutive_failures = 0  # Reset on success

                logger.info(f"⏸️ Next scan in {SCAN_INTERVAL/60:.0f} minutes...")
                await asyncio.sleep(SCAN_INTERVAL)

            except Exception as e:
                consecutive_failures += 1
                logger.error(f"🚨 Scan error ({consecutive_failures}/{max_failures}): {e}")

                if consecutive_failures >= max_failures:
                    logger.error(f"💥 Too many failures - entering emergency mode")
                    await asyncio.sleep(1800)  # 30 min cooldown
                    consecutive_failures = 0
                else:
                    await asyncio.sleep(300)  # 5 min retry