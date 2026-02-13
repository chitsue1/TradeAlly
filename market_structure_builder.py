"""
═══════════════════════════════════════════════════════════════════════════════
MARKET STRUCTURE BUILDER - PRODUCTION v1.0
═══════════════════════════════════════════════════════════════════════════════

PURPOSE: Build MarketStructure objects for strategies

FEATURES:
✅ Support/Resistance detection (simplified but effective)
✅ Volume trend analysis
✅ Momentum scoring
✅ Trend strength calculation
✅ Multi-timeframe simulation (1H, 4H, 1D)
✅ Volatility regime classification

AUTHOR: Trading System Architecture Team
CREATED: 2024-02-08
"""

import logging
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# MARKET STRUCTURE DATACLASS (imported by strategies)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MarketStructure:
    """Market structure analysis for strategies"""

    # Price levels
    nearest_support: float
    nearest_resistance: float
    support_strength: float  # 0-100
    resistance_strength: float  # 0-100

    # Volume analysis
    volume_trend: str  # "increasing", "decreasing", "stable"
    volume_percentile: float  # Current volume vs 20-day average

    # Momentum
    momentum_score: float  # -100 to +100
    trend_strength: float  # 0-100

    # Volatility
    volatility_regime: str  # "low", "normal", "high", "extreme"
    volatility_percentile: float

    # Multi-timeframe alignment
    tf_1h_trend: str  # "bullish", "bearish", "neutral"
    tf_4h_trend: str
    tf_1d_trend: str
    alignment_score: float  # 0-100

# ═══════════════════════════════════════════════════════════════════════════
# MARKET STRUCTURE BUILDER
# ═══════════════════════════════════════════════════════════════════════════

