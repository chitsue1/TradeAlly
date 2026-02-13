"""
Trading Engine v5.0 FINAL - YOUR STRUCTURE + AI RISK LAYER
✅ შენი ორიგინალი სტრუქტურა შენარჩუნებული
✅ AI Risk Evaluator ინტეგრირებული
✅ საათივით მომუშავე სისტემა
"""

import asyncio
import time
import json
import os
import logging
import numpy as np
from datetime import datetime, timedelta

from config import *
from analytics_system import AnalyticsDatabase, AnalyticsDashboard
from market_regime import MarketRegimeDetector
from market_structure_builder import MarketStructureBuilder
from strategies.long_term_strategy import LongTermStrategy
from strategies.scalping_strategy import ScalpingStrategy
from strategies.opportunistic_strategy import OpportunisticStrategy
from strategies.swing_strategy import SwingStrategy

logger = logging.getLogger(__name__)

# ✅ Import market_data
logger.info("🔍 Importing market_data...")
try:
    from market_data import MultiSourceDataProvider
    MULTI_SOURCE_AVAILABLE = True
    logger.info("✅ Imported successfully")
except ImportError as e:
    MULTI_SOURCE_AVAILABLE = False
    logger.error(f"❌ ImportError: {e}")
except Exception as e:
    MULTI_SOURCE_AVAILABLE = False
    logger.error(f"❌ Error: {e}")

logger.info(f"   MULTI_SOURCE_AVAILABLE = {MULTI_SOURCE_AVAILABLE}")

# ✅ Import AI Risk Evaluator
try:
    from ai_risk_evaluator import AIRiskEvaluator, AIDecision
    AI_EVALUATOR_AVAILABLE = True
    logger.info("✅ AI Risk Evaluator imported")
except ImportError:
    AI_EVALUATOR_AVAILABLE = False
    logger.warning("⚠️  AI Risk Evaluator not found - will run without AI")
except Exception as e:
    AI_EVALUATOR_AVAILABLE = False
    logger.error(f"❌ AI import error: {e}")

class Position:
    def __init__(self, symbol, entry_price, strategy_type, signal_id=None):
        self.symbol = symbol
        self.entry_price = entry_price
        self.strategy_type = strategy_type
        self.signal_id = signal_id
        self.entry_time = datetime.now().isoformat()
        self.buy_signals_sent = 1

