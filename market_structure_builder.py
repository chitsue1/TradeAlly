"""
Market Structure Builder - PHASE 1 ENHANCED VERSION
Calculates support/resistance levels with strength metrics
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

@dataclass
class MarketStructure:
    # Core structure
    nearest_support:         float
    nearest_resistance:      float
    support_strength:        float   # 0-100
    resistance_strength:     float   # 0-100
    volume_trend:            str     # "increasing"/"decreasing"/"neutral"
    volume_momentum:         float
    structure_quality:       float   # 0-100
    support_distance_pct:    float
    resistance_distance_pct: float
    pivot_point:             float
    midpoint:                float
    # Multi-TF fields (used by strategies — defaults so old code still works)
    momentum_score:          float = 0.0
    trend_strength:          float = 50.0
    volatility_regime:       str   = "normal"
    volatility_percentile:   float = 50.0
    tf_1h_trend:             str   = "neutral"
    tf_4h_trend:             str   = "neutral"
    tf_1d_trend:             str   = "neutral"
    alignment_score:         float = 50.0
    volume_percentile:       float = 50.0


class MarketStructureBuilder:
    def __init__(self):
        logger.info("✅ MarketStructureBuilder initialized (Phase 1 Enhanced)")
        self.price_cache = {}

    def build(
        self,
        symbol: str,
        current_price: float,
        market_data: Dict,
        market_regime,
        price_history: List[float] = None
    ) -> MarketStructure:

        if price_history is None:
            price_history = self.price_cache.get(symbol, [current_price] * 200)
        else:
            self.price_cache[symbol] = price_history

        # Find support levels
        support_levels, support_strengths = self._find_support_levels(price_history, current_price)
        nearest_support = support_levels[0] if support_levels else current_price * 0.97
        support_strength_count = support_strengths[0] if support_strengths else 1

        # Find resistance levels
        resistance_levels, resistance_strengths = self._find_resistance_levels(price_history, current_price)
        nearest_resistance = resistance_levels[0] if resistance_levels else current_price * 1.03
        resistance_strength_count = resistance_strengths[0] if resistance_strengths else 1

        # Calculate distances
        support_distance_pct = ((current_price - nearest_support) / current_price) * 100
        resistance_distance_pct = ((nearest_resistance - current_price) / current_price) * 100

        # Analyze volume
        volume_trend, volume_momentum = self._analyze_volume_trend(market_data)

        # Calculate quality
        quality_score = self._calculate_structure_quality(
            support_strength_count,
            resistance_strength_count,
            support_distance_pct,
            resistance_distance_pct,
            volume_momentum,
            market_regime
        )

        # Calculate pivots
        pivot_point = (nearest_support + nearest_resistance) / 2
        midpoint = (nearest_support + current_price + nearest_resistance) / 3

        # Derive extra fields for strategy compatibility
        try:
            trend_str = str(getattr(market_regime, 'regime', '')).lower()
            if 'bull' in trend_str or 'uptrend' in trend_str:
                tf_trend = "bullish"
                trend_strength_val = 65.0
            elif 'bear' in trend_str or 'downtrend' in trend_str:
                tf_trend = "bearish"
                trend_strength_val = 35.0
            else:
                tf_trend = "neutral"
                trend_strength_val = 50.0
            vol_pct = float(getattr(market_regime, 'volatility_percentile', 50.0))
        except Exception:
            tf_trend = "neutral"
            trend_strength_val = 50.0
            vol_pct = 50.0

        momentum = min(max(volume_momentum, -100), 100)

        structure = MarketStructure(
            nearest_support=round(nearest_support, 4),
            nearest_resistance=round(nearest_resistance, 4),
            support_strength=float(support_strength_count),
            resistance_strength=float(resistance_strength_count),
            volume_trend=volume_trend,
            volume_momentum=round(volume_momentum, 1),
            structure_quality=round(quality_score, 1),
            support_distance_pct=round(support_distance_pct, 2),
            resistance_distance_pct=round(resistance_distance_pct, 2),
            pivot_point=round(pivot_point, 4),
            midpoint=round(midpoint, 4),
            momentum_score=round(momentum, 1),
            trend_strength=round(trend_strength_val, 1),
            volatility_regime="high" if vol_pct > 75 else "low" if vol_pct < 25 else "normal",
            volatility_percentile=round(vol_pct, 1),
            tf_1h_trend=tf_trend,
            tf_4h_trend=tf_trend,
            tf_1d_trend=tf_trend,
            alignment_score=65.0 if tf_trend == "bullish" else 35.0 if tf_trend == "bearish" else 50.0,
            volume_percentile=min(95.0, max(5.0, 50.0 + volume_momentum / 2)),
        )

        logger.info(
            f"✅ {symbol} Structure: "
            f"Support ${nearest_support:.4f}(x{int(support_strength_count)}), "
            f"Resistance ${nearest_resistance:.4f}(x{int(resistance_strength_count)}), "
            f"Quality {quality_score:.0f}/100"
        )

        return structure

    def _find_support_levels(
        self,
        price_history: List[float],
        current_price: float,
        lookback: int = 100
    ) -> Tuple[List[float], List[int]]:

        if not price_history or len(price_history) < 10:
            return [current_price * 0.97], [1]

        recent = price_history[-lookback:]
        supports = []

        # Find local minima
        for i in range(1, len(recent) - 1):
            if recent[i] < recent[i-1] and recent[i] < recent[i+1]:
                level = recent[i]
                if level < current_price * 0.99:
                    supports.append(level)

        if not supports:
            supports = [
                current_price * 0.98,
                current_price * 0.95,
                current_price * 0.90
            ]
        else:
            supports = list(set([round(s, 2) for s in supports]))
            supports = sorted(supports, key=lambda x: current_price - x)
            supports = supports[:3]

        strengths = []
        for support in supports:
            tolerance = support * 0.01
            touches = sum(1 for p in price_history if abs(p - support) <= tolerance)
            strengths.append(max(touches, 1))

        return supports, strengths

    def _find_resistance_levels(
        self,
        price_history: List[float],
        current_price: float,
        lookback: int = 100
    ) -> Tuple[List[float], List[int]]:

        if not price_history or len(price_history) < 10:
            return [current_price * 1.03], [1]

        recent = price_history[-lookback:]
        resistances = []

        # Find local maxima
        for i in range(1, len(recent) - 1):
            if recent[i] > recent[i-1] and recent[i] > recent[i+1]:
                level = recent[i]
                if level > current_price * 1.01:
                    resistances.append(level)

        if not resistances:
            resistances = [
                current_price * 1.02,
                current_price * 1.05,
                current_price * 1.10
            ]
        else:
            resistances = list(set([round(r, 2) for r in resistances]))
            resistances = sorted(resistances, key=lambda x: x - current_price)
            resistances = resistances[:3]

        strengths = []
        for resistance in resistances:
            tolerance = resistance * 0.01
            touches = sum(1 for p in price_history if abs(p - resistance) <= tolerance)
            strengths.append(max(touches, 1))

        return resistances, strengths

    def _analyze_volume_trend(self, market_data: Dict) -> Tuple[str, float]:

        volume = market_data.get('volume', 1)
        avg_volume = market_data.get('avg_volume_20d', 1)

        if volume == 0 or avg_volume == 0:
            return 'neutral', 0

        momentum = ((volume - avg_volume) / avg_volume) * 100

        if volume > avg_volume * 1.3:
            return 'increasing', min(momentum, 100)
        elif volume < avg_volume * 0.7:
            return 'decreasing', max(momentum, -100)
        else:
            return 'neutral', momentum

    def _calculate_structure_quality(
        self,
        support_strength: int,
        resistance_strength: int,
        support_distance_pct: float,
        resistance_distance_pct: float,
        volume_momentum: float,
        market_regime
    ) -> float:

        score = 50

        total_strength = support_strength + resistance_strength
        strength_bonus = min(total_strength * 2, 25)
        score += strength_bonus

        distance_diff = abs(support_distance_pct - resistance_distance_pct)
        if distance_diff < 0.5:
            score += 15
        elif distance_diff < 1.0:
            score += 12
        elif distance_diff < 2.0:
            score += 8
        elif distance_diff < 3.0:
            score += 4

        if volume_momentum > 50:
            score += 15
        elif volume_momentum > 20:
            score += 10
        elif volume_momentum > 0:
            score += 5

        try:
            if hasattr(market_regime, 'regime'):
                regime_str = str(market_regime.regime).lower()
                if 'strong' in regime_str and 'uptrend' in regime_str:
                    score += 10
                elif 'uptrend' in regime_str:
                    score += 7
                elif 'downtrend' in regime_str:
                    score += 5
        except:
            pass

        return min(score, 100)