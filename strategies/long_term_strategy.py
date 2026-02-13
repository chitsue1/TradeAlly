"""
═══════════════════════════════════════════════════════════════════════════════
LONG-TERM INVESTMENT STRATEGY - REFACTORED v2.0
═══════════════════════════════════════════════════════════════════════════════

STRATEGY NICHE: Structural trends + Deep value accumulation zones

CORE PHILOSOPHY:
- Buy structural uptrends at temporary pullbacks
- Focus on EMA200 as primary trend filter
- Deep oversold conditions (RSI < 35) preferred
- 1-3 week holding period
- Risk-reward minimum 1:2

KEY INDICATORS:
✅ PRIMARY: EMA200 (trend filter), RSI (entry timing)
✅ SECONDARY: Bollinger Bands (pullback depth), Volume (confirmation)
✅ TERTIARY: Multi-timeframe alignment (4H + 1D)

CONFIDENCE THRESHOLD: 55% minimum (was 60%)
REASON: More opportunities in ranging markets, still selective

DIFFERENTIATION FROM OTHER STRATEGIES:
- vs Swing: Longer holds, deeper pullbacks required
- vs Scalping: Structural focus, ignores short-term noise
- vs Opportunistic: No news dependency, pure technical

AUTHOR: Trading System Architecture Team
LAST UPDATE: 2024-02-05
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

from .base_strategy import (
    BaseStrategy, TradingSignal, StrategyType,
    ConfidenceLevel, ActionType, MarketStructure
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# LONG-TERM STRATEGY
# ═══════════════════════════════════════════════════════════════════════════

class LongTermStrategy(BaseStrategy):
    """
    გრძელვადიანი ინვესტიციის სტრატეგია

    ✅ REFACTORED: Lower threshold (55%), better market structure awareness
    ✅ FOCUS: EMA200 trend + deep RSI pullbacks
    """

    def __init__(self):
        super().__init__(
            name="LongTermInvestment",
            strategy_type=StrategyType.LONG_TERM
        )

        # Position tracking
        self.active_long_positions = set()
        self.last_buy_signal = {}
        self.position_entry_prices = {}

        # Configuration
        self.min_cooldown_hours = 48  # 2 days between signals per symbol
        self.min_confidence = 55.0  # Lowered from 60%

        # RSI thresholds
        self.rsi_max_entry = 40  # Can enter up to RSI 40
        self.rsi_optimal = 30    # Optimal entry below 30
        self.rsi_extreme = 20    # Extreme oversold

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
        market_structure: Optional[MarketStructure] = None
    ) -> Optional[TradingSignal]:
        """
        Long-term opportunity analysis

        ENTRY CONDITIONS:
        1. EMA200 > price OR price within 3% of EMA200 (structural support)
        2. RSI < 40 (pullback)
        3. Bollinger Bands: price in lower 60% of range
        4. Volume: not declining trend
        5. Confidence >= 55%
        """

        # ════════════════════════════════════════════════════════════════════
        # 1. PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════════════════

        if symbol in self.active_long_positions:
            logger.debug(
                f"[{self.name}] {symbol} active position exists - waiting for SELL"
            )
            return None

        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                self.active_long_positions.add(symbol)
                logger.debug(f"[{self.name}] {symbol} existing position detected")
                return None

        if not self._check_minimum_cooldown(symbol):
            return None

        # ════════════════════════════════════════════════════════════════════
        # 2. EXTRACT TECHNICAL DATA
        # ════════════════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        ema200 = technical_data.get('ema200', price)
        ema50 = technical_data.get('ema50', price)
        bb_low = technical_data.get('bb_low', price)
        bb_high = technical_data.get('bb_high', price)
        bb_mid = technical_data.get('bb_mid', price)

        volume = technical_data.get('volume', 0)
        avg_volume = technical_data.get('avg_volume_20d', volume)

        # ════════════════════════════════════════════════════════════════════
        # 3. CORE FILTERS + PULLBACK BOTTOM DETECTION
        # ════════════════════════════════════════════════════════════════════

        # Filter 1: RSI must show pullback
        if rsi > self.rsi_max_entry:
            logger.debug(
                f"[{self.name}] {symbol} RSI too high: {rsi:.1f} "
                f"(max {self.rsi_max_entry})"
            )
            return None

        # ✅ NEW: Wait for pullback BOTTOM (not still falling!)
        # Get previous RSI and price to detect momentum shift
        prev_rsi = technical_data.get('prev_rsi', rsi)
        prev_close = technical_data.get('prev_close', price)

        price_change_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
        rsi_change = rsi - prev_rsi

        # Check if still in free-fall
        if rsi < 35 and price_change_pct < -2.0 and rsi_change < -2:
            logger.debug(
                f"[{self.name}] {symbol} STILL FALLING - waiting for bottom:\n"
                f"   Price: {price_change_pct:.1f}% (dropping)\n"
                f"   RSI: {prev_rsi:.1f}→{rsi:.1f} (falling {rsi_change:.1f})\n"
                f"   ⏳ Wait for stabilization before entry"
            )
            return None

        # Ideal: RSI starting to rise (divergence or bottom found)
        if rsi_change > 0:
            logger.info(
                f"[{self.name}] {symbol} ✅ RSI bottoming signal: "
                f"{prev_rsi:.1f}→{rsi:.1f} (+{rsi_change:.1f}) - pullback likely ending"
            )
        else:
            logger.info(
                f"[{self.name}] {symbol} ✅ Deep oversold: RSI {rsi:.1f} "
                f"(change: {rsi_change:.1f})"
            )

        # Filter 2: EMA200 trend analysis
        distance_from_ema200 = (price - ema200) / ema200

        # Allow entry if:
        # - Price above EMA200 (uptrend), OR
        # - Price within -5% to +3% of EMA200 (consolidation/support)
        if distance_from_ema200 < -0.05:
            logger.debug(
                f"[{self.name}] {symbol} too far below EMA200: "
                f"{distance_from_ema200*100:.1f}% (min -5%)"
            )
            return None

        # Filter 3: Bollinger Band position (pullback depth check)
        bb_range = bb_high - bb_low
        bb_position = (
            (price - bb_low) / bb_range if bb_range > 0 else 0.5
        )

        # Price should be in lower 60% of BB range for long-term entry
        if bb_position > 0.65:
            logger.debug(
                f"[{self.name}] {symbol} price too high in BB range: "
                f"{bb_position*100:.0f}% (max 65%)"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 4. VOLUME ANALYSIS
        # ════════════════════════════════════════════════════════════════════

        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        # Volume trend scoring
        volume_score = 50  # default

        if volume_ratio > 1.5:
            volume_score = 80  # Strong volume surge (good for entry)
        elif volume_ratio > 1.0:
            volume_score = 70  # Above average
        elif volume_ratio > 0.7:
            volume_score = 50  # Normal
        else:
            volume_score = 30  # Low volume (risky)

        # ════════════════════════════════════════════════════════════════════
        # 5. MARKET STRUCTURE SCORING
        # ════════════════════════════════════════════════════════════════════

        structure_score = 50  # default

        if market_structure:
            # Check if price near support
            dist_to_support = (
                abs(price - market_structure.nearest_support) / price
            )

            if dist_to_support < 0.02:  # Within 2% of support
                structure_score += 30
            elif dist_to_support < 0.05:  # Within 5%
                structure_score += 15

            # Bonus for strong support
            if market_structure.support_strength > 70:
                structure_score += 10

            # Multi-timeframe alignment bonus
            if market_structure.alignment_score > 60:
                structure_score += 10

        structure_score = min(structure_score, 100)

        # ════════════════════════════════════════════════════════════════════
        # 6. TECHNICAL SCORING
        # ════════════════════════════════════════════════════════════════════

        technical_score = 0

        # RSI component (0-40 points)
        if rsi < self.rsi_extreme:  # < 20
            technical_score += 40
        elif rsi < 25:
            technical_score += 35
        elif rsi < self.rsi_optimal:  # < 30
            technical_score += 30
        elif rsi < 35:
            technical_score += 20
        elif rsi < self.rsi_max_entry:  # < 40
            technical_score += 10

        # EMA200 positioning (0-30 points)
        if distance_from_ema200 > 0.03:  # More than 3% above
            technical_score += 30
        elif distance_from_ema200 > 0:  # Above EMA200
            technical_score += 25
        elif distance_from_ema200 > -0.02:  # Just below (support zone)
            technical_score += 20
        elif distance_from_ema200 > -0.05:  # Up to -5%
            technical_score += 10

        # Bollinger Band depth (0-30 points)
        if bb_position < 0.20:  # Deep in lower BB
            technical_score += 30
        elif bb_position < 0.35:
            technical_score += 25
        elif bb_position < 0.50:
            technical_score += 20
        elif bb_position < 0.65:
            technical_score += 10

        # ════════════════════════════════════════════════════════════════════
        # 7. MULTI-TIMEFRAME ALIGNMENT
        # ════════════════════════════════════════════════════════════════════

        tf_alignment = 50  # default

        if market_structure:
            tf_alignment = market_structure.alignment_score

        # ════════════════════════════════════════════════════════════════════
        # 8. CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════════════════

        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_score=technical_score,
            structure_score=structure_score,
            volume_score=volume_score,
            multi_tf_alignment=tf_alignment
        )

        # ✅ THRESHOLD: 55% (lowered from 60%)
        if confidence_score < self.min_confidence:
            logger.debug(
                f"[{self.name}] {symbol} confidence insufficient: "
                f"{confidence_score:.1f}% (min {self.min_confidence}%)"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 9. TIER-BASED TARGETS
        # ════════════════════════════════════════════════════════════════════

        tier_config = self._get_tier_config(tier)

        # ════════════════════════════════════════════════════════════════════
        # 10. STOP LOSS CALCULATION
        # ════════════════════════════════════════════════════════════════════

        # Dynamic stop loss based on:
        # - Bollinger Band width (volatility)
        # - Distance to nearest support

        base_stop_pct = 8.0  # Default -8%

        # Adjust for volatility
        if regime_analysis.volatility_percentile > 80:
            base_stop_pct = 10.0  # Wider stop in high volatility
        elif regime_analysis.volatility_percentile < 40:
            base_stop_pct = 6.0   # Tighter stop in low volatility

        # Adjust for support proximity
        if market_structure and market_structure.nearest_support < price:
            support_distance = abs(price - market_structure.nearest_support) / price

            # If support is close (< 5%), use it as stop reference
            if support_distance < 0.05:
                stop_below_support = market_structure.nearest_support * 0.98
                stop_loss_price = min(
                    stop_below_support,
                    price * (1 - base_stop_pct / 100)
                )
            else:
                stop_loss_price = price * (1 - base_stop_pct / 100)
        else:
            stop_loss_price = price * (1 - base_stop_pct / 100)

        # ════════════════════════════════════════════════════════════════════
        # 11. REASONING CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        primary_reason = self._build_primary_reason(
            symbol=symbol,
            regime_analysis=regime_analysis,
            tier=tier,
            rsi=rsi,
            distance_from_ema200=distance_from_ema200,
            bb_position=bb_position
        )

        supporting_reasons = self._build_supporting_reasons(
            regime_analysis=regime_analysis,
            rsi=rsi,
            distance_from_ema200=distance_from_ema200,
            bb_position=bb_position,
            volume_ratio=volume_ratio,
            market_structure=market_structure
        )

        risk_factors = self._build_risk_factors(
            regime_analysis=regime_analysis,
            volume_ratio=volume_ratio,
            structure_score=structure_score
        )

        # ════════════════════════════════════════════════════════════════════
        # 12. RISK ASSESSMENT
        # ════════════════════════════════════════════════════════════════════

        volume_trend = "stable"
        if volume_ratio > 1.2:
            volume_trend = "increasing"
        elif volume_ratio < 0.8:
            volume_trend = "decreasing"

        risk_level = self._assess_risk_level(
            volatility_percentile=regime_analysis.volatility_percentile,
            volume_trend=volume_trend,
            structure_quality=structure_score,
            warning_count=len(regime_analysis.warning_flags)
        )

        # ════════════════════════════════════════════════════════════════════
        # 13. SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.LONG_TERM,
            entry_price=price,
            target_price=price * (1 + tier_config['target_percent'] / 100),
            stop_loss_price=stop_loss_price,
            expected_hold_duration=tier_config['hold_duration'],
            entry_timestamp=datetime.now().isoformat(),
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            risk_level=risk_level,
            primary_reason=primary_reason,
            supporting_reasons=supporting_reasons,
            risk_factors=risk_factors,
            expected_profit_min=tier_config['target_percent'] * 0.6,
            expected_profit_max=tier_config['target_percent'] * 1.2,
            market_regime=regime_analysis.regime.value,
            market_structure=market_structure,
            requires_sell_notification=True,
            technical_scores={
                'rsi': rsi,
                'technical_score': technical_score,
                'structure_score': structure_score,
                'volume_score': volume_score,
                'tf_alignment': tf_alignment
            }
        )

        logger.info(
            f"✅ [{self.name}] {symbol} SIGNAL GENERATED\n"
            f"   Entry: ${price:.4f} | Target: ${signal.target_price:.4f}\n"
            f"   Confidence: {confidence_score:.1f}% | Risk: {risk_level}\n"
            f"   RSI: {rsi:.1f} | EMA200 dist: {distance_from_ema200*100:+.1f}%"
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
        """
        Final validation before sending
        """

        # Confidence check
        if signal.confidence_score < self.min_confidence:
            return False, f"confidence too low ({signal.confidence_score:.1f}%)"

        # Risk check
        if signal.risk_level == "EXTREME" and signal.confidence_score < 70:
            return False, "EXTREME risk with insufficient confidence"

        # Position check
        if symbol in self.active_long_positions:
            return False, "active position already exists"

        # Risk:Reward check
        if signal.risk_reward_ratio < 1.5:
            return False, f"R:R too low ({signal.risk_reward_ratio:.2f})"

        # Register position
        self.active_long_positions.add(symbol)
        self.last_buy_signal[symbol] = datetime.now()
        self.position_entry_prices[symbol] = signal.entry_price

        self.record_activity()

        logger.info(
            f"[{self.name}] ✅ {symbol} approved for Telegram\n"
            f"   Confidence: {signal.confidence_score:.1f}%\n"
            f"   R:R: 1:{signal.risk_reward_ratio:.2f}"
        )

        return True, "all conditions met"

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def mark_position_closed(self, symbol: str):
        """Mark position as closed - allow new signals"""
        if symbol in self.active_long_positions:
            self.active_long_positions.remove(symbol)
            self.position_entry_prices.pop(symbol, None)

            logger.info(
                f"[{self.name}] ✅ {symbol} position closed - "
                f"new signals allowed after cooldown"
            )

    def clear_position(self, symbol: str):
        """Alias for mark_position_closed"""
        self.mark_position_closed(symbol)

    def get_active_positions(self) -> set:
        """Get active long positions"""
        return self.active_long_positions.copy()

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _check_minimum_cooldown(self, symbol: str) -> bool:
        """Check per-symbol cooldown"""
        if symbol not in self.last_buy_signal:
            return True

        last_time = self.last_buy_signal[symbol]
        hours_since = (datetime.now() - last_time).total_seconds() / 3600

        if hours_since < self.min_cooldown_hours:
            logger.debug(
                f"[{self.name}] {symbol} cooldown active "
                f"({hours_since:.1f}h / {self.min_cooldown_hours}h)"
            )
            return False

        return True

    def _get_tier_config(self, tier: str) -> Dict:
        """Tier-specific configuration"""
        configs = {
            "BLUE_CHIP": {
                "target_percent": 12.0,
                "hold_duration": "2-3 კვირა"
            },
            "HIGH_GROWTH": {
                "target_percent": 18.0,
                "hold_duration": "1-3 კვირა"
            },
            "MEME": {
                "target_percent": 30.0,
                "hold_duration": "1-2 კვირა"
            },
            "NARRATIVE": {
                "target_percent": 22.0,
                "hold_duration": "1-3 კვირა"
            },
            "EMERGING": {
                "target_percent": 25.0,
                "hold_duration": "2-3 კვირა"
            }
        }
        return configs.get(tier, configs["HIGH_GROWTH"])

    def _build_primary_reason(
        self,
        symbol: str,
        regime_analysis: Any,
        tier: str,
        rsi: float,
        distance_from_ema200: float,
        bb_position: float
    ) -> str:
        """Build primary reasoning string"""

        reason = f"{symbol} "

        # Trend description
        if regime_analysis.is_structural:
            reason += "სტრუქტურულ აღმავალ ტრენდში მდებარეობს"
        else:
            reason += "აღმავალი პოტენციალის მქონე ზონაშია"

        # Current state
        if rsi < 25:
            reason += " და ძლიერად გადაყიდულია"
        elif rsi < 35:
            reason += " და oversold ზონაშია"
        else:
            reason += " და pullback ფაზაშია"

        reason += ". "

        # EMA200 context
        if distance_from_ema200 > 0.03:
            reason += "ფასი EMA200-ზე მაღლა მოძრაობს (ძლიერი აღმავალი), "
        elif distance_from_ema200 > 0:
            reason += "ფასი EMA200-ზე მაღლა არის (uptrend), "
        else:
            reason += "ფასი EMA200-ის support ზონაშია, "

        # BB context
        if bb_position < 0.30:
            reason += "ბოლინჯერის ქვედა ზონაში (კარგი entry)."
        else:
            reason += "ბოლინჯერის შუა-ქვედა ნაწილში."

        # Tier note
        tier_notes = {
            "BLUE_CHIP": " (Blue Chip - სტაბილური)",
            "HIGH_GROWTH": " (High Growth - მაღალი პოტენციალი)",
            "MEME": " (Meme - მაღალი ვოლატილობა)",
            "NARRATIVE": " (Narrative - ტრენდზე მყოფი)",
            "EMERGING": " (Emerging - ახალი ზრდის ფაზა)"
        }
        reason += tier_notes.get(tier, "")

        return reason

    def _build_supporting_reasons(
        self,
        regime_analysis: Any,
        rsi: float,
        distance_from_ema200: float,
        bb_position: float,
        volume_ratio: float,
        market_structure: Optional[MarketStructure]
    ) -> List[str]:
        """Build supporting reasons list"""

        reasons = []

        # Regime
        if regime_analysis.is_structural:
            reasons.append("📈 სტრუქტურული აღმავალი ტრენდი დადასტურებულია")

        # RSI
        if rsi < 25:
            reasons.append(f"🔵 ძლიერი oversold (RSI: {rsi:.1f})")
        elif rsi < 35:
            reasons.append(f"🔵 Oversold ზონა (RSI: {rsi:.1f})")
        else:
            reasons.append(f"📊 RSI pullback (RSI: {rsi:.1f})")

        # EMA200
        if distance_from_ema200 > 0:
            reasons.append(
                f"✅ ფასი EMA200-ზე მაღლა ({distance_from_ema200*100:+.1f}%)"
            )
        else:
            reasons.append(
                f"⚖️ EMA200 support ზონა ({distance_from_ema200*100:+.1f}%)"
            )

        # Bollinger
        if bb_position < 0.30:
            reasons.append(f"📉 ბოლინჯერის ქვედა ზონა (ღრმა pullback)")

        # Volume
        if volume_ratio > 1.2:
            reasons.append(f"📊 მოცულობა გაზრდილია ({volume_ratio:.1f}x)")

        # Market structure
        if market_structure:
            if market_structure.alignment_score > 60:
                reasons.append("🎯 Multi-timeframe alignment დადებითი")

            dist_to_support = abs(
                (market_structure.nearest_support / 
                 (market_structure.nearest_support + 1)) - 1
            )
            if dist_to_support < 0.03:
                reasons.append("🛡️ Support level ახლოსაა")

        return reasons[:5]  # Top 5

    def _build_risk_factors(
        self,
        regime_analysis: Any,
        volume_ratio: float,
        structure_score: float
    ) -> List[str]:
        """Build risk factors list"""

        factors = []

        # Volatility
        if regime_analysis.volatility_percentile > 85:
            factors.append(
                f"⚠️ ძალიან მაღალი ვოლატილობა "
                f"({regime_analysis.volatility_percentile:.0f}%)"
            )
        elif regime_analysis.volatility_percentile > 70:
            factors.append(
                f"⚠️ გაზრდილი ვოლატილობა "
                f"({regime_analysis.volatility_percentile:.0f}%)"
            )

        # Volume
        if volume_ratio < 0.7:
            factors.append("⚠️ დაბალი ვაჭრობის მოცულობა")

        # Structure
        if structure_score < 40:
            factors.append("⚠️ სუსტი market structure")

        # Warnings from regime
        for warning in regime_analysis.warning_flags[:2]:
            factors.append(f"⚠️ {warning}")

        # Default if no risks
        if not factors:
            factors.append("✅ რისკი კონტროლირებადია")

        return factors[:4]  # Max 4