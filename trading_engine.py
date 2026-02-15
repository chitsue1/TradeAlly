"""
═══════════════════════════════════════════════════════════════════════════════
TRADING ENGINE v6.0 - PHASE 2 COMPLETE INTEGRATION
═══════════════════════════════════════════════════════════════════════════════

✅ Phase 1: Market Structure Integration
✅ Phase 2: AI v2 Professional Context (15+ indicators, divergences, rich analysis)

RATING: 7.5/10 (Ready for Phase 3)

🎯 Features:
- Multi-source data (Yahoo, CoinGecko, Binance)
- AI Risk Evaluator v2 with professional trading context
- 4 strategies (Long-term, Swing, Scalping, Opportunistic)
- Exit monitoring & SELL signals
- Position tracking
- Analytics & Performance monitoring
- Divergence detection
- Trade history learning

AUTHOR: Trading System v6.0
DATE: 2024-02-15
"""

import asyncio
import time
import json
import os
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from config import *
from analytics_system import AnalyticsDatabase, AnalyticsDashboard
from market_regime import MarketRegimeDetector
from market_structure_builder import MarketStructureBuilder
from strategies.long_term_strategy import LongTermStrategy
from strategies.scalping_strategy import ScalpingStrategy
from strategies.opportunistic_strategy import OpportunisticStrategy
from strategies.swing_strategy import SwingStrategy

# Exit & Position Monitoring
from exit_signals_handler import ExitSignalsHandler, ExitReason
from sell_signal_message_generator import SellSignalMessageGenerator
from position_monitor import PositionMonitor

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# DATA PROVIDER
# ═══════════════════════════════════════════════════════════════════════════

logger.info("🔍 Importing market_data...")
try:
    from market_data import MultiSourceDataProvider
    MULTI_SOURCE_AVAILABLE = True
    logger.info("✅ MultiSourceDataProvider imported")
