"""
═══════════════════════════════════════════════════════════════════════════════
TRADING ENGINE v6.0 - PRODUCTION FINAL
═══════════════════════════════════════════════════════════════════════════════

🎯 ახალი ფიচარები:
✅ EXIT LOGIC INTEGRATION
✅ POSITION MONITORING (real-time)
✅ SELL SIGNAL GENERATION
✅ PROFIT TRACKING (100$ სიმულაცია)
✅ PERFORMANCE ANALYTICS

სტრუქტურა:
1. BUY signal generation (ჩვენი სტრატეგიები)
2. Position registration (exit handler)
3. SELL signal generation (position monitor)
4. Analytics recording

AUTHOR: Trading System Architecture Team
DATE: 2024-02-14
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

# ✅ NEW IMPORTS
from exit_signals_handler import ExitSignalsHandler, ExitReason
from sell_signal_message_generator import SellSignalMessageGenerator
from position_monitor import PositionMonitor

logger = logging.getLogger(__name__)

# Import market_data
logger.info("🔍 Importing market_data...")
try:
    from market_data import MultiSourceDataProvider
    MULTI_SOURCE_AVAILABLE = True
    logger.info("✅ Imported successfully")
except Exception as e:
    MULTI_SOURCE_AVAILABLE = False
    logger.error(f"❌ Error: {e}")

# Import AI
try:
    from ai_risk_evaluator import AIRiskEvaluator, AIDecision
    AI_EVALUATOR_AVAILABLE = True
    logger.info("✅ AI Risk Evaluator imported")
except:
    AI_EVALUATOR_AVAILABLE = False
    logger.warning("⚠️ AI not found")

# ═══════════════════════════════════════════════════════════════════════════
# POSITION CLASS
# ═══════════════════════════════════════════════════════════════════════════

class Position:
    """აქტიური position მონაცემი"""
    def __init__(self, symbol, entry_price, strategy_type, signal_id=None):
        self.symbol = symbol
        self.entry_price = entry_price
        self.strategy_type = strategy_type
        self.signal_id = signal_id
        self.entry_time = datetime.now().isoformat()
        self.buy_signals_sent = 1

# ═══════════════════════════════════════════════════════════════════════════
# TRADING ENGINE v6.0
# ═══════════════════════════════════════════════════════════════════════════

class TradingEngine:
    """
    TRADING ENGINE v6.0

    ✅ სრული cycle: BUY → HOLD → SELL
    ✅ Real-time position monitoring
    ✅ Profit tracking
    """

    def __init__(self):
        logger.info("🔧 TradingEngine v6.0 initializing...")

        # ════════════════════════════════════════════════════════════════════
        # CORE COMPONENTS
        # ════════════════════════════════════════════════════════════════════

        self.telegram_handler = None
        self.analytics_db = AnalyticsDatabase("trading_analytics.db")
        self.dashboard = AnalyticsDashboard(self.analytics_db)

        # ✅ NEW: Exit handler
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
                logger.info("✅ Data provider created")
            except Exception as e:
                logger.error(f"❌ Provider failed: {e}")
                self.use_multi_source = False

        # ════════════════════════════════════════════════════════════════════
        # AI RISK EVALUATOR
        # ════════════════════════════════════════════════════════════════════

        self.ai_enabled = False
        self.ai_evaluator = None

        if AI_EVALUATOR_AVAILABLE and AI_RISK_ENABLED and ANTHROPIC_API_KEY and len(ANTHROPIC_API_KEY) > 20:
            try:
                logger.info("🧠 Creating AI...")
                self.ai_evaluator = AIRiskEvaluator(api_key=ANTHROPIC_API_KEY)
                self.ai_enabled = True
                logger.info("✅ AI ready")
            except Exception as e:
                logger.error(f"❌ AI failed: {e}")

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

        # ════════════════════════════════════════════════════════════════════
        # ✅ POSITION MONITOR
        # ════════════════════════════════════════════════════════════════════

        self.position_monitor = None  # Will be created after telegram_handler set

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
            f"✅ Engine v6.0 ready | "
            f"Data: {'✅' if self.use_multi_source else '❌'} | "
            f"AI: {'✅' if self.ai_enabled else '❌'} | "
            f"Exit Handler: ✅"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # TELEGRAM SETUP
    # ═══════════════════════════════════════════════════════════════════════

    def set_telegram_handler(self, handler):
        """Telegram handler დაკავშირება"""
        self.telegram_handler = handler

        # ✅ ახლა შეგვიძლია Position Monitor გავაშვოთ
        if not self.position_monitor:
            self.position_monitor = PositionMonitor(
                exit_handler=self.exit_handler,
                data_provider=self.data_provider,
                telegram_handler=self.telegram_handler,
                analytics_db=self.analytics_db,
                scan_interval=30  # თითოეული 30 წამი ზეწნა
            )

        logger.info("✅ Telegram linked + Position Monitor created")

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def load_positions(self) -> Dict:
        """აქტიური positions ჩატვირთვა"""
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
        """აქტიური positions შენახვა"""
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
    # TIER DETECTION
    # ═══════════════════════════════════════════════════════════════════════

    def get_tier(self, symbol: str) -> str:
        """ტიერის განსაზღვრა"""
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
        """ბაზარი მონაცემი მიღება"""

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
        """Volume სიმულაცია"""
        vol = 1000000 * np.random.uniform(0.5, 2.5)

        if symbol not in self.volume_history:
            self.volume_history[symbol] = []

        self.volume_history[symbol].append(vol)

        if len(self.volume_history[symbol]) > self.max_volume_history:
            self.volume_history[symbol].pop(0)

        return vol

    def _get_avg_volume(self, symbol: str) -> float:
        """საშუალო volume"""
        if symbol not in self.volume_history or not self.volume_history[symbol]:
            return 1000000
        return np.mean(self.volume_history[symbol])

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL GENERATION & SENDING
    # ═══════════════════════════════════════════════════════════════════════

    async def send_buy_signal(self, signal, ai_eval=None):
        """BUY signal გაგზავნა + Position registration"""

        if not self.telegram_handler:
            return

        try:
            # Generate message
            message = signal.to_message()

            # ✅ AI ქართული message
            if ai_eval:
                message += f"\n\n🧠 **AI შეფასება: {ai_eval.adjusted_confidence:.0f}%**\n"

                if ai_eval.decision.value == "APPROVE":
                    message += "✅ ძლიერი სიგნალი - შედი ახლავე\n"
                elif ai_eval.decision.value == "APPROVE_WITH_CAUTION":
                    message += "⚠️ სიფრთხილით - რისკი საშუალო\n"

                if ai_eval.red_flags:
                    message += "\n🔴 გაფრთხილება:\n"
                    for flag in ai_eval.red_flags[:2]:
                        message += f"• {flag}\n"

                if ai_eval.green_flags:
                    message += "\n🟢 დადებითი:\n"
                    for flag in ai_eval.green_flags[:2]:
                        message += f"• {flag}\n"

            if not message:
                return

            # Record signal in analytics
            try:
                signal_id = self.analytics_db.record_signal(signal)
            except Exception as e:
                logger.error(f"❌ Failed to record signal: {e}")
                signal_id = None

            # ✅ NEW: Register position in exit handler
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
                ai_approved=(ai_eval is not None and ai_eval.decision.value == "APPROVE")
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
        """SELL signal გაგზავნა"""

        if not self.telegram_handler:
            return

        try:
            # Generate message
            message = SellSignalMessageGenerator.generate_sell_message(
                symbol=symbol,
                exit_analysis=exit_analysis
            )

            # Send to Telegram
            await self.telegram_handler.broadcast_signal(
                message=message,
                asset=symbol
            )

            # Update stats
            self.stats['total_signals'] += 1
            self.stats['sell_signals'] += 1

            logger.info(f"✅ SELL signal sent: {symbol}")

        except Exception as e:
            logger.error(f"❌ Failed to send SELL signal: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # MARKET SCANNING
    # ═══════════════════════════════════════════════════════════════════════

    async def scan_market(self, all_assets: List[str]):
        """ბაზარი სკანირება ყველა აქტივზე"""

        logger.info("=" * 70)
        logger.info(
            f"🔍 SCAN | Assets: {len(all_assets)} | "
            f"Data: {'✅' if self.use_multi_source else '❌'} | "
            f"AI: {'✅' if self.ai_enabled else '❌'}"
        )
        logger.info("=" * 70)

        if not self.use_multi_source:
            logger.error("❌ ABORTED - No data provider")
            logger.info("=" * 70)
            logger.info("✅ DONE (0.0min)")
            logger.info("📊 Success: 0/57 | Fail: 57")
            logger.info("=" * 70)
            return

        start = time.time()
        success = fail = signals_generated = signals_sent = ai_rejected = 0

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

                tier = self.get_tier(symbol)

                # ════════════════════════════════════════════════════════════
                # 4. STRATEGY ANALYSIS
                # ════════════════════════════════════════════════════════════

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

                    if signal:
                        signals_generated += 1
                        should_send, reason = strategy.should_send_signal(symbol, signal)

                        if should_send:
                            # ════════════════════════════════════════════════
                            # 5. AI EVALUATION
                            # ════════════════════════════════════════════════

                            ai_eval = None

                            if self.ai_enabled and self.ai_evaluator:
                                logger.info(f"🧠 {symbol}: AI evaluating...")
                                try:
                                    ai_eval = await self.ai_evaluator.evaluate_signal(
                                        symbol=symbol,
                                        strategy_type=strategy.strategy_type.value,
                                        entry_price=signal.entry_price,
                                        strategy_confidence=signal.confidence_score,
                                        indicators=technical,
                                        market_structure={
                                            'nearest_support': market_structure.nearest_support,
                                            'nearest_resistance': market_structure.nearest_resistance,
                                            'volume_trend': market_structure.volume_trend
                                        },
                                        regime=regime.regime.value,
                                        tier=tier
                                    )

                                    ai_should_send, ai_reason = (
                                        self.ai_evaluator.should_send_signal(ai_eval)
                                    )

                                    if ai_should_send:
                                        signals_sent += 1
                                        self.stats['ai_approved'] += 1
                                        logger.info(f"✅ {symbol}: AI APPROVED")
                                        await self.send_buy_signal(signal, ai_eval)
                                        strategy.record_activity()
                                    else:
                                        ai_rejected += 1
                                        self.stats['ai_rejected'] += 1
                                        logger.info(f"❌ {symbol}: AI REJECTED")

                                except Exception as e:
                                    logger.error(f"❌ AI error: {e}")
                                    # Fallback: send anyway
                                    signals_sent += 1
                                    await self.send_buy_signal(signal)
                                    strategy.record_activity()
                            else:
                                signals_sent += 1
                                await self.send_buy_signal(signal)
                                strategy.record_activity()

                            break

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
        """ძირითადი loop - თითოეული scan-ის შემდეგ position monitor გაშვება"""

        all_assets = CRYPTO + STOCKS + COMMODITIES

        logger.info(
            f"""