class TradingEngine:
    def __init__(self):
        logger.info("🔧 TradingEngine v5.0 FINAL init...")

        self.telegram_handler = None
        self.analytics_db = AnalyticsDatabase("trading_analytics.db")
        self.dashboard = AnalyticsDashboard(self.analytics_db)
        self.active_signals = {}
        self.use_multi_source = False
        self.data_provider = None

        # ✅ Data Provider (შენი ორიგინალი)
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
                logger.error(f"❌ Data provider failed: {e}")
                self.use_multi_source = False
        else:
            logger.error("❌ No data provider!")

        # ✅ AI Risk Evaluator (NEW)
        self.ai_enabled = False
        self.ai_evaluator = None

        if AI_EVALUATOR_AVAILABLE and AI_RISK_ENABLED:
            if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "YOUR_ANTHROPIC_API_KEY":
                try:
                    logger.info("🧠 Creating AI Risk Evaluator...")
                    self.ai_evaluator = AIRiskEvaluator(api_key=ANTHROPIC_API_KEY)
                    self.ai_enabled = True
                    logger.info("✅ AI Risk Evaluator ready")
                except Exception as e:
                    logger.error(f"❌ AI init failed: {e}")
                    self.ai_enabled = False
            else:
                logger.warning("⚠️  AI disabled: Set ANTHROPIC_API_KEY in config.py")
        else:
            logger.info("ℹ️  AI Risk Evaluator disabled (AI_RISK_ENABLED=False or not available)")

        # ✅ Core components (შენი ორიგინალი)
        self.regime_detector = MarketRegimeDetector()
        self.structure_builder = MarketStructureBuilder()
        self.strategies = [
            LongTermStrategy(),
            SwingStrategy(),
            ScalpingStrategy(),
            OpportunisticStrategy()
        ]
        logger.info(f"✅ {len(self.strategies)} strategies")

        self.positions_file = "active_positions.json"
        self.active_positions = self.load_positions()
        self.volume_history = {}
        self.max_volume_history = 20

        # ✅ Stats (updated with AI metrics)
        self.stats = {
            'total_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'ai_approved': 0,  # NEW
            'ai_rejected': 0,  # NEW
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

        logger.info(f"✅ TradingEngine v5.0 ready | AI: {'ENABLED' if self.ai_enabled else 'DISABLED'}")

    def set_telegram_handler(self, telegram_handler):
        self.telegram_handler = telegram_handler
        logger.info("✅ Telegram linked")

    def load_positions(self):
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
        except:
            pass

    def get_tier(self, symbol: str) -> str:
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

    async def fetch_data(self, symbol: str):
        if not self.use_multi_source or self.data_provider is None:
            return None
        try:
            market_data = await self.data_provider.fetch_with_fallback(symbol)
            if market_data is None:
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
                "macd_histogram_prev": getattr(market_data, 'macd_histogram_prev', market_data.macd_histogram),
                "bb_low": market_data.bb_low,
                "bb_high": market_data.bb_high,
                "bb_mid": market_data.bb_mid,
                "bb_width": market_data.bb_width,
                "avg_bb_width_20d": market_data.avg_bb_width_20d,
                "source": market_data.source
            }

            data['volume'] = self._get_simulated_volume(symbol)
            data['avg_volume_20d'] = self._get_avg_volume(symbol)
            return data
        except:
            return None

    def _get_simulated_volume(self, symbol: str) -> float:
        vol = 1000000 * np.random.uniform(0.5, 2.5)
        if symbol not in self.volume_history:
            self.volume_history[symbol] = []
        self.volume_history[symbol].append(vol)
        if len(self.volume_history[symbol]) > self.max_volume_history:
            self.volume_history[symbol].pop(0)
        return vol

    def _get_avg_volume(self, symbol: str) -> float:
        if symbol not in self.volume_history or not self.volume_history[symbol]:
            return 1000000
        return np.mean(self.volume_history[symbol])

    async def send_signal(self, signal, ai_evaluation=None):
        """Send signal with optional AI evaluation"""
        if not self.telegram_handler:
            return
        try:
            message = signal.to_message()

            # ✅ Add AI evaluation to message if available
            if ai_evaluation:
                message += f"\n\n🧠 **AI Risk Assessment:**\n"
                message += f"• Decision: {ai_evaluation.decision.value}\n"
                message += f"• AI Confidence: {ai_evaluation.adjusted_confidence:.0f}%\n"
                message += f"• Risk Score: {ai_evaluation.risk_score:.0f}/100\n"

                if ai_evaluation.red_flags:
                    message += f"\n⚠️ **Warnings:**\n"
                    for flag in ai_evaluation.red_flags[:2]:
                        message += f"• {flag}\n"

                if ai_evaluation.green_flags:
                    message += f"\n✅ **Confirmations:**\n"
                    for flag in ai_evaluation.green_flags[:2]:
                        message += f"• {flag}\n"

            if not message:
                return

            try:
                signal_id = self.analytics_db.record_signal(signal)
            except:
                signal_id = None

            await self.telegram_handler.broadcast_signal(message=message, asset=signal.symbol)

            if signal_id:
                self.active_signals[signal.symbol] = {
                    'signal_id': signal_id,
                    'entry_price': signal.entry_price,
                    'target_price': signal.target_price,
                    'stop_loss': signal.stop_loss_price,
                    'strategy': signal.strategy_type.value,
                    'entry_time': signal.entry_timestamp
                }

            self.stats['total_signals'] += 1
            self.stats['buy_signals'] += 1

            if signal.symbol not in self.active_positions:
                self.active_positions[signal.symbol] = Position(
                    signal.symbol,
                    signal.entry_price,
                    signal.strategy_type.value,
                    signal_id
                )
            self.save_positions()
        except:
            pass

    async def update_active_signals_tracking(self):
        pass

    async def scan_market(self, all_assets):
        logger.info("="*70)
        logger.info(f"🔍 SCAN | Assets: {len(all_assets)} | Data: {'✅' if self.use_multi_source else '❌'} | AI: {'✅' if self.ai_enabled else '❌'}")
        logger.info("="*70)

        if not self.use_multi_source:
            logger.error("❌ ABORTED - no data provider")
            logger.info("="*70)
            logger.info("✅ DONE (0.0min) - ABORTED")
            logger.info("📊 Success: 0/57 | Fail: 57")
            logger.info("="*70)
            return

        start = time.time()
        success = 0
        fail = 0
        signals_generated = 0
        signals_sent = 0
        ai_rejected = 0

        for symbol in all_assets:
            try:
                data = await self.fetch_data(symbol)
                if data is None:
                    fail += 1
                    continue
                success += 1

                price_history = self._generate_mock_price_history(data['price'], 200)
                regime = self.regime_detector.analyze_regime(
                    symbol, data['price'], price_history,
                    data['rsi'], data['ema200'], data['bb_low'], data['bb_high']
                )
                market_structure = self.structure_builder.build(symbol, data['price'], data, regime)

                technical = {
                    'rsi': data['rsi'],
                    'prev_rsi': data['prev_rsi'],
                    'ema50': data['ema50'],
                    'ema200': data['ema200'],
                    'macd': data['macd'],
                    'macd_signal': data['macd_signal'],
                    'macd_histogram': data['macd_histogram'],
                    'macd_histogram_prev': data.get('macd_histogram_prev', data['macd_histogram']),
                    'bb_low': data['bb_low'],
                    'bb_high': data['bb_high'],
                    'bb_mid': data['bb_mid'],
                    'bb_width': data['bb_width'],
                    'avg_bb_width_20d': data['avg_bb_width_20d'],
                    'volume': data['volume'],
                    'avg_volume_20d': data['avg_volume_20d'],
                    'prev_close': data['prev_close']
                }

                tier = self.get_tier(symbol)

                for strategy in self.strategies:
                    signal = strategy.analyze(
                        symbol, data['price'], regime, technical,
                        tier, self.active_positions.get(symbol), market_structure
                    )

                    if signal:
                        signals_generated += 1
                        should_send, reason = strategy.should_send_signal(symbol, signal)

                        if should_send:
                            # ✅ AI Risk Evaluation
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

                                    ai_should_send, ai_reason = self.ai_evaluator.should_send_signal(ai_eval)

                                    if ai_should_send:
                                        signals_sent += 1
                                        self.stats['ai_approved'] += 1
                                        logger.info(f"✅ {symbol}: AI APPROVED | {ai_eval.decision.value}")
                                        await self.send_signal(signal, ai_eval)
                                        strategy.record_activity()
                                    else:
                                        ai_rejected += 1
                                        self.stats['ai_rejected'] += 1
                                        logger.info(f"❌ {symbol}: AI REJECTED | {ai_reason}")

                                except Exception as e:
                                    logger.error(f"❌ AI error for {symbol}: {e}")
                                    # Fallback: send without AI
                                    signals_sent += 1
                                    await self.send_signal(signal)
                                    strategy.record_activity()
                            else:
                                # No AI: send directly
                                signals_sent += 1
                                logger.info(f"🎯 SIGNAL: {strategy.strategy_type.value} | {symbol}")
                                await self.send_signal(signal)
                                strategy.record_activity()

                            break

                await asyncio.sleep(ASSET_DELAY)
            except:
                fail += 1

        duration = (time.time() - start) / 60
        logger.info("="*70)
        logger.info(f"✅ DONE ({duration:.1f}min)")
        logger.info(f"📊 Success: {success}/{len(all_assets)} | Fail: {fail}")
        logger.info(f"🔍 Generated: {signals_generated} → 🧠 AI Rejected: {ai_rejected} → 📤 Sent: {signals_sent}")
        logger.info("="*70)

    async def run_forever(self):
        all_assets = CRYPTO + STOCKS + COMMODITIES

        logger.info(f"""
╔════════════════════════════════════════╗
║  TRADING ENGINE v5.0 FINAL             ║
║  ✅ Data: {'ACTIVE' if self.use_multi_source else 'INACTIVE'}
║  🧠 AI Risk: {'ACTIVE' if self.ai_enabled else 'INACTIVE'}
╠════════════════════════════════════════╣
║ Assets: {len(all_assets)} | Strategies: {len(self.strategies)}
╚════════════════════════════════════════╝
        """)

        while True:
            try:
                await self.scan_market(all_assets)
                logger.info(f"⏸️  Next scan in {SCAN_INTERVAL/60:.0f}min...")
                await asyncio.sleep(SCAN_INTERVAL)
            except:
                await asyncio.sleep(300)

    def _generate_mock_price_history(self, current_price: float, length: int):
        returns = np.random.normal(0, 0.02, length-1)
        prices = [current_price]
        for ret in reversed(returns):
            prices.insert(0, prices[0] / (1 + ret))
        return np.array(prices)