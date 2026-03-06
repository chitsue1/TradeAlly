"""
Market Structure Builder - v2.0 FIXED
P1/#4: real multi-TF data (MultiTFData) injected from market_data.py
       — no more inference from single regime string
v1.0 (Phase 1 Enhanced) unchanged in all other logic
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# MultiTFData import (optional — graceful fallback if not available)
try:
    from market_data import MultiTFData
    MULTI_TF_AVAILABLE = True
except ImportError:
    MULTI_TF_AVAILABLE = False
    MultiTFData = None


@dataclass
class MarketStructure:
    nearest_support:          float
    nearest_resistance:       float
    support_strength:         float
    resistance_strength:      float
    volume_trend:             str
    volume_momentum:          float
    structure_quality:        float
    support_distance_pct:     float
    resistance_distance_pct:  float
    pivot_point:              float
    midpoint:                 float
    momentum_score:           float = 0.0
    trend_strength:           float = 50.0
    volatility_regime:        str   = "normal"
    volatility_percentile:    float = 50.0
    # ✅ P1/#4 — real TF trends (no more inference from regime string)
    tf_1h_trend:              str   = "neutral"
    tf_4h_trend:              str   = "neutral"
    tf_1d_trend:              str   = "neutral"
    alignment_score:          float = 50.0
    volume_percentile:        float = 50.0


class MarketStructureBuilder:

    def __init__(self):
        self.price_cache: Dict[str, List[float]] = {}
        logger.info("✅ MarketStructureBuilder v2.0 initialized (real multi-TF)")

    def build(
        self,
        symbol:        str,
        current_price: float,
        market_data:   Dict,
        market_regime,
        price_history: List[float] = None,
        multi_tf=None,               # ✅ P1/#4 — MultiTFData or None
    ) -> MarketStructure:

        if price_history is None:
            price_history = self.price_cache.get(symbol, [current_price] * 200)
        else:
            self.price_cache[symbol] = price_history

        support_levels, support_strengths = self._find_support_levels(price_history, current_price)
        nearest_support    = support_levels[0]    if support_levels    else current_price * 0.97
        support_str_count  = support_strengths[0] if support_strengths else 1

        resistance_levels, resistance_strengths = self._find_resistance_levels(price_history, current_price)
        nearest_resistance   = resistance_levels[0]    if resistance_levels    else current_price * 1.03
        resistance_str_count = resistance_strengths[0] if resistance_strengths else 1

        support_distance_pct    = ((current_price - nearest_support)    / current_price) * 100
        resistance_distance_pct = ((nearest_resistance - current_price) / current_price) * 100

        volume_trend, volume_momentum = self._analyze_volume_trend(market_data)
        quality_score = self._calculate_structure_quality(
            support_str_count, resistance_str_count,
            support_distance_pct, resistance_distance_pct,
            volume_momentum, market_regime
        )

        pivot_point = (nearest_support + nearest_resistance) / 2
        midpoint    = (nearest_support + current_price + nearest_resistance) / 3

        # ✅ P1/#4 — use real multi-TF data if available
        tf_1h = tf_4h = tf_1d = "neutral"
        alignment = 50.0
        trend_strength_val = 50.0

        if multi_tf is not None and MULTI_TF_AVAILABLE:
            tf_1h      = multi_tf.trend_1h
            tf_4h      = multi_tf.trend_4h
            tf_1d      = multi_tf.trend_1d
            alignment  = multi_tf.alignment_score
            # Trend strength from alignment
            trend_strength_val = alignment
        else:
            # Fallback: derive from regime only (v1.0 behaviour)
            trend_str = str(getattr(market_regime, "regime", "")).lower()
            if "bull" in trend_str or "uptrend" in trend_str:
                tf_1h = tf_4h = tf_1d = "bullish"
                trend_strength_val = 65.0
                alignment = 85.0
            elif "bear" in trend_str or "downtrend" in trend_str:
                tf_1h = tf_4h = tf_1d = "bearish"
                trend_strength_val = 35.0
                alignment = 15.0
            else:
                alignment = 50.0
                trend_strength_val = 50.0

        # Volatility from regime
        vol_pct = getattr(market_regime, "volatility_percentile", 50.0)
        if vol_pct > 80:
            vol_regime = "high"
        elif vol_pct > 50:
            vol_regime = "normal"
        else:
            vol_regime = "low"

        # Momentum score from price vs EMA
        ema50 = market_data.get("ema50", current_price)
        ema200 = market_data.get("ema200", current_price)
        mom_score = 50.0
        if ema50 > 0 and ema200 > 0:
            vs50  = (current_price - ema50)  / ema50  * 100
            vs200 = (current_price - ema200) / ema200 * 100
            mom_score = 50.0 + vs50 * 2 + vs200 * 1
            mom_score = max(0.0, min(100.0, mom_score))

        # Volume percentile
        volume    = market_data.get("volume", 0)
        avg_vol   = market_data.get("avg_volume_20d", 1)
        vol_ratio = volume / avg_vol if avg_vol > 0 and volume > 0 else 1.0
        vol_percentile = min(100.0, vol_ratio * 50.0)

        return MarketStructure(
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            support_strength=min(support_str_count * 10.0, 100.0),
            resistance_strength=min(resistance_str_count * 10.0, 100.0),
            volume_trend=volume_trend,
            volume_momentum=volume_momentum,
            structure_quality=quality_score,
            support_distance_pct=support_distance_pct,
            resistance_distance_pct=resistance_distance_pct,
            pivot_point=pivot_point,
            midpoint=midpoint,
            momentum_score=mom_score,
            trend_strength=trend_strength_val,
            volatility_regime=vol_regime,
            volatility_percentile=vol_pct,
            tf_1h_trend=tf_1h,
            tf_4h_trend=tf_4h,
            tf_1d_trend=tf_1d,
            alignment_score=alignment,
            volume_percentile=vol_percentile,
        )

    # ─── Support / Resistance detection (unchanged from v1.0) ─────────────

    def _find_support_levels(
        self, price_history: List[float], current_price: float
    ) -> Tuple[List[float], List[int]]:
        if len(price_history) < 10:
            return [current_price * 0.97], [1]

        prices = np.array(price_history)
        support_levels = []
        support_strengths = []

        window = max(5, len(prices) // 20)
        for i in range(window, len(prices) - window):
            if prices[i] == min(prices[max(0, i-window):i+window+1]):
                if prices[i] < current_price:
                    touches = sum(1 for p in prices if abs(p - prices[i]) / prices[i] < 0.015)
                    support_levels.append(float(prices[i]))
                    support_strengths.append(touches)

        if not support_levels:
            return [current_price * 0.97], [1]

        # Sort by proximity to current price
        paired = sorted(zip(support_levels, support_strengths),
                        key=lambda x: abs(x[0] - current_price))
        return [p[0] for p in paired[:5]], [p[1] for p in paired[:5]]

    def _find_resistance_levels(
        self, price_history: List[float], current_price: float
    ) -> Tuple[List[float], List[int]]:
        if len(price_history) < 10:
            return [current_price * 1.03], [1]

        prices = np.array(price_history)
        resistance_levels = []
        resistance_strengths = []

        window = max(5, len(prices) // 20)
        for i in range(window, len(prices) - window):
            if prices[i] == max(prices[max(0, i-window):i+window+1]):
                if prices[i] > current_price:
                    touches = sum(1 for p in prices if abs(p - prices[i]) / prices[i] < 0.015)
                    resistance_levels.append(float(prices[i]))
                    resistance_strengths.append(touches)

        if not resistance_levels:
            return [current_price * 1.03], [1]

        paired = sorted(zip(resistance_levels, resistance_strengths),
                        key=lambda x: abs(x[0] - current_price))
        return [p[0] for p in paired[:5]], [p[1] for p in paired[:5]]

    def _analyze_volume_trend(self, market_data: Dict) -> Tuple[str, float]:
        volume    = market_data.get("volume", 0)
        avg_vol   = market_data.get("avg_volume_20d", 1)
        vol_miss  = market_data.get("volume_missing", False)

        if vol_miss or avg_vol == 0:
            return "unknown", 0.0

        vol_ratio = volume / avg_vol
        if vol_ratio > 1.5:   return "increasing", min(vol_ratio, 3.0)
        elif vol_ratio > 0.8: return "stable",     vol_ratio
        else:                 return "decreasing", vol_ratio

    def _calculate_structure_quality(
        self,
        support_strength: int,
        resistance_strength: int,
        support_dist: float,
        resistance_dist: float,
        volume_momentum: float,
        market_regime,
    ) -> float:
        quality = 50.0
        quality += min(support_strength * 5, 20)
        quality += min(resistance_strength * 5, 20)
        if 2 < support_dist < 8:    quality += 10
        if 2 < resistance_dist < 10: quality += 10
        if volume_momentum > 1.2:   quality += 10
        elif volume_momentum < 0.8: quality -= 10
        warnings = getattr(market_regime, "warning_flags", [])
        quality -= len(warnings) * 5
        return max(0.0, min(100.0, quality))