╔════════════════════════════════════════╗
║  ENGINE v6.0 PRODUCTION               ║
║  Data: {'ACTIVE' if self.use_multi_source else 'INACTIVE'} | AI: {'ACTIVE' if self.ai_enabled else 'INACTIVE'}
║  Assets: {len(all_assets)} | Strategies: {len(self.strategies)}
║  Exit Handler: ✅
║  Position Monitor: {'✅ READY' if self.position_monitor else '❌ PENDING'}
╚════════════════════════════════════════╝
            """
        )

        # ✅ START POSITION MONITOR
        if self.position_monitor:
            await self.position_monitor.start_monitoring()
            logger.info("✅ Position Monitor დაიწყო")
        else:
            logger.warning("⚠️ Position Monitor not initialized")

        scan_count = 0

        while True:
            try:
                scan_count += 1
                logger.info(f"\n🔄 SCAN #{scan_count}")

                # Market scan
                await self.scan_market(all_assets)

                # Position monitor is running in background
                # მას აქვს თავი საკუთარი async task

                logger.info(
                    f"⏸️ Next scan in {SCAN_INTERVAL/60:.0f}min... "
                    f"(Position Monitor აკვლია background-ში)"
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
        """ფასის ისტორია სიმულაცია"""
        returns = np.random.normal(0, 0.02, length - 1)
        prices = [current_price]

        for ret in reversed(returns):
            prices.insert(0, prices[0] / (1 + ret))

        return np.array(prices)

    # ═══════════════════════════════════════════════════════════════════════
    # STATUS COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    def get_engine_status(self) -> str:
        """Engine status"""

        active_pos = len(self.active_positions)
        exit_stats = self.exit_handler.get_exit_statistics()

        status = f"""
📊 **ENGINE STATUS**

**Components:**
├─ Data Provider: {'✅' if self.use_multi_source else '❌'}
├─ AI Evaluator: {'✅' if self.ai_enabled else '❌'}
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
"""

        return status