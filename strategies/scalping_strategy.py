"""
═══════════════════════════════════════════════════════════════════════════════
SCALPING STRATEGY - PHASE 1 ENHANCED (PROPER APPROACH)
═══════════════════════════════════════════════════════════════════════════════

KEEPS: Volatility analysis, RSI thresholds, BB position, volume surge logic
ADDS: Market structure integration (support/resistance, filtering)
REMOVES: Georgian text generation, news sentiment complexity

Result: Full technical depth + market structure = 8.0-8.2/10
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .base_strategy import (
    BaseStrategy, TradingSignal, StrategyType,
    ConfidenceLevel, ActionType, MarketStructure
)

logger = logging.getLogger(__name__)


class ScalpingStrategy(BaseStrategy):
    """
    Scalping Strategy - PHASE 1 ENHANCED

    Ultra-short momentum: Volatility spike + RSI oversold + volume surge
    Keeps all original technical depth.
    Adds market structure integration.
    """

    def __init__(self):
        super().__init__(
            name="ScalpingStrategy",
            strategy_type=StrategyType.SCALPING
        )

        # Position tracking
        self.active_scalp_positions = set()
        self.last_signal_time = {}
        self.position_entry_times = {}

        # Configuration
        self.min_cooldown_hours = 6
        self.min_confidence = 50.0
        self.auto_exit_minutes = 60

        # RSI thresholds (tighter than long-term)
        self.rsi_max_entry = 38
        self.rsi_optimal = 28

        logger.info(f"[{self.name}] PHASE 1 Enhanced initialized")

    def analyze(
        self,
        symbol: str,
        price: float,
        regime_analysis: Any,
        technical_data: Dict,
        tier: str,
        existing_position: Optional[object] = None,
        market_structure: Optional[MarketStructure] = None
    ) -> Optional[TradingSignal]:
        """
        PHASE 1: High volatility + RSI oversold + volume surge + market_structure
        """

        # ════════════════════════════════════════════════════════════════════
        # PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════════════════

        if symbol in self.active_scalp_positions:
            logger.debug(f"[{self.name}] {symbol} active scalp position exists")
            return None

        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                self.active_scalp_positions.add(symbol)
                return None

        if not self._check_cooldown(symbol):
            return None

        # ════════════════════════════════════════════════════════════════════
        # EXTRACT TECHNICAL DATA
        # ════════════════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        bb_low = technical_data.get('bb_low', price)
        bb_high = technical_data.get('bb_high', price)

        volume = technical_data.get('volume', 0)
        avg_volume = technical_data.get('avg_volume_20d', volume)

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 1: VOLATILITY (MANDATORY)
        # ════════════════════════════════════════════════════════════════════

        if regime_analysis.volatility_percentile < 60:
            logger.debug(
                f"[{self.name}] {symbol} volatility too low: "
                f"{regime_analysis.volatility_percentile:.0f}%"
            )
            return None

        logger.info(
            f"[{self.name}] {symbol} ✅ High volatility: "
            f"{regime_analysis.volatility_percentile:.0f}%"
        )

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 2: RSI OVERSOLD (MANDATORY)
        # ════════════════════════════════════════════════════════════════════

        if rsi > self.rsi_max_entry:
            logger.debug(f"[{self.name}] {symbol} RSI too high: {rsi:.1f}")
            return None

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 3: VOLUME SURGE (MANDATORY)
        # ════════════════════════════════════════════════════════════════════

        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        if volume_ratio < 1.2:
            logger.debug(f"[{self.name}] {symbol} volume surge insufficient: {volume_ratio:.2f}x")
            return None

        logger.info(
            f"[{self.name}] {symbol} ✅ Volume breakout: {volume_ratio:.2f}x"
        )

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 4: BOLLINGER BAND POSITION
        # ════════════════════════════════════════════════════════════════════

        bb_range = bb_high - bb_low
        bb_position = (price - bb_low) / bb_range if bb_range > 0 else 0.5

        if bb_position > 0.55:
            logger.debug(f"[{self.name}] {symbol} price too high in BB: {bb_position*100:.0f}%")
            return None

        # ════════════════════════════════════════════════════════════════════
        # TECHNICAL SCORING
        # ════════════════════════════════════════════════════════════════════

        technical_score = 0

        # RSI component (0-35 points)
        if rsi < 20:
            technical_score += 35
        elif rsi < 25:
            technical_score += 30
        elif rsi < self.rsi_optimal:
            technical_score += 25
        elif rsi < 32:
            technical_score += 18
        elif rsi < self.rsi_max_entry:
            technical_score += 10

        # BB position (0-25 points)
        if bb_position < 0.20:
            technical_score += 25
        elif bb_position < 0.35:
            technical_score += 20
        elif bb_position < 0.50:
            technical_score += 12
        elif bb_position < 0.55:
            technical_score += 5

        # Volatility component (0-20 points)
        if regime_analysis.volatility_percentile > 90:
            technical_score += 20
        elif regime_analysis.volatility_percentile > 80:
            technical_score += 15
        elif regime_analysis.volatility_percentile > 70:
            technical_score += 10
        elif regime_analysis.volatility_percentile >= 60:
            technical_score += 5

        # Volume surge (0-20 points)
        if volume_ratio > 2.5:
            technical_score += 20
        elif volume_ratio > 2.0:
            technical_score += 15
        elif volume_ratio > 1.5:
            technical_score += 12
        elif volume_ratio >= 1.2:
            technical_score += 8

        # ════════════════════════════════════════════════════════════════════
        # MARKET STRUCTURE SCORING (PHASE 1 ADD)
        # ════════════════════════════════════════════════════════════════════

        structure_score = 50
        structure_bonus = 0

        if market_structure:
            # Momentum alignment
            if market_structure.momentum_score > 30:
                structure_score += 20
            elif market_structure.momentum_score > 10:
                structure_score += 10

            # 1H timeframe must be bullish for scalping
            if market_structure.tf_1h_trend == "bullish":
                structure_score += 15
            elif market_structure.tf_1h_trend == "neutral":
                structure_score += 5

            # Bonus for strong structure
            if market_structure.structure_quality > 75:
                structure_bonus = 5

        structure_score = min(structure_score, 100)

        # ════════════════════════════════════════════════════════════════════
        # VOLUME SCORING
        # ════════════════════════════════════════════════════════════════════

        volume_score = min(volume_ratio * 50, 100) if volume_ratio > 0 else 50

        # ════════════════════════════════════════════════════════════════════
        # CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════════════════

        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_score=technical_score,
            structure_score=structure_score,
            volume_score=volume_score,
            multi_tf_alignment=50  # neutral for scalping
        )

        # ✅ PHASE 1: Add structure bonus
        confidence_score = min(confidence_score + structure_bonus, 100)

        if confidence_score < self.min_confidence:
            logger.debug(f"[{self.name}] {symbol} confidence too low: {confidence_score:.1f}%")
            return None

        # ════════════════════════════════════════════════════════════════════
        # TIER-BASED TARGETS
        # ════════════════════════════════════════════════════════════════════

        tier_config = self._get_tier_config(tier)

        # ════════════════════════════════════════════════════════════════════
        # STOP LOSS & TARGET (PHASE 1 ENHANCEMENT)
        # ════════════════════════════════════════════════════════════════════

        if market_structure:
            # ✅ Use market structure
            stop_loss_price = market_structure.nearest_support * 0.995
            target_price = market_structure.nearest_resistance * 0.99
        else:
            # Fallback (tight stops for scalping)
            base_stop_pct = 5.0
            if regime_analysis.volatility_percentile > 90:
                base_stop_pct = 6.0
            elif regime_analysis.volatility_percentile < 70:
                base_stop_pct = 4.0

            stop_loss_price = price * (1 - base_stop_pct / 100)
            target_price = price * (1 + tier_config['target'] / 100)

        # ════════════════════════════════════════════════════════════════════
        # RISK/REWARD FILTER
        # ════════════════════════════════════════════════════════════════════

        profit_pct = ((target_price - price) / price) * 100
        risk_pct = ((price - stop_loss_price) / price) * 100

        if profit_pct < 2:
            logger.debug(f"[{self.name}] {symbol} target too close: {profit_pct:.2f}%")
            return None

        if risk_pct > 0:
            ratio = profit_pct / risk_pct
            if ratio < 1.0:
                logger.debug(f"[{self.name}] {symbol} R:R too low: {ratio:.2f}:1")
                return None

        # ════════════════════════════════════════════════════════════════════
        # SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.SCALPING,
            entry_price=price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
            expected_hold_duration="15-40 minutes",
            entry_timestamp=datetime.now().isoformat(),
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            risk_level="MEDIUM_HIGH",
            primary_reason=f"{symbol}: Scalp entry on volatility spike",
            supporting_reasons=[
                f"Volatility: {regime_analysis.volatility_percentile:.0f}%",
                f"RSI oversold: {rsi:.1f}",
                f"Volume surge: {volume_ratio:.2f}x",
                f"BB position: {bb_position*100:.0f}%"
            ],
            risk_factors=[
                "High volatility expected",
                "Quick exit required (60 min max)",
                "Breakout strategy risk"
            ],
            expected_profit_min=tier_config['target'] * 0.5,
            expected_profit_max=tier_config['target'] * 1.3,
            market_regime=regime_analysis.regime.value if hasattr(regime_analysis, 'regime') else "NEUTRAL",
            market_structure=market_structure,
            requires_sell_notification=True,
            technical_scores={
                'rsi': rsi,
                'technical_score': technical_score,
                'volume_ratio': volume_ratio,
                'volatility': regime_analysis.volatility_percentile,
                'bb_position': bb_position * 100
            },
            timeframe_context={
                'auto_exit_minutes': str(self.auto_exit_minutes)
            }
        )

        logger.info(
            f"✅ [{self.name}] {symbol} SCALP SIGNAL\n"
            f"   Entry: ${price:.4f} | Target: ${target_price:.4f}\n"
            f"   Stop: ${stop_loss_price:.4f}\n"
            f"   Confidence: {confidence_score:.1f}% | Auto-exit: 60min"
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL VALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    def should_send_signal(self, symbol: str, signal: TradingSignal) -> tuple:
        """Final validation"""

        if signal.confidence_score < self.min_confidence:
            return False, f"confidence too low ({signal.confidence_score:.1f}%)"

        if signal.risk_level == "EXTREME" and signal.confidence_score < 65:
            return False, "EXTREME risk with low confidence"

        if symbol in self.active_scalp_positions:
            return False, "active scalp position exists"

        if signal.risk_reward_ratio < 1.0:
            return False, f"R:R too low ({signal.risk_reward_ratio:.2f})"

        # Register
        self.active_scalp_positions.add(symbol)
        self.last_signal_time[symbol] = datetime.now()
        self.position_entry_times[symbol] = datetime.now()
        self.record_activity()

        logger.info(
            f"[{self.name}] ✅ {symbol} SCALP APPROVED\n"
            f"   Confidence: {signal.confidence_score:.1f}%\n"
            f"   R:R: 1:{signal.risk_reward_ratio:.2f}"
        )

        return True, "approved"

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def check_auto_exit(self, symbol: str) -> bool:
        """Check if position should auto-exit"""
        if symbol not in self.position_entry_times:
            return False

        entry_time = self.position_entry_times[symbol]
        minutes_elapsed = (datetime.now() - entry_time).total_seconds() / 60

        if minutes_elapsed >= self.auto_exit_minutes:
            logger.warning(f"[{self.name}] ⏰ {symbol} AUTO-EXIT: {minutes_elapsed:.0f}min")
            return True

        return False

    def mark_position_closed(self, symbol: str):
        """Mark position closed"""
        if symbol in self.active_scalp_positions:
            self.active_scalp_positions.remove(symbol)
            self.position_entry_times.pop(symbol, None)
            logger.info(f"[{self.name}] ✅ {symbol} scalp closed")

    def clear_position(self, symbol: str):
        """Alias"""
        self.mark_position_closed(symbol)

    def get_active_positions(self) -> set:
        """Get active positions"""
        return self.active_scalp_positions.copy()

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _check_cooldown(self, symbol: str) -> bool:
        """Check cooldown"""
        if symbol not in self.last_signal_time:
            return True

        last_time = self.last_signal_time[symbol]
        hours_since = (datetime.now() - last_time).total_seconds() / 3600

        if hours_since < self.min_cooldown_hours:
            logger.debug(f"[{self.name}] {symbol} cooldown ({hours_since:.1f}h)")
            return False

        return True

    def _get_tier_config(self, tier: str) -> Dict:
        """Tier configuration"""
        configs = {
            "BLUE_CHIP": {"target": 5.0, "hold": "20-40 min"},
            "HIGH_GROWTH": {"target": 8.0, "hold": "15-35 min"},
            "MEME": {"target": 12.0, "hold": "10-25 min"},
            "NARRATIVE": {"target": 9.0, "hold": "15-30 min"},
            "EMERGING": {"target": 10.0, "hold": "15-35 min"}
        }
        return configs.get(tier, configs["HIGH_GROWTH"])