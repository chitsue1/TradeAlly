"""
AI Trading Engine v3.1 - Professional Grade + Full Analytics
✅ Strategy-based architecture
✅ Market regime detection
✅ Context-aware decisions
✅ Full analytics tracking
✅ Real-time performance monitoring
✅ Target/Stop-Loss detection
"""

import asyncio
import time
import json
import os
import logging
import numpy as np
from datetime import datetime

from config import *

# ✅ Analytics System
from analytics_system import AnalyticsDatabase, AnalyticsDashboard

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
# POSITION TRACKING (Enhanced with analytics)
# ════════════════════════════════════════════════════════════════

class Position:
    """Enhanced position tracker with analytics integration"""
    def __init__(self, symbol, entry_price, strategy_type, signal_id=None):
        self.symbol = symbol
        self.entry_price = entry_price
        self.strategy_type = strategy_type
        self.signal_id = signal_id  # ✅ NEW: Link to analytics
        self.entry_time = datetime.now().isoformat()
        self.buy_signals_sent = 1

# ════════════════════════════════════════════════════════════════
# TRADING ENGINE V3.1
# ════════════════════════════════════════════════════════════════

class TradingEngine:
    """
    Professional Trading Engine v3.1 with Full Analytics

    არქიტექტურა:
    1. Market Regime Detection
    2. Strategy-based analysis
    3. Signal validation
    4. Analytics recording
    5. Real-time tracking
    6. Target/Stop detection
    """

    def __init__(self):
        logger.info("🔧 Initializing TradingEngine v3.1...")

        # ════════════════════════════════════════════════════════
        # ✅ ANALYTICS SYSTEM
        # ════════════════════════════════════════════════════════

        self.analytics_db = AnalyticsDatabase("trading_analytics.db")
        self.dashboard = AnalyticsDashboard(self.analytics_db)
        self.active_signals = {}  # symbol → signal tracking data

        logger.info("✅ Analytics system initialized")

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
            LongTermStrategy(),
            ScalpingStrategy(),
            OpportunisticStrategy()
        ]

        logger.info(f"✅ {len(self.strategies)} strategies loaded")

        # ════════════════════════════════════════════════════════
        # POSITION MANAGEMENT (Legacy compatibility)
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

        logger.info("✅ TradingEngine v3.1 initialized")

    # ════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ════════════════════════════════════════════════════════════

    def load_positions(self):
        """Load active positions"""
        if os.path.exists(self.positions_file):
            try:
                with open(self.positions_file, 'r') as f:
                    data = json.load(f)
                    positions = {}
                    for symbol, pos_data in data.items():
                        pos = Position(
                            symbol=pos_data['symbol'],
                            entry_price=pos_data['entry_price'],
                            strategy_type=pos_data.get('strategy_type', 'unknown'),
                            signal_id=pos_data.get('signal_id')  # ✅ NEW
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
                    'signal_id': pos.signal_id,  # ✅ NEW
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
    # ✅ SIGNAL SENDING WITH ANALYTICS
    # ════════════════════════════════════════════════════════════

    async def send_signal(self, signal):
        """
        Send TradingSignal via TelegramHandler + Record in Analytics

        ✅ NEW: Full analytics integration
        """

        if not hasattr(self, 'telegram_handler') or self.telegram_handler is None:
            logger.warning("⚠️ Telegram handler not linked")
            return

        try:
            # ✅ 1. VALIDATE SIGNAL (using base_strategy validation)
            strategy = self._get_strategy(signal.strategy_type)
            if strategy and hasattr(strategy, '_validate_signal'):
                is_valid, reason = strategy._validate_signal(signal)
                if not is_valid:
                    logger.warning(f"❌ Invalid signal: {signal.symbol} - {reason}")
                    return

            # ✅ 2. CONVERT TO MESSAGE
            message = signal.to_message()

            # ✅ 3. SEND VIA TELEGRAM
            await self.telegram_handler.broadcast_signal(message, signal.symbol)

            # ✅ 4. RECORD IN ANALYTICS
            signal_id = self.analytics_db.record_signal(signal)

            logger.info(f"✅ Analytics: recorded signal {signal.symbol} (ID: {signal_id})")

            # ✅ 5. START TRACKING
            self.active_signals[signal.symbol] = {
                'signal_id': signal_id,
                'entry_price': signal.entry_price,
                'target_price': signal.target_price,
                'stop_loss': signal.stop_loss_price,
                'strategy': signal.strategy_type.value,
                'entry_time': signal.entry_timestamp
            }

            # ✅ 6. UPDATE STATS
            self.stats['total_signals'] += 1
            self.stats['buy_signals'] += 1

            strategy_key = signal.strategy_type.value
            if strategy_key in self.stats['signals_by_strategy']:
                self.stats['signals_by_strategy'][strategy_key] += 1

            tier = self.get_tier(signal.symbol)
            if tier in self.stats['signals_by_tier']:
                self.stats['signals_by_tier'][tier] += 1

            # ✅ 7. CREATE/UPDATE POSITION (with signal_id)
            if signal.symbol not in self.active_positions:
                position = Position(
                    symbol=signal.symbol,
                    entry_price=signal.entry_price,
                    strategy_type=signal.strategy_type.value,
                    signal_id=signal_id  # ✅ Link to analytics
                )
                self.active_positions[signal.symbol] = position
            else:
                self.active_positions[signal.symbol].buy_signals_sent += 1

            self.save_positions()

            logger.info(
                f"📤 Signal sent & tracked: {signal.action.value} {signal.symbol} "
                f"[{signal.strategy_type.value}] | "
                f"Confidence: {signal.confidence_score:.0f}% | "
                f"Analytics ID: {signal_id}"
            )

        except Exception as e:
            logger.error(f"❌ Send signal error: {e}")

    def _get_strategy(self, strategy_type):
        """Helper to get strategy instance by type"""
        for strategy in self.strategies:
            if strategy.strategy_type == strategy_type:
                return strategy
        return None

    # ════════════════════════════════════════════════════════════
    # ✅ ACTIVE SIGNALS TRACKING (NEW)
    # ════════════════════════════════════════════════════════════

    async def update_active_signals_tracking(self):
        """
        აქტიური სიგნალების tracking და exit conditions check

        ✅ ეს არის ახალი ფუნქცია - გამოიძახება ყოველი scan-ის დროს
        """
        if not self.active_signals:
            return

        logger.debug(f"🔄 Tracking {len(self.active_signals)} active signals...")

        for symbol in list(self.active_signals.keys()):
            try:
                sig_data = self.active_signals[symbol]

                # Get current price
                data = await self.fetch_data(symbol)
                if not data:
                    continue

                current_price = data['price']

                # ✅ RECORD PRICE UPDATE
                self.analytics_db.record_price_update(
                    signal_id=sig_data['signal_id'],
                    symbol=symbol,
                    current_price=current_price,
                    entry_price=sig_data['entry_price'],
                    target_price=sig_data['target_price'],
                    stop_loss=sig_data['stop_loss']
                )

                # Calculate profit
                profit_pct = ((current_price - sig_data['entry_price']) / 
                             sig_data['entry_price']) * 100

                # ✅ CHECK EXIT CONDITIONS

                # 1. TARGET HIT 🎯
                if current_price >= sig_data['target_price']:
                    await self._handle_target_hit(symbol, sig_data, profit_pct)

                # 2. STOP LOSS HIT 🛑
                elif current_price <= sig_data['stop_loss']:
                    await self._handle_stop_loss_hit(symbol, sig_data, profit_pct)

                # 3. TIMEOUT CHECK (7 days)
                elif self._is_signal_expired(sig_data, timeout_days=7):
                    await self._handle_signal_timeout(symbol, sig_data, profit_pct)

            except Exception as e:
                logger.error(f"❌ Error tracking {symbol}: {e}")

    async def _handle_target_hit(self, symbol, sig_data, profit_pct):
        """Target price მიღწეულია ✅"""

        # ✅ RECORD IN ANALYTICS
        self.analytics_db.record_performance(
            signal_id=sig_data['signal_id'],
            outcome='SUCCESS',
            final_profit_pct=profit_pct,
            exit_reason='TARGET_HIT'
        )

        # ✅ NOTIFY ADMIN
        if hasattr(self, 'telegram_handler') and self.telegram_handler:
            message = (
                f"🎯 **TARGET HIT!**\n\n"
                f"**{symbol}**\n"
                f"Entry: ${sig_data['entry_price']:.4f}\n"
                f"Exit: ${sig_data['target_price']:.4f}\n"
                f"Profit: **{profit_pct:+.2f}%**\n\n"
                f"Strategy: {sig_data['strategy']}\n"
                f"✅ Excellent trade!"
            )

            try:
                await self.telegram_handler.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=message,
                    parse_mode='Markdown'
                )
            except:
                pass

        # ✅ CLEANUP
        del self.active_signals[symbol]
        if symbol in self.active_positions:
            del self.active_positions[symbol]
            self.save_positions()

        logger.info(f"🎯 TARGET HIT: {symbol} {profit_pct:+.2f}%")

    async def _handle_stop_loss_hit(self, symbol, sig_data, profit_pct):
        """Stop loss გააქტიურდა ❌"""

        # ✅ RECORD IN ANALYTICS
        self.analytics_db.record_performance(
            signal_id=sig_data['signal_id'],
            outcome='FAILURE',
            final_profit_pct=profit_pct,
            exit_reason='STOP_LOSS'
        )

        # ✅ NOTIFY ADMIN
        if hasattr(self, 'telegram_handler') and self.telegram_handler:
            message = (
                f"🛑 **STOP LOSS HIT**\n\n"
                f"**{symbol}**\n"
                f"Entry: ${sig_data['entry_price']:.4f}\n"
                f"Exit: ${sig_data['stop_loss']:.4f}\n"
                f"Loss: **{profit_pct:+.2f}%**\n\n"
                f"Strategy: {sig_data['strategy']}\n"
                f"⚠️ Risk management activated"
            )

            try:
                await self.telegram_handler.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=message,
                    parse_mode='Markdown'
                )
            except:
                pass

        # ✅ CLEANUP
        del self.active_signals[symbol]
        if symbol in self.active_positions:
            del self.active_positions[symbol]
            self.save_positions()

        logger.info(f"🛑 STOP LOSS: {symbol} {profit_pct:+.2f}%")

    async def _handle_signal_timeout(self, symbol, sig_data, profit_pct):
        """Signal timeout ⏰"""

        # ✅ RECORD IN ANALYTICS
        self.analytics_db.record_performance(
            signal_id=sig_data['signal_id'],
            outcome='EXPIRED',
            final_profit_pct=profit_pct,
            exit_reason='TIMEOUT'
        )

        # ✅ NOTIFY ADMIN (only if significant movement)
        if abs(profit_pct) > 2 and hasattr(self, 'telegram_handler') and self.telegram_handler:
            message = (
                f"⏰ **SIGNAL EXPIRED**\n\n"
                f"**{symbol}**\n"
                f"Entry: ${sig_data['entry_price']:.4f}\n"
                f"Final P/L: **{profit_pct:+.2f}%**\n\n"
                f"Signal closed due to timeout (7 days)"
            )

            try:
                await self.telegram_handler.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=message,
                    parse_mode='Markdown'
                )
            except:
                pass

        # ✅ CLEANUP
        del self.active_signals[symbol]
        if symbol in self.active_positions:
            del self.active_positions[symbol]
            self.save_positions()

        logger.info(f"⏰ TIMEOUT: {symbol} {profit_pct:+.2f}%")

    def _is_signal_expired(self, sig_data, timeout_days=7):
        """Check if signal is expired"""
        entry_time = datetime.fromisoformat(sig_data['entry_time'])
        age = datetime.now() - entry_time
        from datetime import timedelta
        return age > timedelta(days=timeout_days)

    # ════════════════════════════════════════════════════════════
    # MARKET SCAN
    # ════════════════════════════════════════════════════════════

    async def scan_market(self, all_assets):
        """
        Professional market scan v3.1

        Flow:
        1. Update active signals tracking ✅ NEW
        2. Fetch data
        3. Detect regime
        4. Run strategies
        5. Validate & send signals
        6. Print analytics summary ✅ NEW
        """

        logger.info("="*60)
        logger.info(f"🔍 MARKET SCAN v3.1 STARTED")
        logger.info(f"📊 Assets: {len(all_assets)} | Positions: {len(self.active_positions)}")
        logger.info(f"📈 Active Signals: {len(self.active_signals)}")
        logger.info(f"🧠 Strategies: {len(self.strategies)}")
        logger.info("="*60)

        scan_start = time.time()
        success_count = 0
        fail_count = 0
        signals_sent = 0
        opportunities_found = 0

        # ✅ 1. UPDATE ACTIVE SIGNALS TRACKING (FIRST!)
        await self.update_active_signals_tracking()

        # 2. SCAN FOR NEW SIGNALS
        for i, symbol in enumerate(all_assets, 1):
            try:
                logger.info(f"📊 [{i}/{len(all_assets)}] Scanning: {symbol}")

                # ════════════════════════════════════════════════
                # FETCH DATA
                # ════════════════════════════════════════════════

                data = await self.fetch_data(symbol)

                if data is None:
                    fail_count += 1
                    logger.warning(f"⚠️ Data fetch failed: {symbol}")
                    continue

                success_count += 1

                # ════════════════════════════════════════════════
                # MARKET REGIME DETECTION
                # ════════════════════════════════════════════════

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
                # STRATEGY ANALYSIS
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
                    signal = strategy.analyze(
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

                            # Record activity in strategy
                            strategy.record_activity()

                            # Break after first signal
                            break
                        else:
                            logger.debug(f"   Signal rejected: {reason}")

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
        logger.info(f"📈 Active Signals (Analytics): {len(self.active_signals)}")

        # ✅ Strategy stats
        logger.info("📊 Strategy Statistics:")
        for strategy in self.strategies:
            stats = strategy.get_statistics()
            logger.info(
                f"   {strategy.name}: {stats['total_signals']} signals | "
                f"Last: {stats.get('last_signal', 'Never')}"
            )

        logger.info("="*60)

    # ════════════════════════════════════════════════════════════
    # ✅ ANALYTICS SUMMARY (NEW)
    # ════════════════════════════════════════════════════════════

    def print_analytics_summary(self):
        """
        Print analytics summary to logs

        ✅ გამოიძახება ყოველი 10 scan-ის შემდეგ
        """
        try:
            overall = self.analytics_db.get_overall_stats()

            logger.info("")
            logger.info("╔" + "═"*58 + "╗")
            logger.info("║" + " "*18 + "📊 ANALYTICS SUMMARY" + " "*20 + "║")
            logger.info("╠" + "═"*58 + "╣")
            logger.info(f"║ Total Signals: {overall['total_signals']:<43} ║")
            logger.info(f"║ Active: {overall['active_signals']:<49} ║")
            logger.info(f"║ Completed: {overall['completed_trades']:<46} ║")
            logger.info(f"║ Win Rate: {overall['win_rate']:.1f}%{' '*45}║")
            logger.info(f"║ Total Profit: {overall['total_profit']:+.2f}%{' '*42}║")
            logger.info("╚" + "═"*58 + "╝")
            logger.info("")
        except Exception as e:
            logger.debug(f"Could not print analytics: {e}")

    # ════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ════════════════════════════════════════════════════════════

    async def run_forever(self):
        """Main trading loop v3.1"""

        all_assets = CRYPTO + STOCKS + COMMODITIES

        logger.info(f"""
╔════════════════════════════════════════╗
║  TRADING ENGINE v3.1                   ║
║  + FULL ANALYTICS INTEGRATION          ║
╠════════════════════════════════════════╣
║ Mode: Strategy-Based + Analytics
║ Assets: {len(all_assets)}
║ Strategies: {len(self.strategies)}
║ Scan Cycle: {SCAN_INTERVAL/60:.0f}min
║ 
║ Features:
║ • Long-Term Investment
║ • Scalping (intraday)
║ • Opportunistic (spontaneous)
║ • Real-time performance tracking
║ • Target/Stop-Loss detection
║ • Full analytics dashboard
╚════════════════════════════════════════╝
        """)

        consecutive_failures = 0
        scan_count = 0

        while True:
            try:
                scan_count += 1

                await self.scan_market(all_assets)
                consecutive_failures = 0

                # ✅ Print analytics summary every 10 scans
                if scan_count % 10 == 0:
                    self.print_analytics_summary()

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
        returns = np.random.normal(0, 0.02, length-1)
        prices = [current_price]

        for ret in reversed(returns):
            prices.insert(0, prices[0] / (1 + ret))

        return np.array(prices)