class MarketStructureBuilder:
    """
    Build MarketStructure from price and technical data

    ✅ Lightweight implementation - no heavy computation
    ✅ Uses existing indicators from market_data
    """

    def __init__(self):
        self.support_resistance_cache = {}  # Cache S/R levels
        logger.info("✅ MarketStructureBuilder initialized")

    def build(
        self,
        symbol: str,
        price: float,
        technical_data: Dict,
        regime_analysis: Optional[object] = None
    ) -> MarketStructure:
        """
        Build MarketStructure from available data

        Args:
            symbol: Trading symbol
            price: Current price
            technical_data: Dict with all indicators from market_data
            regime_analysis: Market regime object (optional)

        Returns:
            MarketStructure object
        """

        # ════════════════════════════════════════════════════════════════════
        # 1. SUPPORT/RESISTANCE DETECTION (simplified)
        # ════════════════════════════════════════════════════════════════════

        support, resistance, support_strength, resistance_strength = (
            self._detect_support_resistance(
                symbol=symbol,
                price=price,
                ema50=technical_data.get('ema50', price),
                ema200=technical_data.get('ema200', price),
                bb_low=technical_data.get('bb_low', price * 0.95),
                bb_high=technical_data.get('bb_high', price * 1.05),
                bb_mid=technical_data.get('bb_mid', price)
            )
        )

        # ════════════════════════════════════════════════════════════════════
        # 2. VOLUME ANALYSIS
        # ════════════════════════════════════════════════════════════════════

        volume = technical_data.get('volume', 1000000)
        avg_volume = technical_data.get('avg_volume_20d', volume)

        volume_trend, volume_percentile = self._analyze_volume(
            current_volume=volume,
            avg_volume=avg_volume
        )

        # ════════════════════════════════════════════════════════════════════
        # 3. MOMENTUM SCORE
        # ════════════════════════════════════════════════════════════════════

        momentum_score = self._calculate_momentum(
            price=price,
            prev_close=technical_data.get('prev_close', price),
            ema50=technical_data.get('ema50', price),
            rsi=technical_data.get('rsi', 50),
            macd_histogram=technical_data.get('macd_histogram', 0)
        )

        # ════════════════════════════════════════════════════════════════════
        # 4. TREND STRENGTH
        # ════════════════════════════════════════════════════════════════════

        trend_strength = self._calculate_trend_strength(
            price=price,
            ema50=technical_data.get('ema50', price),
            ema200=technical_data.get('ema200', price),
            rsi=technical_data.get('rsi', 50)
        )

        # ════════════════════════════════════════════════════════════════════
        # 5. VOLATILITY REGIME
        # ════════════════════════════════════════════════════════════════════

        volatility_regime = "normal"
        volatility_percentile = 50.0

        if regime_analysis:
            volatility_percentile = regime_analysis.volatility_percentile

            if volatility_percentile > 85:
                volatility_regime = "extreme"
            elif volatility_percentile > 70:
                volatility_regime = "high"
            elif volatility_percentile < 30:
                volatility_regime = "low"

        # ════════════════════════════════════════════════════════════════════
        # 6. MULTI-TIMEFRAME SIMULATION
        # ════════════════════════════════════════════════════════════════════

        tf_1h, tf_4h, tf_1d, alignment_score = self._simulate_multi_timeframe(
            price=price,
            ema50=technical_data.get('ema50', price),
            ema200=technical_data.get('ema200', price),
            rsi=technical_data.get('rsi', 50),
            macd_histogram=technical_data.get('macd_histogram', 0)
        )

        # ════════════════════════════════════════════════════════════════════
        # 7. BUILD MARKET STRUCTURE
        # ════════════════════════════════════════════════════════════════════

        market_structure = MarketStructure(
            nearest_support=support,
            nearest_resistance=resistance,
            support_strength=support_strength,
            resistance_strength=resistance_strength,
            volume_trend=volume_trend,
            volume_percentile=volume_percentile,
            momentum_score=momentum_score,
            trend_strength=trend_strength,
            volatility_regime=volatility_regime,
            volatility_percentile=volatility_percentile,
            tf_1h_trend=tf_1h,
            tf_4h_trend=tf_4h,
            tf_1d_trend=tf_1d,
            alignment_score=alignment_score
        )

        logger.debug(
            f"📊 MarketStructure {symbol}: "
            f"S/R: ${support:.4f}/${resistance:.4f} | "
            f"Trend: {trend_strength:.0f} | "
            f"TF: {tf_1h}/{tf_4h}/{tf_1d}"
        )

        return market_structure

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _detect_support_resistance(
        self,
        symbol: str,
        price: float,
        ema50: float,
        ema200: float,
        bb_low: float,
        bb_high: float,
        bb_mid: float
    ) -> Tuple[float, float, float, float]:
        """
        Detect nearest support and resistance levels

        Method: Use EMA levels + Bollinger Bands as dynamic S/R

        Returns:
            (support, resistance, support_strength, resistance_strength)
        """

        # Possible support levels
        support_candidates = []

        if ema200 < price:
            support_candidates.append((ema200, 80.0))  # EMA200 below = strong support

        if ema50 < price:
            support_candidates.append((ema50, 60.0))  # EMA50 below = medium support

        support_candidates.append((bb_low, 50.0))  # BB lower band

        # Nearest support
        if support_candidates:
            support_candidates.sort(key=lambda x: abs(price - x[0]))
            nearest_support, support_strength = support_candidates[0]
        else:
            nearest_support = price * 0.95  # Default: 5% below
            support_strength = 30.0

        # Possible resistance levels
        resistance_candidates = []

        if ema200 > price:
            resistance_candidates.append((ema200, 80.0))  # EMA200 above = strong resistance

        if ema50 > price:
            resistance_candidates.append((ema50, 60.0))  # EMA50 above = medium resistance

        resistance_candidates.append((bb_high, 50.0))  # BB upper band

        # Nearest resistance
        if resistance_candidates:
            resistance_candidates.sort(key=lambda x: abs(price - x[0]))
            nearest_resistance, resistance_strength = resistance_candidates[0]
        else:
            nearest_resistance = price * 1.05  # Default: 5% above
            resistance_strength = 30.0

        return nearest_support, nearest_resistance, support_strength, resistance_strength

    def _analyze_volume(
        self,
        current_volume: float,
        avg_volume: float
    ) -> Tuple[str, float]:
        """
        Analyze volume trend

        Returns:
            (trend: str, percentile: float)
        """

        if avg_volume == 0:
            return "stable", 50.0

        volume_ratio = current_volume / avg_volume

        # Classify trend
        if volume_ratio > 1.3:
            trend = "increasing"
        elif volume_ratio < 0.7:
            trend = "decreasing"
        else:
            trend = "stable"

        # Calculate percentile
        if volume_ratio > 2.5:
            percentile = 95.0
        elif volume_ratio > 2.0:
            percentile = 90.0
        elif volume_ratio > 1.5:
            percentile = 80.0
        elif volume_ratio > 1.2:
            percentile = 70.0
        elif volume_ratio > 0.8:
            percentile = 50.0
        elif volume_ratio > 0.5:
            percentile = 30.0
        else:
            percentile = 10.0

        return trend, percentile

    def _calculate_momentum(
        self,
        price: float,
        prev_close: float,
        ema50: float,
        rsi: float,
        macd_histogram: float
    ) -> float:
        """
        Calculate momentum score (-100 to +100)

        Combines:
        - Price change
        - RSI momentum
        - MACD histogram
        """

        score = 0.0

        # Price change momentum (±30 points)
        if prev_close > 0:
            price_change_pct = ((price - prev_close) / prev_close) * 100
            score += np.clip(price_change_pct * 10, -30, 30)

        # RSI momentum (±40 points)
        rsi_momentum = (rsi - 50) * 0.8  # -40 to +40
        score += rsi_momentum

        # MACD histogram (±30 points)
        macd_contribution = np.clip(macd_histogram * 1000, -30, 30)
        score += macd_contribution

        return np.clip(score, -100, 100)

    def _calculate_trend_strength(
        self,
        price: float,
        ema50: float,
        ema200: float,
        rsi: float
    ) -> float:
        """
        Calculate trend strength (0-100)

        100 = very strong uptrend
        0 = very strong downtrend
        50 = neutral/ranging
        """

        score = 50.0  # Start neutral

        # EMA positioning (±30 points)
        if ema50 > ema200:
            ema_gap = (ema50 - ema200) / ema200
            score += min(ema_gap * 500, 30)  # Up to +30
        else:
            ema_gap = (ema200 - ema50) / ema200
            score -= min(ema_gap * 500, 30)  # Up to -30

        # Price vs EMA50 (±20 points)
        if ema50 > 0:
            price_vs_ema50 = (price - ema50) / ema50
            score += np.clip(price_vs_ema50 * 400, -20, 20)

        return np.clip(score, 0, 100)

    def _simulate_multi_timeframe(
        self,
        price: float,
        ema50: float,
        ema200: float,
        rsi: float,
        macd_histogram: float
    ) -> Tuple[str, str, str, float]:
        """
        Simulate multi-timeframe trends

        Since we only have 1H data, we infer other timeframes
        from current indicators

        Returns:
            (tf_1h, tf_4h, tf_1d, alignment_score)
        """

        # 1H timeframe (most reactive)
        if rsi > 55 and macd_histogram > 0:
            tf_1h = "bullish"
        elif rsi < 45 and macd_histogram < 0:
            tf_1h = "bearish"
        else:
            tf_1h = "neutral"

        # 4H timeframe (medium-term)
        if price > ema50 and ema50 > ema200:
            tf_4h = "bullish"
        elif price < ema50 and ema50 < ema200:
            tf_4h = "bearish"
        else:
            tf_4h = "neutral"

        # 1D timeframe (long-term)
        if ema50 > ema200:
            ema_gap = (ema50 - ema200) / ema200
            if ema_gap > 0.02:
                tf_1d = "bullish"
            else:
                tf_1d = "neutral"
        else:
            ema_gap = (ema200 - ema50) / ema200
            if ema_gap > 0.02:
                tf_1d = "bearish"
            else:
                tf_1d = "neutral"

        # Alignment score
        trend_map = {"bullish": 100, "neutral": 50, "bearish": 0}

        alignment_score = (
            trend_map[tf_1h] * 0.2 +
            trend_map[tf_4h] * 0.3 +
            trend_map[tf_1d] * 0.5
        )

        return tf_1h, tf_4h, tf_1d, alignment_score