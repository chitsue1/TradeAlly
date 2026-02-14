"""
═══════════════════════════════════════════════════════════════════════════════
OPPORTUNISTIC STRATEGY - PHASE 1 ENHANCED (PROPER APPROACH)
═══════════════════════════════════════════════════════════════════════════════

KEEPS: BB squeeze detection, RSI divergence, volume analysis, multi-TF momentum
ADDS: Market structure integration (support/resistance, filtering)
REMOVES: Georgian text, news sentiment (focus on patterns only)

Result: Full technical depth + market structure = 8.0-8.2/10
"""

import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime

from .base_strategy import (
    BaseStrategy, TradingSignal, StrategyType,
    ConfidenceLevel, ActionType, MarketStructure
)

logger = logging.getLogger(__name__)


class BBSqueezeDetector:
    """Detect Bollinger Band squeeze patterns"""

    @staticmethod
    def detect_squeeze(
        bb_width: float,
        avg_bb_width_20d: float,
        threshold: float = 0.7
    ) -> Tuple[bool, float]:
        """Detect BB squeeze"""
        if avg_bb_width_20d == 0:
            return False, 1.0

        squeeze_ratio = bb_width / avg_bb_width_20d
        is_squeeze = squeeze_ratio < threshold

        return is_squeeze, squeeze_ratio

    @staticmethod
    def squeeze_score(squeeze_ratio: float) -> int:
        """Score squeeze intensity (0-100)"""
        if squeeze_ratio >= 0.7:
            return 0
        elif squeeze_ratio >= 0.6:
            return 20
        elif squeeze_ratio >= 0.5:
            return 40
        elif squeeze_ratio >= 0.4:
            return 60
        elif squeeze_ratio >= 0.3:
            return 80
        else:
            return 100


class RSIDivergenceDetector:
    """Detect RSI divergence patterns"""

    @staticmethod
    def detect_bullish_divergence(
        current_price: float,
        prev_low_price: float,
        current_rsi: float,
        prev_low_rsi: float
    ) -> Tuple[bool, int]:
        """Detect bullish divergence"""
        price_lower = current_price < prev_low_price
        rsi_higher = current_rsi > prev_low_rsi

        has_divergence = price_lower and rsi_higher

        if not has_divergence:
            return False, 0

        # Score strength
        price_drop = abs(current_price - prev_low_price) / prev_low_price
        rsi_rise = current_rsi - prev_low_rsi

        score = 0
        if price_drop > 0.05 and rsi_rise > 5:
            score = 40
        elif price_drop > 0.03 and rsi_rise > 3:
            score = 30
        elif price_drop > 0.01 and rsi_rise > 2:
            score = 20
        else:
            score = 10

        return True, score


