"""
AI Trading Engine v3.0 - Professional Grade
✅ Strategy-based architecture
✅ Market regime detection
✅ Context-aware decisions
✅ NO spam - only real opportunities
"""

import asyncio
import time
import json
import os
import logging
import numpy as np
from datetime import datetime

from config import *

# Market Regime Detector
from market_regime import MarketRegimeDetector

# Strategies
from strategies.long_term_strategy import LongTermStrategy
from strategies.scalping_strategy import ScalpingStrategy
from strategies.opportunistic_strategy import OpportunisticStrategy

# Multi-source data provider
try:
    from market_data import MultiSourceDataProvider
    MULTI_SOURCE_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ market_data.py imported")
except ImportError as e:
    MULTI_SOURCE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error(f"❌ market_data.py import failed: {e}")

# ════════════════════════════════════════════════════════════════
# POSITION TRACKING (Simple version for compatibility)
# ════════════════════════════════════════════════════════════════

class Position:
    """Simple position tracker"""
    def __init__(self, symbol, entry_price, strategy_type):
        self.symbol = symbol
        self.entry_price = entry_price
        self.strategy_type = strategy_type
        self.entry_time = datetime.now().isoformat()
        self.buy_signals_sent = 1

# ════════════════════════════════════════════════════════════════
# TRADING ENGINE V3
# ════════════════════════════════════════════════════════════════