except Exception as e:
    MULTI_SOURCE_AVAILABLE = False
    logger.error(f"❌ Market data import error: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# AI RISK EVALUATOR v2 - PHASE 2 ENHANCED
# ═══════════════════════════════════════════════════════════════════════════

try:
    from ai_risk_evaluator_v2 import (
        AIRiskEvaluatorV2,
        TechnicalIndicators,
        MarketStructureContext,
        DivergenceAnalysis,
        MarketRegimeContext,
        PreviousTrade,
        AIDecision
    )
    AI_EVALUATOR_AVAILABLE = True
    logger.info("✅ AI Risk Evaluator v2 imported (PHASE 2)")
except Exception as e:
    AI_EVALUATOR_AVAILABLE = False
    logger.warning(f"⚠️ AI v2 not found: {e}")

# Divergence Detector (PHASE 2)
try:
    from divergence_detector import DivergenceDetector
    DIVERGENCE_AVAILABLE = True
    logger.info("✅ Divergence detector imported")
except:
    DIVERGENCE_AVAILABLE = False
    logger.warning("⚠️ Divergence detector not available")

# ═══════════════════════════════════════════════════════════════════════════
# POSITION CLASS
# ═══════════════════════════════════════════════════════════════════════════

class Position:
    """Active position data"""
    def __init__(self, symbol, entry_price, strategy_type, signal_id=None):
        self.symbol = symbol
        self.entry_price = entry_price
        self.strategy_type = strategy_type
        self.signal_id = signal_id
        self.entry_time = datetime.now().isoformat()
        self.buy_signals_sent = 1

# ═══════════════════════════════════════════════════════════════════════════
# TRADING ENGINE v6.0 - PHASE 2 COMPLETE
# ═══════════════════════════════════════════════════════════════════════════

class TradingEngine:
    """
    TRADING ENGINE v6.0 - PHASE 2 COMPLETE

    ✅ Full BUY → HOLD → SELL cycle
    ✅ AI v2 with professional context
    ✅ Real-time position monitoring
    ✅ Profit tracking & analytics
    """

    def __init__(self):
        logger.info("🔧 TradingEngine v6.0 (Phase 2) initializing...")

        # ════════════════════════════════════════════════════════════════════
        # CORE COMPONENTS
        # ════════════════════════════════════════════════════════════════════

        self.telegram_handler = None
        self.analytics_db = AnalyticsDatabase("trading_analytics.db")
        self.dashboard = AnalyticsDashboard(self.analytics_db)
        self.exit_handler = ExitSignalsHandler()

        # ════════════════════════════════════════════════════════════════════
        # DATA PROVIDER
        # ════════════════════════════════════════════════════════════════════

        self.use_multi_source = False
        self.data_provider = None

        if MULTI_SOURCE_AVAILABLE:
            try:
                logger.info("🔄 Creating data provider...")
                self.data_provider = MultiSourceDataProvider(
                    twelve_data_key=TWELVE_DATA_API_KEY,
                    alpaca_key=ALPACA_API_KEY,
                    alpaca_secret=ALPACA_SECRET_KEY
                )
                self.use_multi_source = True
                logger.info("✅ Data provider ready")
            except Exception as e:
                logger.error(f"❌ Provider init failed: {e}")
                self.use_multi_source = False

        # ════════════════════════════════════════════════════════════════════
        # AI RISK EVALUATOR v2 (PHASE 2)
        # ════════════════════════════════════════════════════════════════════

        self.ai_enabled = False
        self.ai_evaluator = None

        if AI_EVALUATOR_AVAILABLE and AI_RISK_ENABLED and ANTHROPIC_API_KEY and len(ANTHROPIC_API_KEY) > 20:
            try:
                logger.info("🧠 Initializing AI Risk Evaluator v2...")
                self.ai_evaluator = AIRiskEvaluatorV2(api_key=ANTHROPIC_API_KEY)
                self.ai_enabled = True
                logger.info("✅ AI v2 ready - Professional trading context enabled")
            except Exception as e:
                logger.error(f"❌ AI v2 initialization failed: {e}")
                self.ai_enabled = False
        else:
            logger.warning("⚠️ AI disabled - Check: AI_RISK_ENABLED, ANTHROPIC_API_KEY")

        # Divergence detector (PHASE 2)
        self.divergence_detector = DivergenceDetector() if DIVERGENCE_AVAILABLE else None

        # Price history for divergence tracking (PHASE 2)
        self._price_history = {}  # {symbol: [{'price': x, 'rsi': y, 'macd': z, 'time': t}]}
        self._max_price_history = 20

        # ════════════════════════════════════════════════════════════════════
        # ANALYSIS COMPONENTS
        # ════════════════════════════════════════════════════════════════════

        self.regime_detector = MarketRegimeDetector()
        self.structure_builder = MarketStructureBuilder()
        self.strategies = [
            LongTermStrategy(),
            SwingStrategy(),
            ScalpingStrategy(),
            OpportunisticStrategy()
        ]

        logger.info(f"✅ {len(self.strategies)} strategies loaded")

        # ════════════════════════════════════════════════════════════════════
        # POSITION TRACKING
        # ════════════════════════════════════════════════════════════════════

        self.positions_file = "active_positions.json"
        self.active_positions = self.load_positions()
        self.volume_history = {}
        self.max_volume_history = 20

        # Position monitor (initialized after telegram_handler set)
        self.position_monitor = None

        # ════════════════════════════════════════════════════════════════════
        # STATISTICS
        # ════════════════════════════════════════════════════════════════════

        self.stats = {
            'total_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'ai_approved': 0,
            'ai_rejected': 0,
            'signals_by_strategy': {
                'long_term': 0,
                'swing': 0,
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

        logger.info(
            f"✅ Engine v6.0 (Phase 2) ready\n"
            f"   Data: {'✅' if self.use_multi_source else '❌'}\n"
            f"   AI v2: {'✅' if self.ai_enabled else '❌'}\n"
            f"   Divergence: {'✅' if self.divergence_detector else '❌'}\n"
            f"   Exit Handler: ✅"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # TELEGRAM SETUP
    # ═══════════════════════════════════════════════════════════════════════

    def set_telegram_handler(self, handler):
        """Link telegram handler"""
        self.telegram_handler = handler

        # Initialize position monitor
        if not self.position_monitor:
            self.position_monitor = PositionMonitor(
                exit_handler=self.exit_handler,
                data_provider=self.data_provider,
                telegram_handler=self.telegram_handler,
                analytics_db=self.analytics_db,
                scan_interval=30
            )

        logger.info("✅ Telegram linked + Position Monitor created")

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def load_positions(self) -> Dict:
        """Load active positions from file"""
        if os.path.exists(self.positions_file):
            try:
                with open(self.positions_file, 'r') as f:
                    data = json.load(f)
                    positions = {}
                    for symbol, pos_data in data.items():
                        pos = Position(
                            pos_data['symbol'],
                            pos_data['entry_price'],
                            pos_data.get('strategy_type', 'unknown'),
                            pos_data.get('signal_id')
                        )
                        pos.buy_signals_sent = pos_data.get('buy_signals_sent', 1)
                        positions[symbol] = pos
                    return positions
            except:
                pass
        return {}

    def save_positions(self):
        """Save active positions to file"""
        try:
            data = {}
            for symbol, pos in self.active_positions.items():
                data[symbol] = {
                    'symbol': pos.symbol,
                    'entry_price': pos.entry_price,
                    'strategy_type': pos.strategy_type,
                    'signal_id': pos.signal_id,
                    'entry_time': pos.entry_time,
                    'buy_signals_sent': pos.buy_signals_sent
                }
            with open(self.positions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save positions: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # PRICE HISTORY TRACKING (PHASE 2 - for divergence detection)
    # ═══════════════════════════════════════════════════════════════════════

    def _update_price_history(self, symbol: str, price: float, rsi: float, macd_hist: float):
        """Track price history for divergence detection"""
        if symbol not in self._price_history:
            self._price_history[symbol] = []

        self._price_history[symbol].append({
            'price': price,
            'rsi': rsi,
            'macd_histogram': macd_hist,
            'time': datetime.now().isoformat()
        })

        # Keep only last N records
        if len(self._price_history[symbol]) > self._max_price_history:
            self._price_history[symbol].pop(0)

    # ═══════════════════════════════════════════════════════════════════════
    # TIER DETECTION
    # ═══════════════════════════════════════════════════════════════════════

    def get_tier(self, symbol: str) -> str:
        """Determine asset tier"""
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
        return "OTHER"

    # ═══════════════════════════════════════════════════════════════════════
    # DATA FETCHING
    # ═══════════════════════════════════════════════════════════════════════

    async def fetch_data(self, symbol: str) -> Optional[Dict]:
        """Fetch market data from provider"""

        if not self.use_multi_source or not self.data_provider:
            return None

        try:
            market_data = await self.data_provider.fetch_with_fallback(symbol)
            if not market_data:
                return None

            data = {
                "price": market_data.price,
                "prev_close": market_data.prev_close,
                "rsi": market_data.rsi,
                "prev_rsi": market_data.prev_rsi,
                "ema50": market_data.ema50,
                "ema200": market_data.ema200,
                "macd": market_data.macd,
                "macd_signal": market_data.macd_signal,
                "macd_histogram": market_data.macd_histogram,
                "macd_histogram_prev": getattr(
                    market_data,
                    'macd_histogram_prev',
                    market_data.macd_histogram
                ),
                "bb_low": market_data.bb_low,
                "bb_high": market_data.bb_high,
                "bb_mid": market_data.bb_mid,
                "bb_width": market_data.bb_width,
                "avg_bb_width_20d": market_data.avg_bb_width_20d,
                "source": market_data.source
            }

            # Volume simulation
            data['volume'] = self._get_simulated_volume(symbol)
            data['avg_volume_20d'] = self._get_avg_volume(symbol)

            return data

        except Exception as e:
            logger.error(f"❌ Data fetch error {symbol}: {e}")
            return None

    def _get_simulated_volume(self, symbol: str) -> float:
        """Simulate volume"""
        vol = 1000000 * np.random.uniform(0.5, 2.5)

        if symbol not in self.volume_history:
            self.volume_history[symbol] = []

        self.volume_history[symbol].append(vol)

        if len(self.volume_history[symbol]) > self.max_volume_history:
            self.volume_history[symbol].pop(0)

        return vol

    def _get_avg_volume(self, symbol: str) -> float:
        """Get average volume"""
        if symbol not in self.volume_history or not self.volume_history[symbol]:
            return 1000000
        return np.mean(self.volume_history[symbol])

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL GENERATION & SENDING
    # ═══════════════════════════════════════════════════════════════════════

    async def send_buy_signal(self, signal, ai_eval=None):
        """Send BUY signal with AI v2 insights"""

        if not self.telegram_handler:
            return

        try:
            # Generate base message
            message = signal.to_message()

            # ✅ AI v2 insights (PHASE 2)
            if ai_eval:
                message += f"\n\n🧠 **AI შეფასება v2:**\n"
                message += f"├─ Claude Confidence: {ai_eval.claude_confidence:.0f}%\n"
                message += f"├─ Adjustment: {ai_eval.confidence_adjustment:+d}%\n"
                message += f"└─ R:R: 1:{ai_eval.risk_reward_ratio:.2f}\n"

                if ai_eval.decision == "APPROVE":
                    message += "\n✅ **AI რეკომენდაცია: ძლიერი შესვლა**\n"
                elif ai_eval.decision == "CAUTION":
                    message += "\n⚠️ **AI რეკომენდაცია: სიფრთხილით**\n"

                # Red flags (max 2)
                if ai_eval.red_flags:
                    message += "\n🔴 **გაფრთხილება:**\n"
                    for flag in ai_eval.red_flags[:2]:
                        message += f"• {flag}\n"

                # Green flags (max 2)
                if ai_eval.green_flags:
                    message += "\n🟢 **დადებითი:**\n"
                    for flag in ai_eval.green_flags[:2]:
                        message += f"• {flag}\n"

                # Professional notes
                if ai_eval.trader_notes:
                    message += f"\n💡 **პროფესიონალის შენიშვნა:**\n{ai_eval.trader_notes[:150]}\n"

            if not message:
                return

            # Record signal in analytics
            try:
                signal_id = self.analytics_db.record_signal(signal)
            except Exception as e:
                logger.error(f"❌ Failed to record signal: {e}")
                signal_id = None

            # Register position in exit handler
            self.exit_handler.register_position(
                symbol=signal.symbol,
                entry_price=signal.entry_price,
                target_price=signal.target_price,
                stop_loss_price=signal.stop_loss_price,
                entry_time=signal.entry_timestamp,
                signal_confidence=signal.confidence_score,
                expected_profit_min=signal.expected_profit_min,
                expected_profit_max=signal.expected_profit_max,
                strategy_type=signal.strategy_type.value,
                signal_id=signal_id,
                ai_approved=(ai_eval is not None and ai_eval.decision == "APPROVE")
            )

            # Send to Telegram
            await self.telegram_handler.broadcast_signal(
                message=message,
                asset=signal.symbol
            )

            # Track in local positions
            if signal.symbol not in self.active_positions:
                self.active_positions[signal.symbol] = Position(
                    signal.symbol,
                    signal.entry_price,
                    signal.strategy_type.value,
                    signal_id
                )

            self.save_positions()

            # Update stats
            self.stats['total_signals'] += 1
            self.stats['buy_signals'] += 1
            self.stats['signals_by_strategy'][signal.strategy_type.value] += 1

            logger.info(f"✅ BUY signal sent: {signal.symbol}")

        except Exception as e:
            logger.error(f"❌ Failed to send signal: {e}")

    async def send_sell_signal(self, symbol: str, exit_analysis):
        """Send SELL signal"""

        if not self.telegram_handler:
            return

        try:
            message = SellSignalMessageGenerator.generate_sell_message(
                symbol=symbol,
                exit_analysis=exit_analysis
            )

            await self.telegram_handler.broadcast_signal(
                message=message,
                asset=symbol
            )

            self.stats['total_signals'] += 1
            self.stats['sell_signals'] += 1

            logger.info(f"✅ SELL signal sent: {symbol}")

        except Exception as e:
            logger.error(f"❌ Failed to send SELL signal: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # MARKET SCANNING - PHASE 2 ENHANCED
    # ═══════════════════════════════════════════════════════════════════════

    async def scan_market(self, all_assets: List[str]):
        """Scan market with AI v2 professional context"""

        logger.info("=" * 70)
        logger.info(
            f"🔍 SCAN | Assets: {len(all_assets)} | "
            f"Data: {'✅' if self.use_multi_source else '❌'} | "
            f"AI v2: {'✅' if self.ai_enabled else '❌'}"
        )
        logger.info("=" * 70)

        if not self.use_multi_source:
            logger.error("❌ ABORTED - No data provider")
            return

        start = time.time()
        success = fail = signals_generated = signals_sent = ai_rejected = 0

        MIN_CONFIDENCE_FOR_AI = 55

        for symbol in all_assets:
            try:
                # ════════════════════════════════════════════════════════════
                # 1. FETCH DATA
                # ════════════════════════════════════════════════════════════

                data = await self.fetch_data(symbol)
                if not data:
                    fail += 1
                    continue

                success += 1

                # ════════════════════════════════════════════════════════════
                # 2. MARKET ANALYSIS
                # ════════════════════════════════════════════════════════════

                price_history = self._generate_mock_price_history(data['price'], 200)
                regime = self.regime_detector.analyze_regime(
                    symbol,
                    data['price'],
                    price_history,
                    data['rsi'],
                    data['ema200'],
                    data['bb_low'],
                    data['bb_high']
                )

                market_structure = self.structure_builder.build(
                    symbol,
                    data['price'],
                    data,
                    regime
                )

                # ════════════════════════════════════════════════════════════
                # 3. PREPARE TECHNICAL DATA
                # ════════════════════════════════════════════════════════════

                technical = {
                    k: data[k]
                    for k in [
                        'rsi', 'prev_rsi', 'ema50', 'ema200',
                        'macd', 'macd_signal', 'macd_histogram',
                        'bb_low', 'bb_high', 'bb_mid', 'bb_width',
                        'avg_bb_width_20d', 'volume', 'avg_volume_20d',
                        'prev_close'
                    ]
                }
                technical['macd_histogram_prev'] = data.get(
                    'macd_histogram_prev',
                    data['macd_histogram']
                )

                # ✅ Update price history (PHASE 2)
                self._update_price_history(
                    symbol, 
                    data['price'], 
                    technical['rsi'],
                    technical['macd_histogram']
                )

                tier = self.get_tier(symbol)

                # ════════════════════════════════════════════════════════════
                # 4. STRATEGY ANALYSIS
                # ════════════════════════════════════════════════════════════

                best_signal = None
                best_confidence = 0

                for strategy in self.strategies:
                    signal = strategy.analyze(
                        symbol,
                        data['price'],
                        regime,
                        technical,
                        tier,
                        self.active_positions.get(symbol),
                        market_structure
                    )

                    if signal and signal.confidence_score > best_confidence:
                        best_signal = signal
                        best_confidence = signal.confidence_score

                if not best_signal:
                    continue

                signals_generated += 1

                # ════════════════════════════════════════════════════════════
                # 5. PRE-AI FILTERING
                # ════════════════════════════════════════════════════════════

                if best_signal.confidence_score < MIN_CONFIDENCE_FOR_AI:
                    logger.debug(
                        f"⏭️ {symbol}: Confidence low ({best_signal.confidence_score:.0f}%)"
                    )
                    continue

                strategy_instance = next(
                    (s for s in self.strategies 
                     if s.strategy_type == best_signal.strategy_type),
                    None
                )

                if strategy_instance:
                    should_send, reason = strategy_instance.should_send_signal(
                        symbol, best_signal
                    )

                    if not should_send:
                        logger.debug(f"⏭️ {symbol}: Strategy NO - {reason}")
                        continue

                # ════════════════════════════════════════════════════════════
                # 6. AI v2 EVALUATION (PHASE 2 - RICH CONTEXT)
                # ════════════════════════════════════════════════════════════

                ai_eval = None

                if self.ai_enabled and self.ai_evaluator:
                    logger.info(f"🧠 {symbol}: AI v2 evaluating ({best_signal.confidence_score:.0f}%)...")

                    try:
                        # ════════════════════════════════════════════════════
                        # Prepare TechnicalIndicators (15+ indicators)
                        # ════════════════════════════════════════════════════

                        bb_range = technical['bb_high'] - technical['bb_low']
                        bb_position = (data['price'] - technical['bb_low']) / bb_range if bb_range > 0 else 0.5

                        indicators = TechnicalIndicators(
                            rsi=technical['rsi'],
                            ema50=technical['ema50'],
                            ema200=technical['ema200'],
                            ema_distance_pct=((technical['ema50'] - technical['ema200']) / technical['ema200']) * 100,
                            macd=technical['macd'],
                            macd_signal=technical['macd_signal'],
                            macd_histogram=technical['macd_histogram'],
                            bb_low=technical['bb_low'],
                            bb_mid=technical['bb_mid'],
                            bb_high=technical['bb_high'],
                            bb_position=bb_position,
                            volume=technical['volume'],
                            avg_volume_20d=technical['avg_volume_20d'],
                            volume_ratio=technical['volume'] / technical['avg_volume_20d'] if technical['avg_volume_20d'] > 0 else 1.0,
                            atr=technical.get('atr', bb_range / 2)  # Approximate ATR
                        )

                        # ════════════════════════════════════════════════════
                        # Prepare MarketStructureContext
                        # ════════════════════════════════════════════════════

                        market_structure_context = MarketStructureContext(
                            nearest_support=market_structure.nearest_support,
                            nearest_resistance=market_structure.nearest_resistance,
                            support_strength=market_structure.support_strength,
                            resistance_strength=market_structure.resistance_strength,
                            support_distance_pct=market_structure.support_distance_pct,
                            resistance_distance_pct=market_structure.resistance_distance_pct,
                            volume_trend=market_structure.volume_trend,
                            structure_quality=market_structure.structure_quality
                        )

                        # ════════════════════════════════════════════════════
                        # Detect Divergences (PHASE 2)
                        # ════════════════════════════════════════════════════

                        rsi_divergence = False
                        rsi_strength = 0
                        macd_divergence = False
                        macd_strength = 0
                        price_volume_divergence = False

                        if self.divergence_detector and symbol in self._price_history and len(self._price_history[symbol]) >= 3:
                            hist = self._price_history[symbol]

                            # Extract lists
                            prices = [h['price'] for h in hist]
                            rsi_values = [h['rsi'] for h in hist]
                            macd_hists = [h['macd_histogram'] for h in hist]

                            # RSI divergence
                            rsi_result = self.divergence_detector.detect_rsi_divergence(prices, rsi_values)
                            if rsi_result.has_divergence and rsi_result.divergence_type == 'bullish':
                                rsi_divergence = True
                                rsi_strength = rsi_result.strength

                            # MACD divergence
                            macd_result = self.divergence_detector.detect_macd_divergence(prices, macd_hists)
                            if macd_result.has_divergence and macd_result.divergence_type == 'bullish':
                                macd_divergence = True
                                macd_strength = macd_result.strength

                            # Price-volume divergence
                            volumes = [technical['volume']] * len(prices)  # Simplified
                            pv_result = self.divergence_detector.detect_price_volume_divergence(prices, volumes)
                            price_volume_divergence = pv_result.has_divergence

                        divergences = DivergenceAnalysis(
                            rsi_bullish_divergence=rsi_divergence,
                            rsi_bullish_strength=rsi_strength,
                            macd_bullish_divergence=macd_divergence,
                            macd_bullish_strength=macd_strength,
                            price_volume_divergence=price_volume_divergence,
                            divergence_type='bullish' if (rsi_divergence or macd_divergence) else None
                        )

                        # ════════════════════════════════════════════════════
                        # Prepare MarketRegimeContext
                        # ════════════════════════════════════════════════════

                        regime_context = MarketRegimeContext(
                            regime=regime.regime.value,
                            volatility_percentile=regime.volatility_percentile,
                            volume_trend=market_structure.volume_trend,
                            warning_flags=regime.warning_flags
                        )

                        # ════════════════════════════════════════════════════
                        # Get Previous Trades (Learning Loop)
                        # ════════════════════════════════════════════════════

                        previous_trades = []

                        if hasattr(self.ai_evaluator, 'trade_history') and self.ai_evaluator.trade_history:
                            similar = [
                                PreviousTrade(
                                    symbol=t.symbol,
                                    entry_price=t.entry_price,
                                    exit_price=t.exit_price,
                                    profit_pct=t.profit_pct,
                                    days_held=int(t.days_held),
                                    strategy=t.strategy,
                                    market_regime=t.market_regime,
                                    similarity_score=t.similarity_score
                                )
                                for t in self.ai_evaluator.trade_history[-10:]
                                if t.symbol == symbol or t.strategy == best_signal.strategy_type.value
                            ]
                            previous_trades = similar[:5]

                        # ════════════════════════════════════════════════════
                        # 🧠 CALL AI v2 - PROFESSIONAL EVALUATION
                        # ════════════════════════════════════════════════════

                        ai_decision = await self.ai_evaluator.evaluate_signal(
                            symbol=symbol,
                            strategy_type=best_signal.strategy_type.value,
                            entry_price=best_signal.entry_price,
                            strategy_confidence=best_signal.confidence_score,
                            indicators=indicators,
                            market_structure=market_structure_context,
                            divergences=divergences,
                            regime=regime_context,
                            previous_trades=previous_trades,
                            tier=tier
                        )

                        # ════════════════════════════════════════════════════
                        # Process AI Decision
                        # ════════════════════════════════════════════════════

                        logger.info(
                            f"🧠 {symbol}: AI Decision: {ai_decision.decision}\n"
                            f"   Claude Confidence: {ai_decision.claude_confidence:.0f}%\n"
                            f"   Adjustment: {ai_decision.confidence_adjustment:+d}%\n"
                            f"   R:R: 1:{ai_decision.risk_reward_ratio:.2f}\n"
                            f"   Red Flags: {len(ai_decision.red_flags)}\n"
                            f"   Green Flags: {len(ai_decision.green_flags)}"
                        )

                        if ai_decision.decision == "APPROVE":
                            adjusted_confidence = min(
                                best_signal.confidence_score + ai_decision.confidence_adjustment,
                                100
                            )

                            if ai_decision.recommended_stop_loss > 0:
                                best_signal.stop_loss_price = ai_decision.recommended_stop_loss

                            if ai_decision.recommended_target_price > 0:
                                best_signal.target_price = ai_decision.recommended_target_price

                            best_signal.confidence_score = adjusted_confidence

                            if ai_decision.green_flags:
                                best_signal.supporting_reasons.extend(ai_decision.green_flags[:2])

                            if ai_decision.red_flags:
                                best_signal.risk_factors.extend(ai_decision.red_flags[:2])

                            signals_sent += 1
                            self.stats['ai_approved'] += 1

                            logger.info(f"✅ {symbol}: AI APPROVED - Sending signal")

                            ai_eval = ai_decision
                            await self.send_buy_signal(best_signal, ai_eval)

                            if strategy_instance:
                                strategy_instance.record_activity()

                        elif ai_decision.decision == "CAUTION":
                            best_signal.risk_level = "HIGH"
                            best_signal.confidence_score = max(
                                best_signal.confidence_score + ai_decision.confidence_adjustment,
                                45
                            )

                            signals_sent += 1
                            self.stats['ai_approved'] += 1

                            logger.warning(f"⚠️ {symbol}: AI CAUTION - Sending with warning")

                            ai_eval = ai_decision
                            await self.send_buy_signal(best_signal, ai_eval)

                        else:  # REJECT
                            ai_rejected += 1
                            self.stats['ai_rejected'] += 1

                            logger.info(
                                f"❌ {symbol}: AI REJECTED\n"
                                f"   Reason: {ai_decision.reasoning[:100]}\n"
                                f"   Red Flags: {', '.join(ai_decision.red_flags[:3])}"
                            )

                    except Exception as e:
                        logger.error(f"❌ AI v2 error for {symbol}: {e}")
                        import traceback
                        logger.error(traceback.format_exc())

                        # Fallback
                        if best_signal.confidence_score >= 70:
                            signals_sent += 1
                            await self.send_buy_signal(best_signal)
                            if strategy_instance:
                                strategy_instance.record_activity()

                else:
                    # AI disabled
                    if best_signal.confidence_score >= 65:
                        signals_sent += 1
                        await self.send_buy_signal(best_signal)
                        if strategy_instance:
                            strategy_instance.record_activity()

                await asyncio.sleep(ASSET_DELAY)

            except Exception as e:
                logger.error(f"❌ Error scanning {symbol}: {e}")
                fail += 1
                continue

        # ════════════════════════════════════════════════════════════════════
        # REPORT
        # ════════════════════════════════════════════════════════════════════

        duration = (time.time() - start) / 60
        logger.info("=" * 70)
        logger.info(f"✅ DONE ({duration:.1f}min)")
        logger.info(f"📊 Success: {success}/{len(all_assets)} | Fail: {fail}")
        logger.info(
            f"🔍 Generated: {signals_generated} → "
            f"🧠 AI Rejected: {ai_rejected} → "
            f"📤 Sent: {signals_sent}"
        )
        logger.info("=" * 70)

    # ═══════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ═══════════════════════════════════════════════════════════════════════

    async def run_forever(self):
        """Main trading loop with position monitoring"""

        all_assets = CRYPTO + STOCKS + COMMODITIES

        logger.info(
            f"""
╔════════════════════════════════════════╗
║  ENGINE v6.0 PHASE 2 PRODUCTION       ║
║  Data: {'ACTIVE' if self.use_multi_source else 'INACTIVE'} | AI v2: {'ACTIVE' if self.ai_enabled else 'INACTIVE'}
║  Assets: {len(all_assets)} | Strategies: {len(self.strategies)}
║  Exit Handler: ✅
║  Position Monitor: {'✅ READY' if self.position_monitor else '❌ PENDING'}
╚════════════════════════════════════════╝
            """
        )

        # Start position monitor
        if self.position_monitor:
            await self.position_monitor.start_monitoring()
            logger.info("✅ Position Monitor started")
        else:
            logger.warning("⚠️ Position Monitor not initialized")

        scan_count = 0

        while True:
            try:
                scan_count += 1
                logger.info(f"\n🔄 SCAN #{scan_count}")

                await self.scan_market(all_assets)

                logger.info(
                    f"⏸️ Next scan in {SCAN_INTERVAL/60:.0f}min... "
                    f"(Position Monitor running in background)"
                )

                await asyncio.sleep(SCAN_INTERVAL)

            except KeyboardInterrupt:
                logger.info("⌨️ Interrupted by user")
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                await asyncio.sleep(300)

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _generate_mock_price_history(self, current_price: float, length: int):
        """Generate mock price history for analysis"""
        returns = np.random.normal(0, 0.02, length - 1)
        prices = [current_price]

        for ret in reversed(returns):
            prices.insert(0, prices[0] / (1 + ret))

        return np.array(prices)

    def get_engine_status(self) -> str:
        """Get engine status report"""

        active_pos = len(self.active_positions)
        exit_stats = self.exit_handler.get_exit_statistics()

        status = f"""
📊 **ENGINE STATUS v6.0 (Phase 2)**

**Components:**
├─ Data Provider: {'✅' if self.use_multi_source else '❌'}
├─ AI Evaluator v2: {'✅' if self.ai_enabled else '❌'}
├─ Divergence Detector: {'✅' if self.divergence_detector else '❌'}
├─ Exit Handler: ✅
└─ Position Monitor: {'✅ Running' if self.position_monitor and self.position_monitor.is_monitoring else '❌'}

**Positions:**
├─ Active: {active_pos}
├─ Closed: {exit_stats.get('total_exits', 0)}
└─ Win Rate: {exit_stats.get('win_rate', 0):.1f}%

**Statistics:**
├─ Total Signals: {self.stats['total_signals']}
├─ Buy: {self.stats['buy_signals']} | Sell: {self.stats['sell_signals']}
├─ AI Approved: {self.stats['ai_approved']} | Rejected: {self.stats['ai_rejected']}
└─ AI Rejection Rate: {(self.stats['ai_rejected'] / max(1, self.stats['ai_approved'] + self.stats['ai_rejected']) * 100):.1f}%
"""

        return status