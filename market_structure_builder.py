"""
═══════════════════════════════════════════════════════════════════════════════
MARKET STRUCTURE BUILDER v2.0 - PHASE 2 COMPATIBLE
═══════════════════════════════════════════════════════════════════════════════

Enhanced with ALL fields needed for trading_engine Phase 2:
- Support/Resistance with strength
- Volume trend
- Structure quality
- Multi-timeframe awareness
- Alignment score

AUTHOR: Trade Ally Bot
VERSION: 2.0 (Phase 2 Compatible)
"""

import logging
import numpy as np
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MarketStructure:
    """Market structure data - Phase 2 enhanced"""

    # Core support/resistance
    nearest_support: float
    nearest_resistance: float
    support_strength: int  # How many times touched
    resistance_strength: int

    # Distance percentages
    support_distance_pct: float  # % below current price
    resistance_distance_pct: float  # % above current price

    # Volume analysis
    volume_trend: str  # 'increasing', 'decreasing', 'stable'

    # Quality metrics
    structure_quality: float  # 0-100 score

    # ✅ NEW: Multi-timeframe (Phase 2)
    tf_1h_trend: str = "neutral"  # 'bullish', 'bearish', 'neutral'
    tf_4h_trend: str = "neutral"
    tf_1d_trend: str = "neutral"

    # ✅ NEW: Alignment score (Phase 2)
    alignment_score: float = 50.0  # 0-100, how aligned indicators are

    # Additional context
    price_near_support: bool = False
    price_near_resistance: bool = False


