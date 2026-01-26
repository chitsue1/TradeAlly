"""
Market Regime Detector - Professional Grade
✅ Bull / Bear / Range / High Volatility / Spontaneous Event
✅ Context-aware analysis
✅ NO blind indicator following
"""

import logging
import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# 1. ENUMS (კრიტიკულია სხვა სტრატეგიებთან იმპორტისთვის)
# ════════════════════════════════════════════════════════════════

class StrategyType(Enum):
    LONG_TERM = "long_term"
    SCALPING = "scalping"
    SWING = "swing"

class ActionType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class ConfidenceLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

# ════════════════════════════════════════════════════════════════
# 2. TRADING SIGNAL STRUCTURE
# ════════════════════════════════════════════════════════════════

@dataclass
class TradingSignal:
    """
    სავაჭრო სიგნალის სტრუქტურა. 
    შექმნილია ისე, რომ იმუშაოს როგორც ახალ, ისე ძველ კოდთან.
    """
    symbol: str
    action: ActionType
    strategy_type: StrategyType
    entry_price: float
    target_price: float
    stop_loss_price: float
    expected_hold_duration: str
    entry_timestamp: str
    confidence_level: ConfidenceLevel
    confidence_score: float
    risk_level: str
    primary_reason: str
    supporting_reasons: List[str]
    risk_factors: List[str]
    expected_profit_min: float
    expected_profit_max: float
    market_regime: str
    requires_sell_notification: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    # თავსებადობისთვის (Legacy Support)
    @property
    def signal_type(self) -> str:
        return self.action.value

    @property
    def price(self) -> float:
        return self.entry_price

# ════════════════════════════════════════════════════════════════
# 3. MARKET REGIME TYPES & ANALYSIS
# ════════════════════════════════════════════════════════════════

class MarketRegime(Enum):
    """ბაზრის რეჟიმები"""
    BULL_STRONG = "bull_strong"           # ძლიერი აღმავალი
    BULL_WEAK = "bull_weak"                # სუსტი აღმავალი
    BEAR_STRONG = "bear_strong"           # ძლიერი დაღმავალი
    BEAR_WEAK = "bear_weak"                # სუსტი დაღმავალი
    RANGE_BOUND = "range_bound"           # ფლეტი/რენჯი
    HIGH_VOLATILITY = "high_volatility"   # ექსტრემალური ვოლატილობა
    CONSOLIDATION = "consolidation"       # კონსოლიდაცია
    BREAKOUT_PENDING = "breakout_pending" # გარღვევის მოლოდინი
    SPONTANEOUS_EVENT = "spontaneous_event" # სპონტანური მოვლენა

@dataclass
class RegimeAnalysis:
    """ბაზრის რეჟიმის ანალიზის შედეგი"""
    regime: MarketRegime
    confidence: float  # 0-100
    trend_strength: float  # -1 (strong bear) to +1 (strong bull)
    volatility_percentile: float  # 0-100
    is_structural: bool  # სტრუქტურული ტრენდია თუ ხმაური
    reasoning: List[str]
    warning_flags: List[str]

    def is_favorable_for_long_term(self) -> bool:
        """ხელსაყრელია თუ არა გრძელვადიანი ინვესტიციისთვის"""
        favorable_regimes = [
            MarketRegime.BULL_STRONG,
            MarketRegime.BULL_WEAK,
            MarketRegime.CONSOLIDATION
        ]
        return self.regime in favorable_regimes and self.is_structural

    def is_favorable_for_scalping(self) -> bool:
        """ხელსაყრელია თუ არა სკალპინგისთვის"""
        favorable_regimes = [
            MarketRegime.HIGH_VOLATILITY,
            MarketRegime.BREAKOUT_PENDING
        ]
        return self.regime in favorable_regimes and self.volatility_percentile > 60

# ════════════════════════════════════════════════════════════════
# 4. BASE STRATEGY CLASS
# ════════════════════════════════════════════════════════════════

class BaseStrategy:
    """
    ბაზისური კლასი, რომელსაც ყველა სტრატეგია აპირობებს.
    აქ დევს საერთო ფუნქციონალი რისკის და ნდობის დასათვლელად.
    """
    def __init__(self, name: str, strategy_type: StrategyType):
        self.name = name
        self.strategy_type = strategy_type
        self.detector = MarketRegimeDetector()

    def _calculate_confidence(
        self, 
        regime_confidence: float, 
        technical_alignment: float, 
        structural_confidence: float
    ) -> tuple[ConfidenceLevel, float]:
        """საერთო ნდობის ინდექსის გამოთვლა"""

        # Weighted score calculation
        score = (regime_confidence * 0.4) + \
                (technical_alignment * 0.4) + \
                (structural_confidence * 0.2)

        if score >= 80:
            level = ConfidenceLevel.HIGH
        elif score >= 50:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        return level, score

    def _assess_risk_level(
        self, 
        volatility_percentile: float, 
        is_structural: bool, 
        warning_count: int
    ) -> str:
        """რისკის დონის განსაზღვრა"""

        if volatility_percentile > 85 or warning_count >= 3:
            return "EXTREME"

        if volatility_percentile > 65 or not is_structural:
            return "HIGH"

        if volatility_percentile > 35:
            return "MEDIUM"

        return "LOW"

