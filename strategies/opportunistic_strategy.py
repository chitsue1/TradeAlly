"""
═══════════════════════════════════════════════════════════════════════════════
OPPORTUNISTIC STRATEGY - REFACTORED v2.0 - FIXED
═══════════════════════════════════════════════════════════════════════════════

✅ FIXED: __init__ accepts crypto_symbols parameter (backward compatible)
✅ All other functionality unchanged

STRATEGY NICHE: Multi-timeframe breakouts + Bollinger Band squeeze patterns

CORE PHILOSOPHY:
- Capture explosive moves after consolidation periods
- BB squeeze detection (low volatility → high volatility transition)
- RSI divergence patterns (hidden strength/weakness)
- Volume surge confirmation
- 1-7 day holding period
- High risk, high reward

KEY INDICATORS:
✅ PRIMARY: BB squeeze (20-period), RSI divergence, Volume breakout (>2x)
✅ SECONDARY: Multi-TF momentum shift (1H + 4H + 1D alignment)
✅ TERTIARY: Support/resistance breakout confirmation

CONFIDENCE THRESHOLD: 60% minimum
REASON: Higher risk requires higher conviction

AUTHOR: Trading System Architecture Team
LAST UPDATE: 2024-02-05 (Fixed __init__)
"""

import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
import numpy as np

