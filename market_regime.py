"""
Market Regime Detector - FINAL CORRECTED
✅ Base confidence გაზრდილია
✅ არასტრუქტურული: -15 → -10
✅ High volatility: -20 → -15
✅ Warnings: *10 → *5
✅ Min confidence: 0% → 20%
"""

import logging
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# MARKET REGIME TYPES
# ════════════════════════════════════════════════════════════════

class MarketRegime(Enum):
    """ბაზრის რეჟიმები"""
    BULL_STRONG = "bull_strong"
    BULL_WEAK = "bull_weak"
    BEAR_STRONG = "bear_strong"
    BEAR_WEAK = "bear_weak"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    CONSOLIDATION = "consolidation"
    BREAKOUT_PENDING = "breakout_pending"
    SPONTANEOUS_EVENT = "spontaneous_event"

@dataclass
class RegimeAnalysis:
    """ბაზრის რეჟიმის ანალიზის შედეგი"""
    regime: MarketRegime
    confidence: float  # 0-100
    trend_strength: float  # -1 to +1
    volatility_percentile: float  # 0-100
    is_structural: bool
    reasoning: List[str]
    warning_flags: List[str]

    def is_favorable_for_long_term(self) -> bool:
        """ხელსაყრელია თუ არა გრძელვადიანი ინვესტიციისთვის"""
        return self.regime in [
            MarketRegime.BULL_STRONG,
            MarketRegime.BULL_WEAK,
            MarketRegime.CONSOLIDATION
        ] and self.is_structural

    def is_favorable_for_scalping(self) -> bool:
        """ხელსაყრელია თუ არა სკალპინგისთვის"""
        return self.regime in [
            MarketRegime.HIGH_VOLATILITY,
            MarketRegime.BREAKOUT_PENDING
        ] and self.volatility_percentile > 60

# ════════════════════════════════════════════════════════════════
# MARKET REGIME DETECTOR
# ════════════════════════════════════════════════════════════════