class MarketStructureBuilder:
    """
    Build market structure with support/resistance detection

    Phase 2 Features:
    ✅ Support/resistance with strength
    ✅ Volume trend analysis
    ✅ Structure quality scoring
    ✅ Multi-timeframe trends
    ✅ Indicator alignment
    """

    def __init__(self):
        self.lookback = 20  # Periods to analyze
        self.touch_threshold = 0.02  # 2% threshold for "touch"

    def build(
        self,
        symbol: str,
        current_price: float,
        technical_data: dict,
        regime
    ) -> MarketStructure:
        """
        Build complete market structure

        Args:
            symbol: Asset symbol
            current_price: Current price
            technical_data: Dict with indicators (rsi, ema50, ema200, etc.)
            regime: Market regime object

        Returns:
            MarketStructure object with ALL Phase 2 fields
        """

        try:
            # ════════════════════════════════════════════════════════════════
            # 1. FIND SUPPORT & RESISTANCE
            # ════════════════════════════════════════════════════════════════

            support_levels = self._find_support_levels(current_price, technical_data)
            resistance_levels = self._find_resistance_levels(current_price, technical_data)

            # Get nearest levels
            nearest_support = self._get_nearest_support(current_price, support_levels)
            nearest_resistance = self._get_nearest_resistance(current_price, resistance_levels)

            # Calculate strength (mock - in production would use price history)
            support_strength = self._calculate_level_strength(nearest_support, current_price)
            resistance_strength = self._calculate_level_strength(nearest_resistance, current_price)

            # ════════════════════════════════════════════════════════════════
            # 2. DISTANCE CALCULATIONS
            # ════════════════════════════════════════════════════════════════

            support_distance_pct = ((current_price - nearest_support) / current_price) * 100
            resistance_distance_pct = ((nearest_resistance - current_price) / current_price) * 100

            # ════════════════════════════════════════════════════════════════
            # 3. VOLUME TREND
            # ════════════════════════════════════════════════════════════════

            volume_trend = self._analyze_volume_trend(technical_data)

            # ════════════════════════════════════════════════════════════════
            # 4. STRUCTURE QUALITY
            # ════════════════════════════════════════════════════════════════

            structure_quality = self._calculate_structure_quality(
                support_strength,
                resistance_strength,
                support_distance_pct,
                resistance_distance_pct,
                volume_trend
            )

            # ════════════════════════════════════════════════════════════════
            # 5. MULTI-TIMEFRAME TRENDS (Phase 2)
            # ════════════════════════════════════════════════════════════════

            tf_1h_trend = self._determine_tf_trend(technical_data, "1h")
            tf_4h_trend = self._determine_tf_trend(technical_data, "4h")
            tf_1d_trend = self._determine_tf_trend(technical_data, "1d")

            # ════════════════════════════════════════════════════════════════
            # 6. ALIGNMENT SCORE (Phase 2)
            # ════════════════════════════════════════════════════════════════

            alignment_score = self._calculate_alignment_score(
                technical_data,
                tf_1h_trend,
                tf_4h_trend,
                tf_1d_trend
            )

            # ════════════════════════════════════════════════════════════════
            # 7. PROXIMITY FLAGS
            # ════════════════════════════════════════════════════════════════

            price_near_support = support_distance_pct < 2.0  # Within 2%
            price_near_resistance = resistance_distance_pct < 2.0

            # ════════════════════════════════════════════════════════════════
            # BUILD STRUCTURE
            # ════════════════════════════════════════════════════════════════

            structure = MarketStructure(
                nearest_support=nearest_support,
                nearest_resistance=nearest_resistance,
                support_strength=support_strength,
                resistance_strength=resistance_strength,
                support_distance_pct=support_distance_pct,
                resistance_distance_pct=resistance_distance_pct,
                volume_trend=volume_trend,
                structure_quality=structure_quality,
                tf_1h_trend=tf_1h_trend,
                tf_4h_trend=tf_4h_trend,
                tf_1d_trend=tf_1d_trend,
                alignment_score=alignment_score,
                price_near_support=price_near_support,
                price_near_resistance=price_near_resistance
            )

            logger.info(
                f"✅ {symbol} Structure: "
                f"Support ${nearest_support:.4f}(x{support_strength}), "
                f"Resistance ${nearest_resistance:.4f}(x{resistance_strength}), "
                f"Quality {structure_quality:.0f}/100"
            )

            return structure

        except Exception as e:
            logger.error(f"❌ Structure building error for {symbol}: {e}")
            # Return safe defaults
            return self._get_default_structure(current_price)

    # ═══════════════════════════════════════════════════════════════════════
    # SUPPORT/RESISTANCE DETECTION
    # ═══════════════════════════════════════════════════════════════════════

    def _find_support_levels(self, current_price: float, technical: dict) -> List[float]:
        """Find potential support levels"""
        levels = []

        # Use technical indicators as support
        if 'ema200' in technical and technical['ema200'] < current_price:
            levels.append(technical['ema200'])

        if 'ema50' in technical and technical['ema50'] < current_price:
            levels.append(technical['ema50'])

        if 'bb_low' in technical and technical['bb_low'] < current_price:
            levels.append(technical['bb_low'])

        # Add psychological levels (round numbers)
        psychological = self._get_psychological_levels(current_price, below=True)
        levels.extend(psychological)

        # Filter to only levels below current price
        levels = [l for l in levels if l < current_price and l > current_price * 0.8]

        return sorted(levels, reverse=True) if levels else [current_price * 0.95]

    def _find_resistance_levels(self, current_price: float, technical: dict) -> List[float]:
        """Find potential resistance levels"""
        levels = []

        # Use technical indicators as resistance
        if 'ema200' in technical and technical['ema200'] > current_price:
            levels.append(technical['ema200'])

        if 'ema50' in technical and technical['ema50'] > current_price:
            levels.append(technical['ema50'])

        if 'bb_high' in technical and technical['bb_high'] > current_price:
            levels.append(technical['bb_high'])

        # Add psychological levels
        psychological = self._get_psychological_levels(current_price, below=False)
        levels.extend(psychological)

        # Filter to only levels above current price
        levels = [l for l in levels if l > current_price and l < current_price * 1.2]

        return sorted(levels) if levels else [current_price * 1.05]

    def _get_psychological_levels(self, price: float, below: bool) -> List[float]:
        """Get psychological round number levels"""
        levels = []

        # Determine step size based on price magnitude
        if price >= 1000:
            step = 100
        elif price >= 100:
            step = 10
        elif price >= 10:
            step = 1
        elif price >= 1:
            step = 0.1
        else:
            step = 0.01

        # Find nearest round numbers
        base = int(price / step) * step

        if below:
            levels = [base - step, base - step * 2]
        else:
            levels = [base + step, base + step * 2]

        return levels

    def _get_nearest_support(self, current_price: float, levels: List[float]) -> float:
        """Get nearest support level below current price"""
        if not levels:
            return current_price * 0.95

        # Filter levels below price
        below = [l for l in levels if l < current_price]

        if not below:
            return current_price * 0.95

        # Return closest
        return max(below)

    def _get_nearest_resistance(self, current_price: float, levels: List[float]) -> float:
        """Get nearest resistance level above current price"""
        if not levels:
            return current_price * 1.05

        # Filter levels above price
        above = [l for l in levels if l > current_price]

        if not above:
            return current_price * 1.05

        # Return closest
        return min(above)

    def _calculate_level_strength(self, level: float, current_price: float) -> int:
        """
        Calculate how strong a level is (mock implementation)
        In production, would analyze price history
        """

        # Simple heuristic: closer = stronger
        distance_pct = abs(level - current_price) / current_price * 100

        if distance_pct < 1:
            return 8  # Very close, strong level
        elif distance_pct < 2:
            return 5
        elif distance_pct < 5:
            return 3
        else:
            return 1

    # ═══════════════════════════════════════════════════════════════════════
    # VOLUME ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════

    def _analyze_volume_trend(self, technical: dict) -> str:
        """Analyze volume trend"""

        if 'volume' not in technical or 'avg_volume_20d' not in technical:
            return 'stable'

        volume = technical['volume']
        avg_volume = technical['avg_volume_20d']

        if avg_volume == 0:
            return 'stable'

        ratio = volume / avg_volume

        if ratio > 1.3:
            return 'increasing'
        elif ratio < 0.7:
            return 'decreasing'
        else:
            return 'stable'

    # ═══════════════════════════════════════════════════════════════════════
    # QUALITY SCORING
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_structure_quality(
        self,
        support_strength: int,
        resistance_strength: int,
        support_distance: float,
        resistance_distance: float,
        volume_trend: str
    ) -> float:
        """
        Calculate overall structure quality (0-100)

        Factors:
        - Level strength (stronger = better)
        - Distance (optimal range 1-5%)
        - Volume confirmation
        """

        quality = 50.0  # Base score

        # Level strength (max +20)
        avg_strength = (support_strength + resistance_strength) / 2
        quality += min(avg_strength * 2, 20)

        # Distance quality (max +15)
        # Optimal: 1-5% away
        avg_distance = (support_distance + resistance_distance) / 2
        if 1 <= avg_distance <= 5:
            quality += 15
        elif 0.5 <= avg_distance <= 7:
            quality += 10
        elif avg_distance < 0.5:
            quality += 5  # Too close

        # Volume confirmation (max +15)
        if volume_trend == 'increasing':
            quality += 15
        elif volume_trend == 'stable':
            quality += 10
        elif volume_trend == 'decreasing':
            quality += 5

        return min(max(quality, 0), 100)

    # ═══════════════════════════════════════════════════════════════════════
    # MULTI-TIMEFRAME (PHASE 2)
    # ═══════════════════════════════════════════════════════════════════════

    def _determine_tf_trend(self, technical: dict, timeframe: str) -> str:
        """
        Determine trend for specific timeframe

        Uses EMA relationship as proxy
        """

        if 'ema50' not in technical or 'ema200' not in technical:
            return 'neutral'

        ema50 = technical['ema50']
        ema200 = technical['ema200']

        if ema50 > ema200 * 1.02:  # 2% above
            return 'bullish'
        elif ema50 < ema200 * 0.98:  # 2% below
            return 'bearish'
        else:
            return 'neutral'

    # ═══════════════════════════════════════════════════════════════════════
    # ALIGNMENT SCORE (PHASE 2)
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_alignment_score(
        self,
        technical: dict,
        tf_1h: str,
        tf_4h: str,
        tf_1d: str
    ) -> float:
        """
        Calculate how aligned indicators are (0-100)

        High alignment = all pointing same direction
        """

        score = 50.0  # Base

        # Check RSI alignment with EMAs
        if 'rsi' in technical and 'ema50' in technical and 'ema200' in technical:
            rsi = technical['rsi']

            if technical['ema50'] > technical['ema200']:  # Bullish EMAs
                if rsi > 50:  # RSI also bullish
                    score += 15
                elif rsi < 40:  # RSI bearish (divergence)
                    score -= 10
            elif technical['ema50'] < technical['ema200']:  # Bearish EMAs
                if rsi < 50:  # RSI also bearish
                    score += 15
                elif rsi > 60:  # RSI bullish (divergence)
                    score -= 10

        # Check MACD alignment
        if 'macd' in technical and 'macd_signal' in technical:
            if technical['macd'] > technical['macd_signal']:
                score += 10  # Bullish MACD
            else:
                score -= 5  # Bearish MACD

        # Check timeframe alignment
        trends = [tf_1h, tf_4h, tf_1d]
        bullish_count = trends.count('bullish')
        bearish_count = trends.count('bearish')

        if bullish_count == 3:
            score += 25  # All bullish
        elif bullish_count == 2:
            score += 15  # Mostly bullish
        elif bearish_count == 3:
            score -= 25  # All bearish
        elif bearish_count == 2:
            score -= 15  # Mostly bearish

        return min(max(score, 0), 100)

    # ═══════════════════════════════════════════════════════════════════════
    # DEFAULT STRUCTURE
    # ═══════════════════════════════════════════════════════════════════════

    def _get_default_structure(self, current_price: float) -> MarketStructure:
        """Return safe default structure when analysis fails"""

        return MarketStructure(
            nearest_support=current_price * 0.95,
            nearest_resistance=current_price * 1.05,
            support_strength=1,
            resistance_strength=1,
            support_distance_pct=5.0,
            resistance_distance_pct=5.0,
            volume_trend='stable',
            structure_quality=50.0,
            tf_1h_trend='neutral',
            tf_4h_trend='neutral',
            tf_1d_trend='neutral',
            alignment_score=50.0,
            price_near_support=False,
            price_near_resistance=False
        )


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def prepare_market_structure(
    symbol: str,
    current_price: float,
    technical_data: dict,
    regime
) -> MarketStructure:
    """
    Convenience function to build market structure

    Usage:
        structure = prepare_market_structure(symbol, price, technical, regime)
    """
    builder = MarketStructureBuilder()
    return builder.build(symbol, current_price, technical_data, regime)