from .base_strategy import (
    BaseStrategy, TradingSignal, StrategyType,
    ConfidenceLevel, ActionType, MarketStructure
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# BOLLINGER BAND SQUEEZE DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

class BBSqueezeDetector:
    """
    Detect Bollinger Band squeeze patterns

    Squeeze = period of low volatility before explosive move
    """

    @staticmethod
    def detect_squeeze(
        bb_width: float,
        avg_bb_width_20d: float,
        threshold: float = 0.7
    ) -> Tuple[bool, float]:
        """
        Detect BB squeeze

        Args:
            bb_width: Current BB width (high - low)
            avg_bb_width_20d: 20-day average BB width
            threshold: Squeeze threshold (default 0.7 = 70% of average)

        Returns:
            (is_squeeze: bool, squeeze_ratio: float)
        """
        if avg_bb_width_20d == 0:
            return False, 1.0

        squeeze_ratio = bb_width / avg_bb_width_20d
        is_squeeze = squeeze_ratio < threshold

        return is_squeeze, squeeze_ratio

    @staticmethod
    def squeeze_score(squeeze_ratio: float) -> int:
        """
        Score squeeze intensity (0-100)

        Lower ratio = tighter squeeze = higher score
        """
        if squeeze_ratio >= 0.7:
            return 0  # No squeeze
        elif squeeze_ratio >= 0.6:
            return 20
        elif squeeze_ratio >= 0.5:
            return 40
        elif squeeze_ratio >= 0.4:
            return 60
        elif squeeze_ratio >= 0.3:
            return 80
        else:
            return 100  # Extreme squeeze

# ═══════════════════════════════════════════════════════════════════════════
# RSI DIVERGENCE DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

class RSIDivergenceDetector:
    """
    Detect RSI divergence patterns

    Bullish divergence: Price lower low, RSI higher low
    """

    @staticmethod
    def detect_bullish_divergence(
        current_price: float,
        prev_low_price: float,
        current_rsi: float,
        prev_low_rsi: float
    ) -> Tuple[bool, int]:
        """
        Detect bullish divergence

        Returns:
            (has_divergence: bool, divergence_score: int)
        """
        # Price made lower low
        price_lower = current_price < prev_low_price

        # RSI made higher low
        rsi_higher = current_rsi > prev_low_rsi

        has_divergence = price_lower and rsi_higher

        if not has_divergence:
            return False, 0

        # Score strength
        price_drop = abs(current_price - prev_low_price) / prev_low_price
        rsi_rise = current_rsi - prev_low_rsi

        score = 0
        if price_drop > 0.05 and rsi_rise > 5:
            score = 40  # Strong divergence
        elif price_drop > 0.03 and rsi_rise > 3:
            score = 30
        elif price_drop > 0.01 and rsi_rise > 2:
            score = 20
        else:
            score = 10

        return True, score

# ═══════════════════════════════════════════════════════════════════════════
# OPPORTUNISTIC STRATEGY
# ═══════════════════════════════════════════════════════════════════════════

class OpportunisticStrategy(BaseStrategy):
    """
    Opportunistic Strategy - Breakout & Squeeze Expert

    ✅ REFACTORED: BB squeeze detection, RSI divergence, volume breakout logic
    ✅ FOCUS: Explosive moves from consolidation, multi-TF confirmation
    ✅ FIXED: Backward compatible __init__ with crypto_symbols parameter
    """

    def __init__(self, crypto_symbols: Optional[List[str]] = None):
        """
        Initialize Opportunistic Strategy

        Args:
            crypto_symbols: Optional list of crypto symbols (backward compatibility)
                           Not actively used in refactored version
        """
        super().__init__(
            name="OpportunisticStrategy",
            strategy_type=StrategyType.OPPORTUNISTIC
        )

        # Position tracking
        self.active_positions = set()
        self.last_signal_time = {}
        self.position_entry_prices = {}

        # Configuration
        self.min_cooldown_hours = 72  # 3 days
        self.min_confidence = 60.0

        # Detectors
        self.squeeze_detector = BBSqueezeDetector()
        self.divergence_detector = RSIDivergenceDetector()

        # RSI thresholds
        self.rsi_max = 45  # Don't buy if RSI > 45

        # ✅ Crypto symbols (for backward compatibility, not actively used)
        self.crypto_symbols = crypto_symbols or []

        logger.info(
            f"[{self.name}] Initialized - "
            f"BB squeeze + RSI divergence focus"
            f"{f' | Symbols: {len(self.crypto_symbols)}' if self.crypto_symbols else ''}"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # MAIN ANALYSIS METHOD
    # ═══════════════════════════════════════════════════════════════════════

    def analyze(
        self,
        symbol: str,
        price: float,
        regime_analysis: Any,
        technical_data: Dict,
        tier: str,
        existing_position: Optional[object] = None,
        market_structure: Optional[MarketStructure] = None,
        news_text: Optional[str] = None  # OPTIONAL
    ) -> Optional[TradingSignal]:
        """
        Opportunistic breakout analysis

        ENTRY CONDITIONS:
        1. [PREFERRED] BB squeeze OR RSI divergence
        2. [MANDATORY] Volume surge (>1.8x average)
        3. [MANDATORY] RSI < 45
        4. [PREFERRED] Multi-TF alignment improving
        5. [OPTIONAL] Positive news catalyst
        6. Confidence >= 60%
        """

        # ════════════════════════════════════════════════════════════════════
        # 1. PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════════════════

        if symbol in self.active_positions:
            logger.debug(
                f"[{self.name}] {symbol} active opportunistic position exists"
            )
            return None

        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                self.active_positions.add(symbol)
                return None

        if not self._check_cooldown(symbol):
            return None

        # ════════════════════════════════════════════════════════════════════
        # 2. NEWS SENTIMENT (OPTIONAL)
        # ════════════════════════════════════════════════════════════════════

        has_positive_news = False
        news_boost = 0

        if news_text:
            # Simple keyword check
            text_lower = news_text.lower()

            # Negative keywords → BLOCK
            bearish_keywords = [
                "hack", "exploit", "delisting", "lawsuit", "halt", "sec"
            ]
            if any(keyword in text_lower for keyword in bearish_keywords):
                logger.debug(
                    f"[{self.name}] {symbol} negative news detected - blocking"
                )
                return None

            # Positive keywords → BOOST
            bullish_keywords = [
                "partnership", "integration", "mainnet", "launch",
                "adoption", "listing", "burn"
            ]
            if any(keyword in text_lower for keyword in bullish_keywords):
                has_positive_news = True
                news_boost = 15  # Add 15% to confidence
                logger.info(
                    f"[{self.name}] {symbol} positive news catalyst detected"
                )

        # ════════════════════════════════════════════════════════════════════
        # 3. EXTRACT TECHNICAL DATA
        # ════════════════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        bb_low = technical_data.get('bb_low', price)
        bb_high = technical_data.get('bb_high', price)
        bb_mid = technical_data.get('bb_mid', price)

        bb_width = bb_high - bb_low
        avg_bb_width = technical_data.get('avg_bb_width_20d', bb_width)

        volume = technical_data.get('volume', 0)
        avg_volume = technical_data.get('avg_volume_20d', volume)

        # Historical data for divergence detection
        prev_low_price = technical_data.get('prev_low_price', price)
        prev_low_rsi = technical_data.get('prev_low_rsi', rsi)

        # ════════════════════════════════════════════════════════════════════
        # 4. CORE FILTER: RSI
        # ════════════════════════════════════════════════════════════════════

        if rsi > self.rsi_max:
            logger.debug(
                f"[{self.name}] {symbol} RSI too high: {rsi:.1f} "
                f"(max {self.rsi_max})"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 5. VOLUME BREAKOUT (MANDATORY)
        # ════════════════════════════════════════════════════════════════════

        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        if volume_ratio < 1.8:
            logger.debug(
                f"[{self.name}] {symbol} volume surge insufficient: "
                f"{volume_ratio:.2f}x (min 1.8x)"
            )
            return None

        logger.info(
            f"[{self.name}] {symbol} ✅ Volume breakout: {volume_ratio:.2f}x"
        )

        # ════════════════════════════════════════════════════════════════════
        # 6. BOLLINGER BAND SQUEEZE DETECTION
        # ════════════════════════════════════════════════════════════════════

        is_squeeze, squeeze_ratio = self.squeeze_detector.detect_squeeze(
            bb_width=bb_width,
            avg_bb_width_20d=avg_bb_width
        )

        squeeze_score = self.squeeze_detector.squeeze_score(squeeze_ratio)

        if is_squeeze:
            logger.info(
                f"[{self.name}] {symbol} ✅ BB SQUEEZE detected: "
                f"ratio={squeeze_ratio:.2f}, score={squeeze_score}"
            )

        # ════════════════════════════════════════════════════════════════════
        # 7. RSI DIVERGENCE DETECTION
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
            logger.info(
                f"[{self.name}] {symbol} ✅ RSI DIVERGENCE detected: "
                f"score={divergence_score}"
            )

        # ════════════════════════════════════════════════════════════════════
        # 8. PATTERN REQUIREMENT CHECK
        # ════════════════════════════════════════════════════════════════════

        # At least ONE pattern must be present (squeeze OR divergence)
        has_pattern = is_squeeze or has_divergence

        if not has_pattern:
            logger.debug(
                f"[{self.name}] {symbol} no breakout pattern detected "
                f"(no squeeze, no divergence)"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 9. MULTI-TIMEFRAME MOMENTUM
        # ════════════════════════════════════════════════════════════════════

        tf_score = 50  # default

        if market_structure:
            # Check 1H and 4H momentum
            tf_1h = market_structure.tf_1h_trend
            tf_4h = market_structure.tf_4h_trend

            # At minimum, 1H should not be bearish
            if tf_1h == "bearish":
                logger.debug(
                    f"[{self.name}] {symbol} 1H bearish - risky for breakout"
                )
                # Don't hard block, but reduce score
                tf_score = 30
            else:
                tf_score = market_structure.alignment_score

                # Bonus: Both 1H and 4H bullish
                if tf_1h == "bullish" and tf_4h == "bullish":
                    tf_score = min(tf_score + 20, 100)

        # ════════════════════════════════════════════════════════════════════
        # 10. TECHNICAL SCORING
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
        # 11. STRUCTURE SCORING
        # ════════════════════════════════════════════════════════════════════

        structure_score = 50  # default

        if market_structure:
            # Momentum score
            if market_structure.momentum_score > 30:
                structure_score += 25
            elif market_structure.momentum_score > 10:
                structure_score += 15
            elif market_structure.momentum_score > 0:
                structure_score += 5

            # Support/resistance proximity
            dist_to_support = (
                abs(price - market_structure.nearest_support) / price
                if market_structure.nearest_support < price else 1.0
            )

            if dist_to_support < 0.02:
                structure_score += 15  # Very close to support
            elif dist_to_support < 0.05:
                structure_score += 10

        structure_score = min(structure_score, 100)

        # ════════════════════════════════════════════════════════════════════
        # 12. CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════════════════

        volume_score = min(volume_ratio * 40, 100)

        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_score=technical_score,
            structure_score=structure_score,
            volume_score=volume_score,
            multi_tf_alignment=tf_score
        )

        # Apply news boost if present
        if has_positive_news:
            confidence_score = min(confidence_score + news_boost, 100)

            # Re-calculate level after boost
            if confidence_score >= 90:
                confidence_level = ConfidenceLevel.VERY_HIGH
            elif confidence_score >= 75:
                confidence_level = ConfidenceLevel.HIGH
            elif confidence_score >= 60:
                confidence_level = ConfidenceLevel.MEDIUM

        # ✅ THRESHOLD: 60%
        if confidence_score < self.min_confidence:
            logger.debug(
                f"[{self.name}] {symbol} confidence insufficient: "
                f"{confidence_score:.1f}% (min {self.min_confidence}%)"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 13. TIER-BASED TARGETS
        # ════════════════════════════════════════════════════════════════════

        tier_config = self._get_tier_config(tier)

        # ════════════════════════════════════════════════════════════════════
        # 14. STOP LOSS CALCULATION
        # ════════════════════════════════════════════════════════════════════

        # Base stop: -8% (slightly wider for breakout volatility)
        base_stop_pct = 8.0

        # Adjust for volatility
        if regime_analysis.volatility_percentile > 85:
            base_stop_pct = 10.0
        elif regime_analysis.volatility_percentile < 50:
            base_stop_pct = 6.5

        # If squeeze is very tight, use tighter stop
        if squeeze_score > 80:
            base_stop_pct = max(base_stop_pct - 1.0, 6.0)

        stop_loss_price = price * (1 - base_stop_pct / 100)

        # ════════════════════════════════════════════════════════════════════
        # 15. REASONING CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        primary_reason = self._build_primary_reason(
            symbol=symbol,
            is_squeeze=is_squeeze,
            squeeze_ratio=squeeze_ratio,
            has_divergence=has_divergence,
            volume_ratio=volume_ratio,
            rsi=rsi,
            has_news=has_positive_news
        )

        supporting_reasons = self._build_supporting_reasons(
            is_squeeze=is_squeeze,
            squeeze_score=squeeze_score,
            has_divergence=has_divergence,
            divergence_score=divergence_score,
            volume_ratio=volume_ratio,
            rsi=rsi,
            has_news=has_positive_news,
            market_structure=market_structure
        )

        risk_factors = self._build_risk_factors(
            regime_analysis=regime_analysis,
            is_squeeze=is_squeeze,
            has_divergence=has_divergence,
            has_news=has_positive_news
        )

        # ════════════════════════════════════════════════════════════════════
        # 16. RISK ASSESSMENT
        # ════════════════════════════════════════════════════════════════════

        volume_trend = (
            "increasing" if volume_ratio > 2.0 else
            "stable"
        )

        risk_level = self._assess_risk_level(
            volatility_percentile=regime_analysis.volatility_percentile,
            volume_trend=volume_trend,
            structure_quality=structure_score,
            warning_count=len(regime_analysis.warning_flags)
        )

        # Opportunistic is inherently high risk
        if risk_level == "LOW":
            risk_level = "MEDIUM"

        # ════════════════════════════════════════════════════════════════════
        # 17. SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.OPPORTUNISTIC,
            entry_price=price,
            target_price=price * (1 + tier_config['target'] / 100),
            stop_loss_price=stop_loss_price,
            expected_hold_duration=tier_config['hold'],
            entry_timestamp=datetime.now().isoformat(),
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            risk_level=risk_level,
            primary_reason=primary_reason,
            supporting_reasons=supporting_reasons,
            risk_factors=risk_factors,
            expected_profit_min=tier_config['target'] * 0.5,
            expected_profit_max=tier_config['target'] * 1.5,
            market_regime=regime_analysis.regime.value,
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
                'has_divergence': str(has_divergence),
                'has_news': str(has_positive_news)
            }
        )

        logger.info(
            f"✅ [{self.name}] {symbol} OPPORTUNISTIC SIGNAL\n"
            f"   Entry: ${price:.4f} | Target: ${signal.target_price:.4f}\n"
            f"   Stop: ${stop_loss_price:.4f}\n"
            f"   Confidence: {confidence_score:.1f}% | Risk: {risk_level}\n"
            f"   Patterns: Squeeze={is_squeeze}, Divergence={has_divergence}, "
            f"News={has_positive_news}\n"
            f"   Volume: {volume_ratio:.2f}x | RSI: {rsi:.1f}"
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL VALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    def should_send_signal(
        self,
        symbol: str,
        signal: TradingSignal
    ) -> tuple[bool, str]:
        """Final validation"""

        if signal.confidence_score < self.min_confidence:
            return False, f"confidence too low ({signal.confidence_score:.1f}%)"

        if signal.risk_level == "EXTREME" and signal.confidence_score < 75:
            return False, "EXTREME risk with insufficient confidence"

        if symbol in self.active_positions:
            return False, "active opportunistic position exists"

        if signal.risk_reward_ratio < 1.3:
            return False, f"R:R too low ({signal.risk_reward_ratio:.2f})"

        # Register
        self.active_positions.add(symbol)
        self.last_signal_time[symbol] = datetime.now()
        self.position_entry_prices[symbol] = signal.entry_price

        self.record_activity()

        logger.info(
            f"[{self.name}] ✅ {symbol} OPPORTUNISTIC approved\n"
            f"   Confidence: {signal.confidence_score:.1f}%\n"
            f"   R:R: 1:{signal.risk_reward_ratio:.2f}"
        )

        return True, "opportunistic conditions met"

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def mark_position_closed(self, symbol: str):
        """Close opportunistic position"""
        if symbol in self.active_positions:
            self.active_positions.remove(symbol)
            self.position_entry_prices.pop(symbol, None)
            logger.info(f"[{self.name}] ✅ {symbol} opportunistic closed")

    def clear_position(self, symbol: str):
        self.mark_position_closed(symbol)

    def get_active_positions(self) -> set:
        return self.active_positions.copy()

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _check_cooldown(self, symbol: str) -> bool:
        if symbol not in self.last_signal_time:
            return True

        hours_since = (
            (datetime.now() - self.last_signal_time[symbol]).total_seconds() / 3600
        )

        if hours_since < self.min_cooldown_hours:
            logger.debug(
                f"[{self.name}] {symbol} cooldown "
                f"({hours_since:.1f}h / {self.min_cooldown_hours}h)"
            )
            return False

        return True

    def _get_tier_config(self, tier: str) -> Dict:
        configs = {
            "BLUE_CHIP": {"target": 9.0, "hold": "3-6 დღე"},
            "HIGH_GROWTH": {"target": 16.0, "hold": "2-6 დღე"},
            "MEME": {"target": 28.0, "hold": "1-5 დღე"},
            "NARRATIVE": {"target": 19.0, "hold": "2-6 დღე"},
            "EMERGING": {"target": 22.0, "hold": "2-7 დღე"}
        }
        return configs.get(tier, configs["HIGH_GROWTH"])

    def _build_primary_reason(
        self,
        symbol: str,
        is_squeeze: bool,
        squeeze_ratio: float,
        has_divergence: bool,
        volume_ratio: float,
        rsi: float,
        has_news: bool
    ) -> str:

        reason = f"{symbol} "

        patterns = []
        if is_squeeze:
            patterns.append(f"BB squeeze (ratio: {squeeze_ratio:.2f})")
        if has_divergence:
            patterns.append("RSI bullish divergence")
        if has_news:
            patterns.append("positive news catalyst")

        if patterns:
            reason += f"breakout setup: {', '.join(patterns)}. "

        reason += f"Volume surge {volume_ratio:.1f}x average. "
        reason += f"RSI {rsi:.1f} (entry zone). "

        reason += "Explosive move potential 1-7 days."

        return reason

    def _build_supporting_reasons(
        self,
        is_squeeze: bool,
        squeeze_score: int,
        has_divergence: bool,
        divergence_score: int,
        volume_ratio: float,
        rsi: float,
        has_news: bool,
        market_structure: Optional[MarketStructure]
    ) -> List[str]:

        reasons = []

        if is_squeeze:
            reasons.append(
                f"🔥 BB squeeze detected (score: {squeeze_score})"
            )

        if has_divergence:
            reasons.append(
                f"📈 RSI divergence (score: {divergence_score})"
            )

        reasons.append(f"📊 Volume breakout: {volume_ratio:.2f}x")
        reasons.append(f"🔵 RSI entry zone: {rsi:.1f}")

        if has_news:
            reasons.append("📰 Positive news catalyst")

        if market_structure and market_structure.momentum_score > 20:
            reasons.append("⚡ Momentum turning positive")

        return reasons[:5]

    def _build_risk_factors(
        self,
        regime_analysis: Any,
        is_squeeze: bool,
        has_divergence: bool,
        has_news: bool
    ) -> List[str]:

        factors = []

        factors.append("⚠️ Breakout strategy - high volatility expected")

        if regime_analysis.volatility_percentile > 85:
            factors.append(
                f"⚠️ Already high volatility "
                f"({regime_analysis.volatility_percentile:.0f}%)"
            )

        if not is_squeeze and not has_divergence:
            factors.append("⚠️ No strong technical pattern - relying on volume")

        if has_news:
            factors.append("⚠️ News-driven - momentum can reverse quickly")

        for warning in regime_analysis.warning_flags[:2]:
            factors.append(f"⚠️ {warning}")

        return factors[:4]


# ═══════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY ALIAS
# ═══════════════════════════════════════════════════════════════════════════

# For engines importing HybridOpportunisticStrategy
HybridOpportunisticStrategy = OpportunisticStrategy