"""
Market Regime Detector v2.0 - PROFESSIONAL REALISM
✅ Base confidence: 50 → 35
✅ Structural bonus: +20 → +15
✅ Non-structural penalty: -10 → -20
✅ High volatility: -15 → -25
✅ Warning penalty: *5 → *8
✅ Min confidence: 20% → 15%
✅ Max confidence: 100% → 75%

RESULT: Much more conservative, realistic confidence scores
"""

import logging
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

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
    confidence: float
    trend_strength: float
    volatility_percentile: float
    is_structural: bool
    reasoning: List[str]
    warning_flags: List[str]

    def is_favorable_for_long_term(self) -> bool:
        return self.regime in [
            MarketRegime.BULL_STRONG,
            MarketRegime.BULL_WEAK,
            MarketRegime.CONSOLIDATION
        ] and self.is_structural

    def is_favorable_for_scalping(self) -> bool:
        return self.regime in [
            MarketRegime.HIGH_VOLATILITY,
            MarketRegime.BREAKOUT_PENDING
        ] and self.volatility_percentile > 60

class MarketRegimeDetector:
    """
    ✅ PROFESSIONAL REALISTIC REGIME DETECTION

    Much more conservative confidence scoring
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

        # 1. TREND ANALYSIS
        trend_strength = self._calculate_trend_strength(price, ema200, price_history)

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

        # 2. VOLATILITY ASSESSMENT
        volatility_percentile = self._calculate_volatility_percentile(price_history)

        if volatility_percentile > 90:
            reasoning.append("🔥 ექსტრემალური ვოლატილობა")
            warnings.append("მაღალი რისკი - სწრაფი მოძრაობები")
        elif volatility_percentile > 70:
            reasoning.append("⚡ მაღალი ვოლატილობა")
            warnings.append("გაზრდილი რისკი")
        elif volatility_percentile < 30:
            reasoning.append("💤 დაბალი ვოლატილობა")

        # 3. STRUCTURAL vs NOISE
        is_structural = self._is_structural_move(price_history, trend_strength)

        if is_structural:
            reasoning.append("✅ სტრუქტურული მოძრაობა")
        else:
            reasoning.append("⚠️ შესაძლოა ხმაურია")
            warnings.append("არასტაბილური სიგნალი")

        # 4. BOLLINGER BAND POSITION
        bb_position = self._analyze_bollinger_position(price, bb_low, bb_high)
        reasoning.append(bb_position['description'])
        if bb_position['warning']:
            warnings.append(bb_position['warning'])

        # 5. REGIME CLASSIFICATION
        regime = self._classify_regime(
            trend_strength, volatility_percentile, is_structural,
            rsi, price, ema200
        )

        # 6. ✅ REALISTIC CONFIDENCE
        confidence = self._calculate_confidence(
            is_structural, volatility_percentile, len(warnings)
        )

        # 7. STORE HISTORY
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

    def _calculate_trend_strength(self, price: float, ema200: float, price_history: np.ndarray) -> float:
        distance_from_ema = (price - ema200) / ema200

        if len(price_history) >= 20:
            recent_returns = np.diff(price_history[-20:]) / price_history[-20:-1]
            momentum = np.mean(recent_returns)
        else:
            momentum = 0

        trend_score = (distance_from_ema * 2) + (momentum * 100)
        return np.clip(trend_score, -1, 1)

    def _calculate_volatility_percentile(self, price_history: np.ndarray) -> float:
        if len(price_history) < 21:
            return 50.0

        returns = np.diff(price_history) / price_history[:-1]
        current_vol = np.std(returns[-20:])
        historical_vol = np.std(returns)

        percentile = (current_vol / (historical_vol + 1e-10)) * 50
        return np.clip(percentile, 0, 100)

    def _is_structural_move(self, price_history: np.ndarray, trend_strength: float) -> bool:
        if len(price_history) < 50:
            return True

        recent_prices = price_history[-50:]
        returns = np.diff(recent_prices) / recent_prices[:-1]

        if trend_strength > 0:
            consistency = np.sum(returns > 0) / len(returns)
        else:
            consistency = np.sum(returns < 0) / len(returns)

        return consistency > 0.6

    def _analyze_bollinger_position(self, price: float, bb_low: float, bb_high: float) -> Dict:
        bb_range = bb_high - bb_low
        position_in_band = (price - bb_low) / bb_range if bb_range > 0 else 0.5

        if position_in_band < 0.1:
            return {
                'description': '📉 BB ქვედა ზოლთან (oversold)',
                'warning': None
            }
        elif position_in_band > 0.9:
            return {
                'description': '📈 BB ზედა ზოლთან (overbought)',
                'warning': 'გადახურების რისკი - ძალიან მაღალია'
            }
        elif 0.4 <= position_in_band <= 0.6:
            return {
                'description': '⚖️ BB შუაში (ნეიტრალური)',
                'warning': None
            }
        else:
            return {
                'description': '📊 BB ზოლებში',
                'warning': None
            }

    def _classify_regime(self, trend_strength: float, volatility_percentile: float,
                        is_structural: bool, rsi: float, price: float, ema200: float) -> MarketRegime:

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
        ✅ PROFESSIONAL REALISTIC CONFIDENCE

        Changes:
        - Base: 50 → 35 (start lower)
        - Structural: +20 → +15
        - Non-structural: -10 → -20
        - High volatility: -15 → -25
        - Warning penalty: *5 → *8
        - Min: 20% → 15%
        - Max: 100% → 75%
        """
        confidence = 35.0  # ✅ Base lower (was 50)

        # Structural/non-structural
        if is_structural:
            confidence += 15  # ✅ Less bonus (was +20)
        else:
            confidence -= 20  # ✅ Heavier penalty (was -10)

        # Volatility
        if volatility_percentile > 80:
            confidence -= 25  # ✅ Much heavier (was -15)
        elif volatility_percentile > 60:
            confidence -= 10  # ✅ NEW: penalty for moderate-high vol
        elif volatility_percentile < 20:
            confidence += 8  # ✅ Slight bonus for low vol

        # Warnings
        confidence -= (warning_count * 8)  # ✅ Heavier (was *5)

        # ✅ REALISTIC RANGE
        return np.clip(confidence, 15, 75)  # ✅ was (20, 100), now (15, 75)

    def get_regime_context(self, symbol: str) -> str:
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