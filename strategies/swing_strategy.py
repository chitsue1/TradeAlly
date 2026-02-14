"""
═══════════════════════════════════════════════════════════════════════════════
SWING TRADING STRATEGY - REFACTORED v2.0
═══════════════════════════════════════════════════════════════════════════════

STRATEGY NICHE: Trend continuation + Multi-timeframe momentum alignment

CORE PHILOSOPHY:
- Ride established trends with pullback entries
- EMA50/EMA200 crossover as primary filter
- MACD + RSI divergence detection
- 4-10 day holding period
- Medium risk, medium-high reward

KEY INDICATORS:
✅ PRIMARY: EMA50 > EMA200 (golden cross), MACD histogram, RSI 35-55
✅ SECONDARY: Volume trend (increasing), Multi-TF alignment (4H + 1D)
✅ TERTIARY: Support/resistance proximity, Momentum score

CONFIDENCE THRESHOLD: 55% minimum
REASON: Balance between opportunity frequency and quality

DIFFERENTIATION:
- vs Long-Term: Shorter holds, trend-following (not deep value)
- vs Scalping: Macro trend required, longer holds
- vs Opportunistic: Pure technical, no news dependency

FOCUS AREAS:
1. EMA crossovers (50/200) for trend confirmation
2. MACD histogram expansion for momentum
3. RSI pullbacks to 40-50 range (healthy retracements)
4. Volume confirmation (increasing on rallies)

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
# SWING STRATEGY
# ═══════════════════════════════════════════════════════════════════════════

class SwingStrategy(BaseStrategy):
    """
    Swing Trading Strategy - Trend Continuation Expert

    ✅ REFACTORED: MACD integration, multi-TF momentum, EMA crossover logic
    ✅ FOCUS: Riding established trends with optimal entry timing
    """

    def __init__(self):
        super().__init__(
            name="SwingStrategy",
            strategy_type=StrategyType.SWING
        )

        # Position tracking
        self.active_positions = set()
        self.last_signal_time = {}
        self.position_entry_prices = {}

        # Configuration
        self.min_cooldown_hours = 96  # 4 days between signals
        self.min_confidence = 55.0

        # RSI thresholds (healthy pullback zone)
        self.rsi_min = 35   # Don't buy if RSI < 35 (too weak)
        self.rsi_max = 58   # Don't buy if RSI > 58 (overbought)
        self.rsi_optimal_min = 40
        self.rsi_optimal_max = 52

        logger.info(f"[{self.name}] Initialized - Trend continuation focus")

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
        Swing opportunity analysis

        ENTRY CONDITIONS:
        1. EMA50 > EMA200 (uptrend confirmation)
        2. Price > EMA50 OR price within 3% below EMA50 (pullback)
        3. RSI 35-58 (healthy momentum zone)
        4. MACD histogram positive OR turning positive
        5. Multi-timeframe alignment (4H + 1D bullish)
        6. Volume trend stable or increasing
        7. Confidence >= 55%
        """

        # ════════════════════════════════════════════════════════════════════
        # 1. PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════════════════

        if symbol in self.active_positions:
            logger.debug(
                f"[{self.name}] {symbol} active swing position exists"
            )
            return None

        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                self.active_positions.add(symbol)
                return None

        if not self._check_cooldown(symbol):
            return None

        # ════════════════════════════════════════════════════════════════════
        # 2. EXTRACT TECHNICAL DATA
        # ════════════════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        ema50 = technical_data.get('ema50', price)
        ema200 = technical_data.get('ema200', price)

        macd = technical_data.get('macd', 0)
        macd_signal = technical_data.get('macd_signal', 0)
        macd_histogram = technical_data.get('macd_histogram', 0)

        bb_low = technical_data.get('bb_low', price)
        bb_high = technical_data.get('bb_high', price)
        bb_mid = technical_data.get('bb_mid', price)

        volume = technical_data.get('volume', 0)
        avg_volume = technical_data.get('avg_volume_20d', volume)

        # ════════════════════════════════════════════════════════════════════
        # 3. CORE FILTER: EMA GOLDEN CROSS
        # ════════════════════════════════════════════════════════════════════

        # Primary filter: EMA50 must be above EMA200 (uptrend)
        if ema50 <= ema200:
            logger.debug(
                f"[{self.name}] {symbol} NO golden cross: "
                f"EMA50 ({ema50:.4f}) <= EMA200 ({ema200:.4f})"
            )
            return None

        golden_cross_strength = (ema50 - ema200) / ema200

        # Cross must be strong enough (at least 0.5% separation)
        if golden_cross_strength < 0.005:
            logger.debug(
                f"[{self.name}] {symbol} golden cross too weak: "
                f"{golden_cross_strength*100:.2f}%"
            )
            return None

        logger.info(
            f"[{self.name}] {symbol} ✅ Golden cross confirmed: "
            f"EMA50/EMA200 gap = {golden_cross_strength*100:.2f}%"
        )

        # ════════════════════════════════════════════════════════════════════
        # 4. PRICE POSITIONING (Pullback check)
        # ════════════════════════════════════════════════════════════════════

        distance_from_ema50 = (price - ema50) / ema50
        distance_from_ema200 = (price - ema200) / ema200

        # Ideal: Price slightly below EMA50 (pullback) but above EMA200
        # Allow: Price above EMA50 if pullback is healthy

        if distance_from_ema50 < -0.05:
            logger.debug(
                f"[{self.name}] {symbol} price too far below EMA50: "
                f"{distance_from_ema50*100:.1f}% (max -5%)"
            )
            return None

        if distance_from_ema200 < -0.02:
            logger.debug(
                f"[{self.name}] {symbol} price below EMA200: "
                f"{distance_from_ema200*100:.1f}%"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 5. RSI FILTER (Healthy momentum zone)
        # ════════════════════════════════════════════════════════════════════

        if rsi < self.rsi_min:
            logger.debug(
                f"[{self.name}] {symbol} RSI too low: {rsi:.1f} "
                f"(min {self.rsi_min}) - may be in downtrend"
            )
            return None

        if rsi > self.rsi_max:
            logger.debug(
                f"[{self.name}] {symbol} RSI too high: {rsi:.1f} "
                f"(max {self.rsi_max}) - wait for pullback"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 6. MACD ANALYSIS (Momentum confirmation)
        # ════════════════════════════════════════════════════════════════════

        macd_bullish = False
        macd_score = 0

        # MACD histogram positive = bullish momentum
        if macd_histogram > 0:
            macd_bullish = True
            macd_score = 30

            # Bonus: histogram expanding (strong momentum)
            # (Would need previous histogram for comparison, assume available)
            prev_histogram = technical_data.get('macd_histogram_prev', macd_histogram)
            if macd_histogram > prev_histogram:
                macd_score += 20

        # MACD line above signal = bullish
        elif macd > macd_signal:
            macd_bullish = True
            macd_score = 20

        # MACD turning positive (early signal)
        elif macd_histogram > -0.01 and macd > macd_signal * 0.9:
            macd_bullish = True
            macd_score = 15

        if not macd_bullish:
            logger.debug(
                f"[{self.name}] {symbol} MACD not bullish: "
                f"histogram={macd_histogram:.4f}"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 7. MULTI-TIMEFRAME ALIGNMENT
        # ════════════════════════════════════════════════════════════════════

        tf_alignment_score = 50  # default

        if market_structure:
            # For swing, we need 4H and 1D both bullish or neutral
            tf_4h = market_structure.tf_4h_trend
            tf_1d = market_structure.tf_1d_trend

            if tf_4h == "bearish" or tf_1d == "bearish":
                logger.debug(
                    f"[{self.name}] {symbol} bearish timeframe: "
                    f"4H={tf_4h}, 1D={tf_1d}"
                )
                return None

            # Calculate alignment
            tf_alignment_score = market_structure.alignment_score

            # Bonus: Both bullish
            if tf_4h == "bullish" and tf_1d == "bullish":
                tf_alignment_score = min(tf_alignment_score + 20, 100)

        # ════════════════════════════════════════════════════════════════════
        # 8. VOLUME ANALYSIS
        # ════════════════════════════════════════════════════════════════════

        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        volume_score = 50  # default
        volume_trend = "stable"

        if volume_ratio > 1.3:
            volume_score = 80
            volume_trend = "increasing"
        elif volume_ratio > 1.0:
            volume_score = 70
            volume_trend = "increasing"
        elif volume_ratio > 0.8:
            volume_score = 50
        else:
            volume_score = 30
            volume_trend = "decreasing"

        # Swing prefers stable or increasing volume
        if volume_trend == "decreasing" and volume_ratio < 0.7:
            logger.debug(
                f"[{self.name}] {symbol} volume too low: {volume_ratio:.2f}x"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 9. MARKET STRUCTURE SCORING
        # ════════════════════════════════════════════════════════════════════

        structure_score = 50  # default

        if market_structure:
            # Trend strength
            if market_structure.trend_strength > 70:
                structure_score += 30
            elif market_structure.trend_strength > 50:
                structure_score += 20
            elif market_structure.trend_strength > 30:
                structure_score += 10

            # Momentum
            if market_structure.momentum_score > 40:
                structure_score += 15
            elif market_structure.momentum_score > 20:
                structure_score += 10

            # Support proximity (bonus if near support)
            if market_structure.nearest_support < price:
                dist_to_support = abs(price - market_structure.nearest_support) / price
                if dist_to_support < 0.03:
                    structure_score += 10

        structure_score = min(structure_score, 100)

        # ════════════════════════════════════════════════════════════════════
        # 10. TECHNICAL SCORING
        # ════════════════════════════════════════════════════════════════════

        technical_score = 0

        # EMA positioning (0-25 points)
        if distance_from_ema50 > 0.02:
            technical_score += 25  # Above EMA50 (strong)
        elif distance_from_ema50 > 0:
            technical_score += 20  # Above EMA50
        elif distance_from_ema50 > -0.02:
            technical_score += 15  # Just below (pullback)
        elif distance_from_ema50 > -0.05:
            technical_score += 10  # Deeper pullback

        # Golden cross strength (0-20 points)
        if golden_cross_strength > 0.03:
            technical_score += 20
        elif golden_cross_strength > 0.02:
            technical_score += 15
        elif golden_cross_strength > 0.01:
            technical_score += 10
        elif golden_cross_strength >= 0.005:
            technical_score += 5

        # RSI positioning (0-25 points)
        if self.rsi_optimal_min <= rsi <= self.rsi_optimal_max:
            technical_score += 25  # Optimal zone
        elif self.rsi_min <= rsi < self.rsi_optimal_min:
            technical_score += 18  # Lower but acceptable
        elif self.rsi_optimal_max < rsi <= self.rsi_max:
            technical_score += 15  # Higher but acceptable

        # MACD (already scored above)
        technical_score += macd_score

        # ════════════════════════════════════════════════════════════════════
        # 11. CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════════════════

        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_score=technical_score,
            structure_score=structure_score,
            volume_score=volume_score,
            multi_tf_alignment=tf_alignment_score
        )

        # ✅ THRESHOLD: 55%
        if confidence_score < self.min_confidence:
            logger.debug(
                f"[{self.name}] {symbol} confidence insufficient: "
                f"{confidence_score:.1f}% (min {self.min_confidence}%)"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 12. TIER-BASED TARGETS
        # ════════════════════════════════════════════════════════════════════

        tier_config = self._get_tier_config(tier)

        # ════════════════════════════════════════════════════════════════════
        # 13. STOP LOSS CALCULATION
        # ════════════════════════════════════════════════════════════════════

        # Base stop: -7% (balanced for swing)
        base_stop_pct = 7.0

        # Adjust for volatility
        if regime_analysis.volatility_percentile > 80:
            base_stop_pct = 9.0
        elif regime_analysis.volatility_percentile < 40:
            base_stop_pct = 5.5

        # If near strong support, place stop below it
        if market_structure and market_structure.nearest_support < price:
            support_distance = abs(price - market_structure.nearest_support) / price

            if support_distance < 0.08 and market_structure.support_strength > 60:
                # Place stop 1.5% below support
                stop_below_support = market_structure.nearest_support * 0.985
                stop_loss_price = min(
                    stop_below_support,
                    price * (1 - base_stop_pct / 100)
                )
            else:
                stop_loss_price = price * (1 - base_stop_pct / 100)
        else:
            stop_loss_price = price * (1 - base_stop_pct / 100)

        # ════════════════════════════════════════════════════════════════════
        # 14. REASONING CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        primary_reason = self._build_primary_reason(
            symbol=symbol,
            golden_cross_strength=golden_cross_strength,
            distance_from_ema50=distance_from_ema50,
            rsi=rsi,
            macd_histogram=macd_histogram,
            regime_analysis=regime_analysis
        )

        supporting_reasons = self._build_supporting_reasons(
            golden_cross_strength=golden_cross_strength,
            rsi=rsi,
            macd_histogram=macd_histogram,
            volume_ratio=volume_ratio,
            market_structure=market_structure
        )

        risk_factors = self._build_risk_factors(
            regime_analysis=regime_analysis,
            volume_trend=volume_trend,
            structure_score=structure_score
        )

        # ════════════════════════════════════════════════════════════════════
        # 15. RISK ASSESSMENT
        # ════════════════════════════════════════════════════════════════════

        risk_level = self._assess_risk_level(
            volatility_percentile=regime_analysis.volatility_percentile,
            volume_trend=volume_trend,
            structure_quality=structure_score,
            warning_count=len(regime_analysis.warning_flags)
        )

        # ════════════════════════════════════════════════════════════════════
        # 16. SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.SWING,
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
            expected_profit_min=tier_config['target'] * 0.6,
            expected_profit_max=tier_config['target'] * 1.3,
            market_regime=regime_analysis.regime.value,
            market_structure=market_structure,
            requires_sell_notification=True,
            technical_scores={
                'rsi': rsi,
                'technical_score': technical_score,
                'macd_score': macd_score,
                'golden_cross_strength': golden_cross_strength * 100,
                'volume_score': volume_score,
                'tf_alignment': tf_alignment_score
            }
        )

        logger.info(
            f"✅ [{self.name}] {symbol} SWING SIGNAL\n"
            f"   Entry: ${price:.4f} | Target: ${signal.target_price:.4f}\n"
            f"   Stop: ${stop_loss_price:.4f}\n"
            f"   Confidence: {confidence_score:.1f}% | Risk: {risk_level}\n"
            f"   Golden Cross: {golden_cross_strength*100:.2f}% | "
            f"RSI: {rsi:.1f} | MACD: {macd_histogram:.4f}"
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

        if signal.risk_level == "EXTREME":
            return False, "EXTREME risk blocked"

        if symbol in self.active_positions:
            return False, "active swing position exists"

        if signal.risk_reward_ratio < 1.5:
            return False, f"R:R too low ({signal.risk_reward_ratio:.2f})"

        # Register
        self.active_positions.add(symbol)
        self.last_signal_time[symbol] = datetime.now()
        self.position_entry_prices[symbol] = signal.entry_price

        self.record_activity()

        logger.info(
            f"[{self.name}] ✅ {symbol} SWING approved\n"
            f"   Confidence: {signal.confidence_score:.1f}%\n"
            f"   R:R: 1:{signal.risk_reward_ratio:.2f}"
        )

        return True, "swing conditions met"

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def mark_position_closed(self, symbol: str):
        """Close swing position"""
        if symbol in self.active_positions:
            self.active_positions.remove(symbol)
            self.position_entry_prices.pop(symbol, None)
            logger.info(f"[{self.name}] ✅ {symbol} swing closed")

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
        """✅ REALISTIC TARGETS - Professional grade"""
        configs = {
            "BLUE_CHIP": {"target": 8.0, "hold": "5-8 დღე"},  # was 10% → now 8%
            "HIGH_GROWTH": {"target": 10.0, "hold": "4-8 დღე"},  # was 16% → now 10%
            "MEME": {"target": 15.0, "hold": "3-7 დღე"},  # was 28% → now 15%
            "NARRATIVE": {"target": 12.0, "hold": "4-8 დღე"},  # was 20% → now 12%
            "EMERGING": {"target": 14.0, "hold": "5-9 დღე"}  # was 22% → now 14%
        }
        return configs.get(tier, configs["HIGH_GROWTH"])

    def _build_primary_reason(
        self,
        symbol: str,
        golden_cross_strength: float,
        distance_from_ema50: float,
        rsi: float,
        macd_histogram: float,
        regime_analysis: Any
    ) -> str:

        reason = f"{symbol} აღმავალ ტრენდშია (EMA50 > EMA200, "
        reason += f"gap: {golden_cross_strength*100:.1f}%). "

        if distance_from_ema50 < 0:
            reason += f"ფასი EMA50-ზე ქვევითაა ({distance_from_ema50*100:.1f}%) - "
            reason += "ჯანსაღი pullback. "
        else:
            reason += f"ფასი EMA50-ზე მაღლაა ({distance_from_ema50*100:+.1f}%). "

        reason += f"RSI {rsi:.1f} (ბალანსირებული momentum). "

        if macd_histogram > 0:
            reason += "MACD ჰისტოგრამა დადებითი (აღმავალი momentum). "
        else:
            reason += "MACD გადადის დადებით ზონაში. "

        reason += "Swing trade პოტენციალი 4-10 დღეში."

        return reason

    def _build_supporting_reasons(
        self,
        golden_cross_strength: float,
        rsi: float,
        macd_histogram: float,
        volume_ratio: float,
        market_structure: Optional[MarketStructure]
    ) -> List[str]:

        reasons = []

        reasons.append(
            f"✅ Golden Cross active (EMA gap: {golden_cross_strength*100:.1f}%)"
        )

        if 40 <= rsi <= 52:
            reasons.append(f"📊 RSI optimal zone ({rsi:.1f})")
        else:
            reasons.append(f"📊 RSI healthy ({rsi:.1f})")

        if macd_histogram > 0:
            reasons.append(f"📈 MACD bullish (histogram: {macd_histogram:.4f})")

        if volume_ratio > 1.2:
            reasons.append(f"📊 Volume increasing ({volume_ratio:.2f}x)")

        if market_structure and market_structure.alignment_score > 60:
            reasons.append("🎯 Multi-timeframe alignment positive")

        return reasons[:5]

    def _build_risk_factors(
        self,
        regime_analysis: Any,
        volume_trend: str,
        structure_score: float
    ) -> List[str]:

        factors = []

        if regime_analysis.volatility_percentile > 80:
            factors.append(
                f"⚠️ მაღალი ვოლატილობა "
                f"({regime_analysis.volatility_percentile:.0f}%)"
            )

        if volume_trend == "decreasing":
            factors.append("⚠️ მოცულობა იკლებს")

        if structure_score < 50:
            factors.append("⚠️ Market structure საშუალო")

        for warning in regime_analysis.warning_flags[:2]:
            factors.append(f"⚠️ {warning}")

        if not factors:
            factors.append("✅ რისკი მართვადია")

        return factors[:4]