# ════════════════════════════════════════════════════════════════
# 5. MARKET REGIME DETECTOR
# ════════════════════════════════════════════════════════════════

class MarketRegimeDetector:
    """
    Professional Market Regime Detection
    არ არის უბრალოდ "RSI < 30" → Buy
    არამედ: "რა ხდება ბაზარზე და რატომ?"
    """

    def __init__(self):
        self.regime_history = {}  # symbol → [regime, regime, ...]

    def analyze_regime(
        self, 
        symbol: str,
        price: float,
        price_history: np.ndarray,  # Last 200 closes
        rsi: float,
        ema200: float,
        bb_low: float,
        bb_high: float,
        volume_history: Optional[np.ndarray] = None
    ) -> RegimeAnalysis:
        """
        ძირითადი ფუნქცია - ბაზრის რეჟიმის გამოცნობა
        """

        reasoning = []
        warnings = []

        # 1. TREND ANALYSIS
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

        # 2. VOLATILITY ASSESSMENT
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

        # 3. STRUCTURAL vs NOISE
        is_structural = self._is_structural_move(
            price_history, trend_strength
        )

        if is_structural:
            reasoning.append("✅ სტრუქტურული მოძრაობა")
        else:
            reasoning.append("⚠️ შესაძლოა ხმაურია")
            warnings.append("არასტაბილური სიგნალი")

        # 4. BOLLINGER BAND POSITION
        bb_position = self._analyze_bollinger_position(
            price, bb_low, bb_high
        )
        reasoning.append(bb_position['description'])
        if bb_position['warning']:
            warnings.append(bb_position['warning'])

        # 5. REGIME CLASSIFICATION
        regime = self._classify_regime(
            trend_strength,
            volatility_percentile,
            is_structural,
            rsi,
            price,
            ema200
        )

        # 6. INTERNAL CONFIDENCE CALCULATION
        confidence = self._calculate_internal_confidence(
            is_structural,
            volatility_percentile,
            len(warnings)
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

    # ════════════════════════════════════════════════════════════
    # DETECTOR HELPERS (აქ არაფერია შეკუმშული)
    # ════════════════════════════════════════════════════════════

    def _calculate_trend_strength(
        self, 
        price: float, 
        ema200: float, 
        price_history: np.ndarray
    ) -> float:
        """ტრენდის სიძლიერის გამოთვლა [-1, 1] შუალედში"""
        # Distance from EMA200
        distance_from_ema = (price - ema200) / ema200

        # Recent price momentum (last 20 candles)
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
        """ადგენს არის თუ არა მოძრაობა სტრუქტურული"""
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
        """ბოლინჯერის ზოლების პოზიციის ანალიზი"""
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
        ts: float,
        vp: float,
        ist: bool,
        rsi: float,
        price: float,
        ema: float
    ) -> MarketRegime:
        """ყველა ფაქტორის საფუძველზე ბაზრის რეჟიმის კლასიფიკაცია"""

        if vp > 85:
            return MarketRegime.HIGH_VOLATILITY

        if ts > 0.6 and ist:
            return MarketRegime.BULL_STRONG

        if ts > 0.3 and ist:
            return MarketRegime.BULL_WEAK

        if ts < -0.6 and ist:
            return MarketRegime.BEAR_STRONG

        if ts < -0.3 and ist:
            return MarketRegime.BEAR_WEAK

        if abs(ts) < 0.2:
            if vp < 30:
                return MarketRegime.CONSOLIDATION
            else:
                return MarketRegime.RANGE_BOUND

        if vp < 25 and abs(ts) < 0.3:
            return MarketRegime.BREAKOUT_PENDING

        if not ist:
            return MarketRegime.SPONTANEOUS_EVENT

        return MarketRegime.RANGE_BOUND

    def _calculate_internal_confidence(
        self,
        is_structural: bool,
        volatility_percentile: float,
        warning_count: int
    ) -> float:
        """დეტექტორის შიდა ნდობის ინდექსი"""
        confidence = 50.0

        if is_structural:
            confidence += 20
        else:
            confidence -= 15

        if volatility_percentile > 80:
            confidence -= 20
        elif volatility_percentile < 20:
            confidence += 10

        confidence -= (warning_count * 10)
        return np.clip(confidence, 0, 100)

    def get_regime_context(self, symbol: str) -> str:
        """რეჟიმის კონტექსტი ისტორიაზე დაყრდნობით"""
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