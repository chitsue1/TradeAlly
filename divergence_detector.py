"""
═══════════════════════════════════════════════════════════════════════════════
DIVERGENCE DETECTOR - PHASE 2 ENHANCEMENT
═══════════════════════════════════════════════════════════════════════════════

ტექნიკური დივერგენციების აღმოჩენა (RSI, MACD, Volume)
გამოიყენება AI Risk Evaluator v2-ში უფრო ზუსტი შეფასებისთვის
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DivergenceResult:
    """Divergence detection result"""
    has_divergence: bool
    divergence_type: str  # 'bullish', 'bearish', or None
    strength: int  # 0-40
    confidence: float  # 0-100


class DivergenceDetector:
    """
    Detect technical divergences between price and indicators

    Bullish Divergence:
    - Price makes lower low
    - RSI/MACD makes higher low
    - Signal: Potential reversal UP

    Bearish Divergence:
    - Price makes higher high  
    - RSI/MACD makes lower high
    - Signal: Potential reversal DOWN
    """

    def __init__(self, lookback_periods: int = 10):
        self.lookback = lookback_periods

    def detect_rsi_divergence(
        self,
        prices: List[float],
        rsi_values: List[float]
    ) -> DivergenceResult:
        """
        RSI Divergence Detection

        Args:
            prices: List of price values (most recent last)
            rsi_values: List of RSI values (most recent last)

        Returns:
            DivergenceResult
        """

        if len(prices) < 3 or len(rsi_values) < 3:
            return DivergenceResult(False, None, 0, 0)

        # Get recent data
        recent_prices = prices[-self.lookback:]
        recent_rsi = rsi_values[-self.lookback:]

        # Find local minima/maxima
        price_lows = self._find_local_minima(recent_prices)
        rsi_lows = self._find_local_minima(recent_rsi)

        price_highs = self._find_local_maxima(recent_prices)
        rsi_highs = self._find_local_maxima(recent_rsi)

        # Check for BULLISH divergence (price lower, RSI higher)
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            # Compare last two lows
            price_lower = recent_prices[price_lows[-1]] < recent_prices[price_lows[-2]]
            rsi_higher = recent_rsi[rsi_lows[-1]] > recent_rsi[rsi_lows[-2]]

            if price_lower and rsi_higher:
                # Calculate strength
                price_drop_pct = abs(
                    (recent_prices[price_lows[-1]] - recent_prices[price_lows[-2]]) 
                    / recent_prices[price_lows[-2]]
                ) * 100

                rsi_rise = recent_rsi[rsi_lows[-1]] - recent_rsi[rsi_lows[-2]]

                # Strength: 0-40 points
                strength = min(int(price_drop_pct * 5 + rsi_rise), 40)
                confidence = min(strength * 2.5, 100)

                return DivergenceResult(
                    has_divergence=True,
                    divergence_type='bullish',
                    strength=strength,
                    confidence=confidence
                )

        # Check for BEARISH divergence (price higher, RSI lower)
        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            price_higher = recent_prices[price_highs[-1]] > recent_prices[price_highs[-2]]
            rsi_lower = recent_rsi[rsi_highs[-1]] < recent_rsi[rsi_highs[-2]]

            if price_higher and rsi_lower:
                price_rise_pct = abs(
                    (recent_prices[price_highs[-1]] - recent_prices[price_highs[-2]]) 
                    / recent_prices[price_highs[-2]]
                ) * 100

                rsi_drop = recent_rsi[rsi_highs[-2]] - recent_rsi[rsi_highs[-1]]

                strength = min(int(price_rise_pct * 5 + rsi_drop), 40)
                confidence = min(strength * 2.5, 100)

                return DivergenceResult(
                    has_divergence=True,
                    divergence_type='bearish',
                    strength=strength,
                    confidence=confidence
                )

        return DivergenceResult(False, None, 0, 0)

    def detect_macd_divergence(
        self,
        prices: List[float],
        macd_histogram: List[float]
    ) -> DivergenceResult:
        """
        MACD Histogram Divergence Detection

        Args:
            prices: List of price values
            macd_histogram: List of MACD histogram values

        Returns:
            DivergenceResult
        """

        if len(prices) < 3 or len(macd_histogram) < 3:
            return DivergenceResult(False, None, 0, 0)

        recent_prices = prices[-self.lookback:]
        recent_macd = macd_histogram[-self.lookback:]

        # BULLISH: Price lower lows, MACD higher lows
        price_lows = self._find_local_minima(recent_prices)
        macd_lows = self._find_local_minima(recent_macd)

        if len(price_lows) >= 2 and len(macd_lows) >= 2:
            price_lower = recent_prices[price_lows[-1]] < recent_prices[price_lows[-2]]
            macd_higher = recent_macd[macd_lows[-1]] > recent_macd[macd_lows[-2]]

            if price_lower and macd_higher:
                strength = min(
                    int(abs(recent_macd[macd_lows[-1]] - recent_macd[macd_lows[-2]]) * 1000),
                    40
                )

                return DivergenceResult(
                    has_divergence=True,
                    divergence_type='bullish',
                    strength=strength,
                    confidence=min(strength * 2.5, 100)
                )

        # BEARISH: Price higher highs, MACD lower highs
        price_highs = self._find_local_maxima(recent_prices)
        macd_highs = self._find_local_maxima(recent_macd)

        if len(price_highs) >= 2 and len(macd_highs) >= 2:
            price_higher = recent_prices[price_highs[-1]] > recent_prices[price_highs[-2]]
            macd_lower = recent_macd[macd_highs[-1]] < recent_macd[macd_highs[-2]]

            if price_higher and macd_lower:
                strength = min(
                    int(abs(recent_macd[macd_highs[-2]] - recent_macd[macd_highs[-1]]) * 1000),
                    40
                )

                return DivergenceResult(
                    has_divergence=True,
                    divergence_type='bearish',
                    strength=strength,
                    confidence=min(strength * 2.5, 100)
                )

        return DivergenceResult(False, None, 0, 0)

    def detect_price_volume_divergence(
        self,
        prices: List[float],
        volumes: List[float]
    ) -> DivergenceResult:
        """
        Price-Volume Divergence

        Bearish signal: Price rising but volume falling
        Bullish signal: Price falling but volume rising
        """

        if len(prices) < 5 or len(volumes) < 5:
            return DivergenceResult(False, None, 0, 0)

        # Recent 5 periods
        recent_prices = prices[-5:]
        recent_volumes = volumes[-5:]

        # Check trends
        price_trend = np.polyfit(range(5), recent_prices, 1)[0]  # Slope
        volume_trend = np.polyfit(range(5), recent_volumes, 1)[0]

        # BEARISH: Price UP, Volume DOWN
        if price_trend > 0 and volume_trend < 0:
            strength = min(
                int(abs(price_trend / np.mean(recent_prices)) * 1000 + 
                    abs(volume_trend / np.mean(recent_volumes)) * 500),
                40
            )

            return DivergenceResult(
                has_divergence=True,
                divergence_type='bearish',
                strength=strength,
                confidence=min(strength * 2, 80)
            )

        # BULLISH: Price DOWN, Volume UP
        elif price_trend < 0 and volume_trend > 0:
            strength = min(
                int(abs(price_trend / np.mean(recent_prices)) * 1000 + 
                    abs(volume_trend / np.mean(recent_volumes)) * 500),
                40
            )

            return DivergenceResult(
                has_divergence=True,
                divergence_type='bullish',
                strength=strength,
                confidence=min(strength * 2, 80)
            )

        return DivergenceResult(False, None, 0, 0)

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _find_local_minima(self, data: List[float]) -> List[int]:
        """Find indices of local minimum points"""
        minima = []

        for i in range(1, len(data) - 1):
            if data[i] < data[i-1] and data[i] < data[i+1]:
                minima.append(i)

        return minima

    def _find_local_maxima(self, data: List[float]) -> List[int]:
        """Find indices of local maximum points"""
        maxima = []

        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                maxima.append(i)

        return maxima


# ═══════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Example: Detect RSI divergence
    detector = DivergenceDetector(lookback_periods=10)

    # Sample data
    prices = [100, 98, 95, 96, 94, 92, 93, 95, 97, 96]  # Lower lows
    rsi_values = [30, 32, 28, 31, 30, 29, 32, 35, 38, 40]  # Higher lows

    result = detector.detect_rsi_divergence(prices, rsi_values)

    if result.has_divergence:
        print(f"✅ {result.divergence_type.upper()} divergence detected!")
        print(f"   Strength: {result.strength}/40")
        print(f"   Confidence: {result.confidence:.1f}%")
    else:
        print("❌ No divergence detected")