class MarketRegimeDetector:
    """
    Professional Market Regime Detection

    ✅ FIXED: Base confidence improved
    """

    def __init__(self):
        self.regime_history = {}

    def analyze_regime(
        self, 
        symbol: str,
        price: float,
        price_history: np.ndarray,
        rsi: float,
        ema200: float,
        bb_low: float,
        bb_high: float,
        volume_history: Optional[np.ndarray] = None
    ) -> RegimeAnalysis:
        """ძირითადი ფუნქცია - ბაზრის რეჟიმის გამოცნობა"""

        reasoning = []
        warnings = []

        # ════════════════════════════════════════════════════════
        # 1. TREND ANALYSIS
        # ════════════════════════════════════════════════════════

        trend_strength = self._calculate_trend_strength(
            price, ema200, price_history
        )

        if trend_strength > 0.7:
            reasoning.append(f"ძლიერი აღმავალი ტრენდი ({trend_strength:.2f})")
        elif trend_strength > 0.3:
            reasoning.append(f"საშუალო აღმავალი ტრენდი ({trend_strength:.2f})")
        elif trend_strength < -0.7:
            reasoning.append(f"ძლიერი დაღმავალი ტრენდი ({trend_strength:.2f})")
        elif trend_strength < -0.3:
            reasoning.append(f"საშუალო დაღმავალი ტრენდი ({trend_strength:.2f})")
        else:
            reasoning.append("ფლეტი/რენჯი")

        # ════════════════════════════════════════════════════════
        # 2. VOLATILITY ASSESSMENT
        # ════════════════════════════════════════════════════════

        volatility_percentile = self._calculate_volatility_percentile(
            price_history
        )

        if volatility_percentile > 90:
            reasoning.append("🔥 ექსტრემალური ვოლატილობა")
            warnings.append("მაღალი რისკი - სწრაფი მოძრაობები")
        elif volatility_percentile > 70:
            reasoning.append("⚡ მაღალი ვოლატილობა")
        elif volatility_percentile < 30:
            reasoning.append("💤 დაბალი ვოლატილობა (კონსოლიდაცია)")

        # ════════════════════════════════════════════════════════
        # 3. STRUCTURAL vs NOISE
        # ════════════════════════════════════════════════════════

        is_structural = self._is_structural_move(
            price_history, trend_strength
        )

        if is_structural:
            reasoning.append("✅ სტრუქტურული მოძრაობა")
        else:
            reasoning.append("⚠️ შესაძლოა ხმაურია")
            warnings.append("არასტაბილური სიგნალი")

        # ════════════════════════════════════════════════════════
        # 4. BOLLINGER BAND POSITION
        # ════════════════════════════════════════════════════════

        bb_position = self._analyze_bollinger_position(
            price, bb_low, bb_high
        )
        reasoning.append(bb_position['description'])
        if bb_position['warning']:
            warnings.append(bb_position['warning'])

        # ════════════════════════════════════════════════════════
        # 5. REGIME CLASSIFICATION
        # ════════════════════════════════════════════════════════

        regime = self._classify_regime(
            trend_strength,
            volatility_percentile,
            is_structural,
            rsi,
            price,
            ema200
        )

        # ════════════════════════════════════════════════════════
        # 6. CONFIDENCE CALCULATION - ✅ IMPROVED
        # ════════════════════════════════════════════════════════

        confidence = self._calculate_confidence(
            is_structural,
            volatility_percentile,
            len(warnings)
        )

        # ════════════════════════════════════════════════════════
        # 7. STORE HISTORY
        # ════════════════════════════════════════════════════════

        if symbol not in self.regime_history:
            self.regime_history[symbol] = []

        self.regime_history[symbol].append(regime)
        if len(self.regime_history[symbol]) > 10:
            self.regime_history[symbol].pop(0)

        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility_percentile=volatility_percentile,
            is_structural=is_structural,
            reasoning=reasoning,
            warning_flags=warnings
        )

    # ════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ════════════════════════════════════════════════════════════

    def _calculate_trend_strength(
        self, 
        price: float, 
        ema200: float, 
        price_history: np.ndarray
    ) -> float:
        """ტრენდის სიძლიერის გამოთვლა"""
        distance_from_ema = (price - ema200) / ema200

        if len(price_history) >= 20:
            recent_returns = np.diff(price_history[-20:]) / price_history[-20:-1]
            momentum = np.mean(recent_returns)
        else:
            momentum = 0

        trend_score = (distance_from_ema * 2) + (momentum * 100)
        return np.clip(trend_score, -1, 1)

    def _calculate_volatility_percentile(
        self, 
        price_history: np.ndarray
    ) -> float:
        """ვოლატილობის პერცენტილის გამოთვლა"""
        if len(price_history) < 21:
            return 50.0

        returns = np.diff(price_history) / price_history[:-1]
        current_vol = np.std(returns[-20:])
        historical_vol = np.std(returns)

        percentile = (current_vol / (historical_vol + 1e-10)) * 50
        return np.clip(percentile, 0, 100)

    def _is_structural_move(
        self, 
        price_history: np.ndarray, 
        trend_strength: float
    ) -> bool:
        """სტრუქტურული მოძრაობაა თუ ხმაური?"""
        if len(price_history) < 50:
            return True

        recent_prices = price_history[-50:]
        returns = np.diff(recent_prices) / recent_prices[:-1]

        if trend_strength > 0:
            consistency = np.sum(returns > 0) / len(returns)
        else:
            consistency = np.sum(returns < 0) / len(returns)

        return consistency > 0.6

    def _analyze_bollinger_position(
        self, 
        price: float, 
        bb_low: float, 
        bb_high: float
    ) -> Dict:
        """ბოლინჯერის ზოლების ანალიზი"""
        bb_range = bb_high - bb_low
        position_in_band = (price - bb_low) / bb_range if bb_range > 0 else 0.5

        if position_in_band < 0.1:
            return {
                'description': '📉 ბოლინჯერის ქვედა ზოლთან (oversold)',
                'warning': None
            }
        elif position_in_band > 0.9:
            return {
                'description': '📈 ბოლინჯერის ზედა ზოლთან (overbought)',
                'warning': 'გადახურების რისკი'
            }
        elif 0.4 <= position_in_band <= 0.6:
            return {
                'description': '⚖️ ბოლინჯერის შუაში (ნეიტრალური)',
                'warning': None
            }
        else:
            return {
                'description': '📊 ბოლინჯერის ზოლებში',
                'warning': None
            }

    def _classify_regime(
        self,
        trend_strength: float,
        volatility_percentile: float,
        is_structural: bool,
        rsi: float,
        price: float,
        ema200: float
    ) -> MarketRegime:
        """რეჟიმის კლასიფიკაცია"""

        if volatility_percentile > 85:
            return MarketRegime.HIGH_VOLATILITY

        if trend_strength > 0.6 and is_structural:
            return MarketRegime.BULL_STRONG
        elif trend_strength > 0.3 and is_structural:
            return MarketRegime.BULL_WEAK

        elif trend_strength < -0.6 and is_structural:
            return MarketRegime.BEAR_STRONG
        elif trend_strength < -0.3 and is_structural:
            return MarketRegime.BEAR_WEAK

        elif abs(trend_strength) < 0.2:
            if volatility_percentile < 30:
                return MarketRegime.CONSOLIDATION
            else:
                return MarketRegime.RANGE_BOUND

        elif volatility_percentile < 25 and abs(trend_strength) < 0.3:
            return MarketRegime.BREAKOUT_PENDING

        elif not is_structural:
            return MarketRegime.SPONTANEOUS_EVENT

        else:
            return MarketRegime.RANGE_BOUND

    def _calculate_confidence(
        self,
        is_structural: bool,
        volatility_percentile: float,
        warning_count: int
    ) -> float:
        """
        ✅ IMPROVED: Base confidence calculation

        Changes:
        - არასტრუქტურული: -15 → -10
        - High volatility: -20 → -15
        - Warnings: *10 → *5
        - Min confidence: 0% → 20%
        """
        confidence = 50.0  # Base

        # ✅ FIXED: არასტრუქტურული penalty reduced
        if is_structural:
            confidence += 20
        else:
            confidence -= 10  # ✅ was -15, now -10

        # ✅ FIXED: Volatility penalty reduced
        if volatility_percentile > 80:
            confidence -= 15  # ✅ was -20, now -15
        elif volatility_percentile < 20:
            confidence += 10

        # ✅ FIXED: Warning penalty reduced
        confidence -= (warning_count * 5)  # ✅ was *10, now *5

        # ✅ FIXED: Minimum confidence raised
        return np.clip(confidence, 20, 100)  # ✅ was (0, 100), now (20, 100)

    def get_regime_context(self, symbol: str) -> str:
        """რეჟიმის კონტექსტი"""
        if symbol not in self.regime_history:
            return "არ არის ისტორია"

        history = self.regime_history[symbol]
        if len(history) < 3:
            return f"მწირი ისტორია ({len(history)} სკანი)"

        recent_regimes = [r.value for r in history[-3:]]

        if len(set(recent_regimes)) == 1:
            return f"სტაბილური რეჟიმი: {history[-1].value}"
        else:
            return f"რეჟიმის ცვლილება: {' → '.join(recent_regimes)}"