class TradingEngine:
    """
    Professional Trading Engine

    არქიტექტურა:
    1. Market Regime Detection
    2. Strategy-based analysis
    3. Signal validation
    4. Execution (via TelegramHandler)
    """

    def __init__(self):
        logger.info("🔧 Initializing TradingEngine v3.0...")

        # ════════════════════════════════════════════════════════
        # DATA PROVIDER
        # ════════════════════════════════════════════════════════

        if MULTI_SOURCE_AVAILABLE:
            try:
                self.data_provider = MultiSourceDataProvider(
                    twelve_data_key=TWELVE_DATA_API_KEY,
                    alpaca_key=ALPACA_API_KEY,
                    alpaca_secret=ALPACA_SECRET_KEY
                )
                self.use_multi_source = True
                logger.info("✅ Multi-source provider initialized")
            except Exception as e:
                logger.error(f"❌ Multi-source init failed: {e}")
                self.use_multi_source = False
        else:
            self.use_multi_source = False
            logger.warning("⚠️ Fallback mode")

        # ════════════════════════════════════════════════════════
        # REGIME DETECTOR & STRATEGIES
        # ════════════════════════════════════════════════════════

        self.regime_detector = MarketRegimeDetector()

        self.strategies = [
            LongTermStrategy({}),
            ScalpingStrategy({}),
            OpportunisticStrategy({})
        ]

        logger.info(f"✅ {len(self.strategies)} strategies loaded")

        # ════════════════════════════════════════════════════════
        # POSITION MANAGEMENT
        # ════════════════════════════════════════════════════════

        self.positions_file = "active_positions.json"
        self.active_positions = self.load_positions()

        # ════════════════════════════════════════════════════════
        # STATISTICS
        # ════════════════════════════════════════════════════════

        self.stats = {
            'total_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'signals_by_strategy': {
                'long_term': 0,
                'scalping': 0,
                'opportunistic': 0
            },
            'signals_by_tier': {
                'BLUE_CHIP': 0,
                'HIGH_GROWTH': 0,
                'MEME': 0,
                'NARRATIVE': 0,
                'EMERGING': 0
            }
        }

        logger.info("✅ TradingEngine v3.0 initialized")

    # ════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ════════════════════════════════════════════════════════════

    def load_positions(self):
        """Load active positions"""
        if os.path.exists(self.positions_file):
            try:
                with open(self.positions_file, 'r') as f:
                    data = json.load(f)
                    # Simple conversion
                    positions = {}
                    for symbol, pos_data in data.items():
                        pos = Position(
                            symbol=pos_data['symbol'],
                            entry_price=pos_data['entry_price'],
                            strategy_type=pos_data.get('strategy_type', 'unknown')
                        )
                        pos.buy_signals_sent = pos_data.get('buy_signals_sent', 1)
                        positions[symbol] = pos
                    return positions
            except Exception as e:
                logger.error(f"❌ Position load error: {e}")
        return {}

    def save_positions(self):
        """Save active positions"""
        try:
            data = {}
            for symbol, pos in self.active_positions.items():
                data[symbol] = {
                    'symbol': pos.symbol,
                    'entry_price': pos.entry_price,
                    'strategy_type': pos.strategy_type,
                    'entry_time': pos.entry_time,
                    'buy_signals_sent': pos.buy_signals_sent
                }
            with open(self.positions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Position save error: {e}")

    def get_tier(self, symbol: str) -> str:
        """Tier-ის განსაზღვრა"""
        if symbol in TIER_1_BLUE_CHIPS:
            return "BLUE_CHIP"
        elif symbol in TIER_2_HIGH_GROWTH:
            return "HIGH_GROWTH"
        elif symbol in TIER_3_MEME_COINS:
            return "MEME"
        elif symbol in TIER_4_NARRATIVE:
            return "NARRATIVE"
        elif symbol in TIER_5_EMERGING:
            return "EMERGING"
        else:
            return "OTHER"

    # ════════════════════════════════════════════════════════════
    # DATA FETCHING
    # ════════════════════════════════════════════════════════════

    async def fetch_data(self, symbol: str):
        """Data fetching with multi-source support"""
        try:
            if self.use_multi_source:
                market_data = await self.data_provider.fetch_with_fallback(symbol)

                if market_data is None:
                    return None

                return {
                    "price": market_data.price,
                    "rsi": market_data.rsi,
                    "ema200": market_data.ema200,
                    "bb_low": market_data.bb_low,
                    "bb_high": market_data.bb_high,
                    "source": market_data.source
                }
            else:
                # Fallback mode (basic fetch)
                logger.warning(f"⚠️ Fallback mode for {symbol}")
                return None

        except Exception as e:
            logger.error(f"❌ Fetch error {symbol}: {e}")
            return None

    # ════════════════════════════════════════════════════════════
    # SIGNAL SENDING
    # ════════════════════════════════════════════════════════════

    async def send_signal(self, signal):
        """Send TradingSignal via TelegramHandler"""

        if not hasattr(self, 'telegram_handler') or self.telegram_handler is None:
            logger.warning("⚠️ Telegram handler not linked")
            return

        # Convert TradingSignal to message
        message = signal.to_message()

        # Send via TelegramHandler
        try:
            await self.telegram_handler.broadcast_signal(message, signal.symbol)

            # Update stats
            self.stats['total_signals'] += 1
            self.stats['buy_signals'] += 1

            strategy_key = signal.strategy_type.value
            if strategy_key in self.stats['signals_by_strategy']:
                self.stats['signals_by_strategy'][strategy_key] += 1

            tier = self.get_tier(signal.symbol)
            if tier in self.stats['signals_by_tier']:
                self.stats['signals_by_tier'][tier] += 1

            # Create/update position
            if signal.symbol not in self.active_positions:
                position = Position(
                    symbol=signal.symbol,
                    entry_price=signal.entry_price,
                    strategy_type=signal.strategy_type.value
                )
                self.active_positions[signal.symbol] = position
            else:
                self.active_positions[signal.symbol].buy_signals_sent += 1

            self.save_positions()

            logger.info(
                f"📤 Signal sent: {signal.action.value} {signal.symbol} "
                f"[{signal.strategy_type.value}] | "
                f"Confidence: {signal.confidence_score:.0f}%"
            )

        except Exception as e:
            logger.error(f"❌ Send signal error: {e}")

    # ════════════════════════════════════════════════════════════
    # MARKET SCAN
    # ════════════════════════════════════════════════════════════

    async def scan_market(self, all_assets):
        """
        Professional market scan

        Flow:
        1. Fetch data
        2. Detect regime
        3. Run strategies
        4. Validate & send signals
        """

        logger.info("="*60)
        logger.info(f"🔍 MARKET SCAN v3.0 STARTED")
        logger.info(f"📊 Assets: {len(all_assets)} | Positions: {len(self.active_positions)}")
        logger.info(f"🧠 Strategies: {len(self.strategies)}")
        logger.info("="*60)

        scan_start = time.time()
        success_count = 0
        fail_count = 0
        signals_sent = 0
        opportunities_found = 0

        for i, symbol in enumerate(all_assets, 1):
            try:
                logger.info(f"📊 [{i}/{len(all_assets)}] Scanning: {symbol}")

                # ════════════════════════════════════════════════
                # 1. FETCH DATA
                # ════════════════════════════════════════════════

                data = await self.fetch_data(symbol)

                if data is None:
                    fail_count += 1
                    logger.warning(f"⚠️ Data fetch failed: {symbol}")
                    continue

                success_count += 1

                # ════════════════════════════════════════════════
                # 2. MARKET REGIME DETECTION
                # ════════════════════════════════════════════════

                # Get price history (mock for now - replace with real data)
                price_history = self._generate_mock_price_history(
                    data['price'], 200
                )

                regime_analysis = self.regime_detector.analyze_regime(
                    symbol=symbol,
                    price=data['price'],
                    price_history=price_history,
                    rsi=data['rsi'],
                    ema200=data['ema200'],
                    bb_low=data['bb_low'],
                    bb_high=data['bb_high']
                )

                logger.info(
                    f"   Regime: {regime_analysis.regime.value} | "
                    f"Confidence: {regime_analysis.confidence:.0f}% | "
                    f"Structural: {regime_analysis.is_structural}"
                )

                # ════════════════════════════════════════════════
                # 3. STRATEGY ANALYSIS
                # ════════════════════════════════════════════════

                tier = self.get_tier(symbol)
                existing_position = self.active_positions.get(symbol)

                technical_data = {
                    'rsi': data['rsi'],
                    'ema200': data['ema200'],
                    'bb_low': data['bb_low'],
                    'bb_high': data['bb_high']
                }

                for strategy in self.strategies:
                    signal = await strategy.analyze(
                        symbol=symbol,
                        price=data['price'],
                        regime_analysis=regime_analysis,
                        technical_data=technical_data,
                        tier=tier,
                        existing_position=existing_position
                    )

                    if signal:
                        opportunities_found += 1

                        # Validate signal
                        should_send, reason = strategy.should_send_signal(
                            symbol, signal
                        )

                        if should_send:
                            signals_sent += 1
                            logger.info(
                                f"🎯 SIGNAL: {signal.strategy_type.value} | "
                                f"{symbol} @ ${signal.entry_price:.4f} | "
                                f"Confidence: {signal.confidence_score:.0f}%"
                            )

                            await self.send_signal(signal)

                            # Log to strategy
                            strategy.log_signal(signal)

                            # Break after first signal (no multiple strategies on same asset)
                            break
                        else:
                            logger.debug(
                                f"   Signal rejected: {reason}"
                            )

                # Delay
                await asyncio.sleep(ASSET_DELAY)

            except Exception as e:
                fail_count += 1
                logger.error(f"❌ Scan error {symbol}: {e}")

        # ════════════════════════════════════════════════════════
        # SCAN SUMMARY
        # ════════════════════════════════════════════════════════

        duration = time.time() - scan_start

        logger.info("="*60)
        logger.info(f"✅ SCAN COMPLETE ({duration/60:.1f}min)")
        logger.info(f"📊 Success: {success_count}/{len(all_assets)}")
        logger.info(f"❌ Failed: {fail_count}")
        logger.info(f"🔍 Opportunities: {opportunities_found}")
        logger.info(f"📤 Signals Sent: {signals_sent}")
        logger.info(f"📂 Open Positions: {len(self.active_positions)}")

        # Strategy stats
        logger.info("📊 Strategy Statistics:")
        for strategy in self.strategies:
            stats = strategy.get_statistics()
            logger.info(
                f"   {strategy.name}: {stats['total_signals']} signals"
            )

        logger.info("="*60)

    # ════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ════════════════════════════════════════════════════════════

    async def run_forever(self):
        """Main trading loop"""

        all_assets = CRYPTO + STOCKS + COMMODITIES

        logger.info(f"""
╔════════════════════════════════════════╗
║  TRADING ENGINE v3.0 (PROFESSIONAL)    ║
╠════════════════════════════════════════╣
║ Mode: Strategy-Based
║ Assets: {len(all_assets)}
║ Strategies: {len(self.strategies)}
║ Scan Cycle: {SCAN_INTERVAL/60:.0f}min
║ 
║ Strategies:
║ • Long-Term Investment
║ • Scalping (intraday)
║ • Opportunistic (spontaneous)
╚════════════════════════════════════════╝
        """)

        consecutive_failures = 0

        while True:
            try:
                await self.scan_market(all_assets)
                consecutive_failures = 0

                logger.info(f"⏸️ Next scan in {SCAN_INTERVAL/60:.0f}min...")
                await asyncio.sleep(SCAN_INTERVAL)

            except Exception as e:
                consecutive_failures += 1
                logger.error(f"🚨 Scan error ({consecutive_failures}/3): {e}")

                if consecutive_failures >= 3:
                    logger.error("💥 Emergency mode (30min cooldown)")
                    await asyncio.sleep(1800)
                    consecutive_failures = 0
                else:
                    await asyncio.sleep(300)

    # ════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════

    def _generate_mock_price_history(self, current_price: float, length: int) -> np.ndarray:
        """
        Mock price history generator

        TODO: Replace with real historical data fetching
        """
        # Simple random walk
        returns = np.random.normal(0, 0.02, length-1)
        prices = [current_price]

        for ret in reversed(returns):
            prices.insert(0, prices[0] / (1 + ret))

        return np.array(prices)