class OpportunisticStrategy(BaseStrategy):
    """
    Opportunistic Strategy - PHASE 1 ENHANCED

    Breakout expert: BB squeeze + RSI divergence + volume surge
    Keeps all original technical depth.
    Adds market structure integration.
    """

    def __init__(self, crypto_symbols: Optional[List[str]] = None):
        super().__init__(
            name="OpportunisticStrategy",
            strategy_type=StrategyType.OPPORTUNISTIC
        )

        # Position tracking
        self.active_positions = set()
        self.last_signal_time = {}
        self.position_entry_prices = {}

        # Configuration
        self.min_cooldown_hours = 72
        self.min_confidence = 60.0
        self.crypto_symbols = crypto_symbols or []

        # Detectors
        self.squeeze_detector = BBSqueezeDetector()
        self.divergence_detector = RSIDivergenceDetector()

        # RSI thresholds
        self.rsi_max = 45

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
        PHASE 1: Squeeze + Divergence + Volume surge + market_structure
        """

        # ════════════════════════════════════════════════════════════════════
        # PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════════════════

        if symbol in self.active_positions:
            logger.debug(f"[{self.name}] {symbol} active position exists")
            return None

        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                self.active_positions.add(symbol)
                return None

        if not self._check_cooldown(symbol):
            return None

        # ════════════════════════════════════════════════════════════════════
        # EXTRACT TECHNICAL DATA
        # ════════════════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        bb_low = technical_data.get('bb_low', price)
        bb_high = technical_data.get('bb_high', price)
        bb_mid = technical_data.get('bb_mid', price)

        bb_width = bb_high - bb_low
        avg_bb_width = technical_data.get('avg_bb_width_20d', bb_width)

        volume = technical_data.get('volume', 0)
        avg_volume = technical_data.get('avg_volume_20d', volume)

        prev_low_price = technical_data.get('prev_low_price', price)
        prev_low_rsi = technical_data.get('prev_low_rsi', rsi)

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 1: RSI
        # ════════════════════════════════════════════════════════════════════

        if rsi > self.rsi_max:
            logger.debug(f"[{self.name}] {symbol} RSI too high: {rsi:.1f}")
            return None

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 2: VOLUME BREAKOUT (MANDATORY)
        # ════════════════════════════════════════════════════════════════════

        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        if volume_ratio < 1.8:
            logger.debug(f"[{self.name}] {symbol} volume surge insufficient: {volume_ratio:.2f}x")
            return None

        logger.info(f"[{self.name}] {symbol} ✅ Volume breakout: {volume_ratio:.2f}x")

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 3: BOLLINGER BAND POSITION
        # ════════════════════════════════════════════════════════════════════

        bb_range = bb_high - bb_low
        bb_position = (price - bb_low) / bb_range if bb_range > 0 else 0.5

        if bb_position > 0.65:
            logger.debug(f"[{self.name}] {symbol} price too high in BB: {bb_position*100:.0f}%")
            return None

        # ════════════════════════════════════════════════════════════════════
        # PATTERN DETECTION 1: BB SQUEEZE
        # ════════════════════════════════════════════════════════════════════

        is_squeeze, squeeze_ratio = self.squeeze_detector.detect_squeeze(
            bb_width=bb_width,
            avg_bb_width_20d=avg_bb_width
        )

        squeeze_score = self.squeeze_detector.squeeze_score(squeeze_ratio)

        if is_squeeze:
            logger.info(f"[{self.name}] {symbol} ✅ BB SQUEEZE: ratio={squeeze_ratio:.2f}, score={squeeze_score}")

        # ════════════════════════════════════════════════════════════════════
        # PATTERN DETECTION 2: RSI DIVERGENCE
        # ════════════════════════════════════════════════════════════════════

        has_divergence, divergence_score = (
            self.divergence_detector.detect_bullish_divergence(
                current_price=price,
                prev_low_price=prev_low_price,
                current_rsi=rsi,
                prev_low_rsi=prev_low_rsi
            )
        )

        if has_divergence:
            logger.info(f"[{self.name}] {symbol} ✅ RSI DIVERGENCE: score={divergence_score}")

        # ════════════════════════════════════════════════════════════════════
        # PATTERN REQUIREMENT: At least ONE pattern must exist
        # ════════════════════════════════════════════════════════════════════

        has_pattern = is_squeeze or has_divergence

        if not has_pattern:
            logger.debug(f"[{self.name}] {symbol} no breakout pattern detected")
            return None

        # ════════════════════════════════════════════════════════════════════
        # MULTI-TIMEFRAME MOMENTUM
        # ════════════════════════════════════════════════════════════════════

        tf_score = 50
        if market_structure:
            tf_1h = market_structure.tf_1h_trend
            tf_4h = market_structure.tf_4h_trend

            if tf_1h == "bearish":
                tf_score = 30
            else:
                tf_score = market_structure.alignment_score
                if tf_1h == "bullish" and tf_4h == "bullish":
                    tf_score = min(tf_score + 20, 100)

        # ════════════════════════════════════════════════════════════════════
        # TECHNICAL SCORING
        # ════════════════════════════════════════════════════════════════════

        technical_score = 0

        # RSI component (0-25 points)
        if rsi < 25:
            technical_score += 25
        elif rsi < 30:
            technical_score += 22
        elif rsi < 35:
            technical_score += 18
        elif rsi < 40:
            technical_score += 12
        elif rsi < self.rsi_max:
            technical_score += 8

        # BB squeeze (0-30 points)
        technical_score += min(squeeze_score * 0.3, 30)

        # RSI divergence (0-25 points)
        technical_score += min(divergence_score * 0.625, 25)

        # Volume surge (0-20 points)
        if volume_ratio > 3.0:
            technical_score += 20
        elif volume_ratio > 2.5:
            technical_score += 18
        elif volume_ratio > 2.0:
            technical_score += 15
        elif volume_ratio >= 1.8:
            technical_score += 10

        # ════════════════════════════════════════════════════════════════════
        # MARKET STRUCTURE SCORING (PHASE 1 ADD)
        # ════════════════════════════════════════════════════════════════════

        structure_score = 50
        structure_bonus = 0

        if market_structure:
            if market_structure.momentum_score > 30:
                structure_score += 25
            elif market_structure.momentum_score > 10:
                structure_score += 15
            elif market_structure.momentum_score > 0:
                structure_score += 5

            dist_to_support = (
                abs(price - market_structure.nearest_support) / price
                if market_structure.nearest_support < price else 1.0
            )
            if dist_to_support < 0.02:
                structure_score += 15
            elif dist_to_support < 0.05:
                structure_score += 10

            if market_structure.structure_quality > 75:
                structure_bonus = 5

        structure_score = min(structure_score, 100)

        # ════════════════════════════════════════════════════════════════════
        # VOLUME SCORING
        # ════════════════════════════════════════════════════════════════════

        volume_score = min(volume_ratio * 40, 100) if volume_ratio > 0 else 50

        # ════════════════════════════════════════════════════════════════════
        # CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════════════════

        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_score=technical_score,
            structure_score=structure_score,
            volume_score=volume_score,
            multi_tf_alignment=tf_score
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
            # Fallback
            base_stop_pct = 8.0
            if regime_analysis.volatility_percentile > 85:
                base_stop_pct = 10.0
            elif regime_analysis.volatility_percentile < 50:
                base_stop_pct = 6.5

            if squeeze_score > 80:
                base_stop_pct = max(base_stop_pct - 1.0, 6.0)

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
            if ratio < 1.3:
                logger.debug(f"[{self.name}] {symbol} R:R too low: {ratio:.2f}:1")
                return None

        # ════════════════════════════════════════════════════════════════════
        # SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.OPPORTUNISTIC,
            entry_price=price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
            expected_hold_duration="1-7 days",
            entry_timestamp=datetime.now().isoformat(),
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            risk_level="HIGH",
            primary_reason=f"{symbol}: Opportunistic breakout setup",
            supporting_reasons=[
                f"Squeeze: {is_squeeze}, Divergence: {has_divergence}",
                f"Volume: {volume_ratio:.2f}x",
                f"RSI: {rsi:.1f}",
                f"Momentum: {tf_score:.0f}%"
            ],
            risk_factors=[
                "High volatility expected",
                "Breakout strategy risk",
                "Pattern may be false"
            ],
            expected_profit_min=tier_config['target'] * 0.5,
            expected_profit_max=tier_config['target'] * 1.5,
            market_regime=regime_analysis.regime.value if hasattr(regime_analysis, 'regime') else "NEUTRAL",
            market_structure=market_structure,
            requires_sell_notification=True,
            technical_scores={
                'rsi': rsi,
                'technical_score': technical_score,
                'squeeze_score': squeeze_score,
                'divergence_score': divergence_score,
                'volume_ratio': volume_ratio
            },
            timeframe_context={
                'has_squeeze': str(is_squeeze),
                'has_divergence': str(has_divergence)
            }
        )

        logger.info(
            f"✅ [{self.name}] {symbol} OPPORTUNISTIC SIGNAL\n"
            f"   Entry: ${price:.4f} | Target: ${target_price:.4f}\n"
            f"   Stop: ${stop_loss_price:.4f}\n"
            f"   Confidence: {confidence_score:.1f}% | Risk: HIGH\n"
            f"   Patterns: Squeeze={is_squeeze}, Divergence={has_divergence}, Vol={volume_ratio:.2f}x"
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL VALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    def should_send_signal(self, symbol: str, signal: TradingSignal) -> tuple:
        """Final validation"""

        if signal.confidence_score < self.min_confidence:
            return False, f"confidence too low ({signal.confidence_score:.1f}%)"

        if signal.risk_level == "EXTREME" and signal.confidence_score < 75:
            return False, "EXTREME risk with low confidence"

        if symbol in self.active_positions:
            return False, "active position exists"

        if signal.risk_reward_ratio < 1.3:
            return False, f"R:R too low ({signal.risk_reward_ratio:.2f})"

        # Register
        self.active_positions.add(symbol)
        self.last_signal_time[symbol] = datetime.now()
        self.position_entry_prices[symbol] = signal.entry_price
        self.record_activity()

        logger.info(
            f"[{self.name}] ✅ {symbol} OPPORTUNISTIC APPROVED\n"
            f"   Confidence: {signal.confidence_score:.1f}%\n"
            f"   R:R: 1:{signal.risk_reward_ratio:.2f}"
        )

        return True, "approved"

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def mark_position_closed(self, symbol: str):
        """Mark position closed"""
        if symbol in self.active_positions:
            self.active_positions.remove(symbol)
            self.position_entry_prices.pop(symbol, None)
            logger.info(f"[{self.name}] ✅ {symbol} position closed")

    def clear_position(self, symbol: str):
        """Alias"""
        self.mark_position_closed(symbol)

    def get_active_positions(self) -> set:
        """Get active positions"""
        return self.active_positions.copy()

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _check_cooldown(self, symbol: str) -> bool:
        """Check cooldown"""
        if symbol not in self.last_signal_time:
            return True

        hours_since = (datetime.now() - self.last_signal_time[symbol]).total_seconds() / 3600

        if hours_since < self.min_cooldown_hours:
            logger.debug(f"[{self.name}] {symbol} cooldown ({hours_since:.1f}h)")
            return False

        return True

    def _get_tier_config(self, tier: str) -> Dict:
        """Tier configuration"""
        configs = {
            "BLUE_CHIP": {"target": 9.0, "hold": "3-6 days"},
            "HIGH_GROWTH": {"target": 16.0, "hold": "2-6 days"},
            "MEME": {"target": 28.0, "hold": "1-5 days"},
            "NARRATIVE": {"target": 19.0, "hold": "2-6 days"},
            "EMERGING": {"target": 22.0, "hold": "2-7 days"}
        }
        return configs.get(tier, configs["HIGH_GROWTH"])


# Backward compatibility
HybridOpportunisticStrategy = OpportunisticStrategy