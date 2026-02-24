"""
═══════════════════════════════════════════════════════════════════════════════
BASE STRATEGY FRAMEWORK - PRODUCTION REFACTORED v2.0
═══════════════════════════════════════════════════════════════════════════════

ARCHITECTURE IMPROVEMENTS:
✅ Enhanced confidence calculation (regime + technical + market structure)
✅ Multi-timeframe awareness
✅ Volume profile integration
✅ Volatility regime detection
✅ Market structure analysis (support/resistance)
✅ Telegram integration unchanged (fully compatible)

AUTHOR: Trading System Architecture Team
LAST UPDATE: 2024-02-05
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class StrategyType(Enum):
    """სტრატეგიის ტიპები"""
    LONG_TERM = "long_term"
    SWING = "swing"
    SCALPING = "scalping"
    OPPORTUNISTIC = "opportunistic"

class ConfidenceLevel(Enum):
    """ნდობის დონე"""
    LOW = "low"           # 40-59%
    MEDIUM = "medium"     # 60-74%
    HIGH = "high"         # 75-89%
    VERY_HIGH = "very_high"  # 90%+

class ActionType(Enum):
    """მოქმედების ტიპი"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class MarketRegime(Enum):
    """ბაზრის რეჟიმი"""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    RANGING = "ranging"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    HIGH_VOLATILITY = "high_volatility"

# ═══════════════════════════════════════════════════════════════════════════
# MARKET STRUCTURE DATACLASS
# ═══════════════════════════════════════════════════════════════════════════

# MarketStructure imported from market_structure_builder (single source of truth)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market_structure_builder import MarketStructure

# ═══════════════════════════════════════════════════════════════════════════
# TRADING SIGNAL - ENHANCED
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TradingSignal:
    """
    ვაჭრობის სიგნალი - გაუმჯობესებული ვერსია

    ✅ Telegram to_message() method (unchanged)
    ✅ Enhanced metadata for analytics
    ✅ Multi-timeframe context
    """
    # Core signal data
    symbol: str
    action: ActionType
    strategy_type: StrategyType
    entry_price: float
    target_price: float
    stop_loss_price: float
    expected_hold_duration: str
    entry_timestamp: str

    # Confidence & risk
    confidence_level: ConfidenceLevel
    confidence_score: float
    risk_level: str

    # Reasoning
    primary_reason: str
    supporting_reasons: List[str]
    risk_factors: List[str]

    # Profit expectations
    expected_profit_min: float
    expected_profit_max: float

    # Market context
    market_regime: str
    market_structure: Optional[MarketStructure] = None

    # Metadata
    requires_sell_notification: bool = False
    timeframe_context: Dict[str, str] = field(default_factory=dict)
    technical_scores: Dict[str, float] = field(default_factory=dict)

    @property
    def price(self) -> float:
        """Alias for entry_price"""
        return self.entry_price

    @property
    def risk_reward_ratio(self) -> float:
        """Calculate R:R ratio"""
        risk = abs(self.entry_price - self.stop_loss_price)
        reward = abs(self.target_price - self.entry_price)
        return reward / risk if risk > 0 else 0

    def to_message(self) -> str:
        """
        ✅ BEAUTIFUL & PERSONALIZED Telegram message

        - Natural language "why now" explanation
        - Clean, professional formatting
        - All essential info visible at a glance
        """

        if self.action == ActionType.BUY:
            return self._format_buy_message()
        else:
            # SELL signals handled separately (called from trading_engine)
            return self._format_basic_message()

    def _format_buy_message(self) -> str:
        """სიგნალის შეტყობინება — ქართული, სუფთა სტრუქტურა"""

        strategy_names = {
            "long_term": "Long-Term Investment",
            "swing": "Swing Trade",
            "scalping": "Scalping",
            "opportunistic": "Breakout Play"
        }
        strategy_badges = {
            "long_term": "🔵",
            "swing": "🟢",
            "scalping": "⚡",
            "opportunistic": "🔥"
        }

        badge = strategy_badges.get(self.strategy_type.value, "📊")
        strategy_name = strategy_names.get(self.strategy_type.value, "Trade")

        profit_pct = ((self.target_price - self.entry_price) / self.entry_price) * 100
        loss_pct   = abs((self.stop_loss_price - self.entry_price) / self.entry_price) * 100

        msg = f"{badge} {strategy_name}\n"
        msg += f"📈 იყიდეთ {self.symbol}\n\n"

        # Why now
        msg += f"💡 რატომ ახლა?\n"
        msg += f"{self.primary_reason}\n\n"

        # Technical factors
        if self.supporting_reasons:
            msg += "📊 ტექნიკური ფაქტორები:\n"
            for reason in self.supporting_reasons[:5]:
                msg += f"  {reason}\n"
            msg += "\n"

        # Trade plan
        msg += "💰 სავაჭრო გეგმა:\n"
        msg += f"• შესვლა: ${self.entry_price:.4f}\n"
        msg += f"• სამიზნე: ${self.target_price:.4f} (+{profit_pct:.1f}%)\n"
        msg += f"• Stop-Loss: ${self.stop_loss_price:.4f} (-{loss_pct:.1f}%)\n"
        msg += f"• R:R Ratio: 1:{self.risk_reward_ratio:.2f}\n"

        if self.expected_profit_min and self.expected_profit_max:
            msg += f"• მოსალოდნელი: {self.expected_profit_min:.1f}% - {self.expected_profit_max:.1f}%\n"

        msg += f"• Holding: {self.expected_hold_duration}\n\n"

        # Confidence footer
        risk_emoji = {
            "LOW": "🟢",
            "MEDIUM": "🟡",
            "HIGH": "🟠",
            "EXTREME": "🔴"
        }.get(self.risk_level, "⚪")

        msg += f"Confidence: {self.confidence_score:.0f}% | Risk: {risk_emoji} {self.risk_level}\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += "არ გესმით რა არის RSI, EMA, Stop-Loss? გამოიყენეთ: /guide"

        return msg

    def _format_basic_message(self) -> str:
        """Basic format for backward compatibility"""
        emoji = "🟢" if self.action == ActionType.BUY else "🔴"
        target_gain = ((self.target_price / self.entry_price) - 1) * 100
        stop_loss_pct = ((self.stop_loss_price / self.entry_price) - 1) * 100

        message = f"""
{emoji} **{self.action.value.upper()} SIGNAL** | {self.strategy_type.value.upper()}

**Asset:** {self.symbol}

**📊 Price Levels:**
• Entry: ${self.entry_price:.4f}
• Target: ${self.target_price:.4f} (+{target_gain:.1f}%)
• Stop Loss: ${self.stop_loss_price:.4f} ({stop_loss_pct:.1f}%)
• R:R Ratio: 1:{self.risk_reward_ratio:.2f}

**💡 Reason:**
{self.primary_reason}

**Confidence:** {self.confidence_score:.0f}% | **Risk:** {self.risk_level}
        """
        return message.strip()

# ═══════════════════════════════════════════════════════════════════════════
# BASE STRATEGY CLASS - REFACTORED
# ═══════════════════════════════════════════════════════════════════════════

class BaseStrategy(ABC):
    """
    ბაზისური სტრატეგიის კლასი - გაუმჯობესებული

    ყველა სტრატეგია ამ კლასს იღებს საფუძვლად.

    NEW FEATURES:
    - Multi-timeframe analysis
    - Volume profile integration
    - Enhanced confidence calculation
    - Market structure awareness
    """

    def __init__(self, name: str, strategy_type: StrategyType):
        self.name = name
        self.strategy_type = strategy_type
        self.signals_generated = 0
        self.last_activity = None

        # Performance tracking
        self.total_signals = 0
        self.successful_signals = 0
        self.failed_signals = 0

    @abstractmethod
    def analyze(
        self,
        symbol: str,
        price: float,
        regime_analysis,
        technical_data: Dict,
        tier: str,
        existing_position: Optional[object] = None,
        market_structure: Optional[MarketStructure] = None
    ) -> Optional[TradingSignal]:
        """
        მთავარი ანალიზის მეთოდი

        Args:
            symbol: Crypto symbol (e.g., "BTCUSDT")
            price: Current price
            regime_analysis: Market regime object
            technical_data: Dictionary with RSI, EMA, BB, MACD, etc.
            tier: Asset tier classification
            existing_position: Current position if any
            market_structure: Enhanced market structure analysis

        Returns:
            TradingSignal if opportunity found, None otherwise
        """
        pass

    @abstractmethod
    def should_send_signal(
        self,
        symbol: str,
        signal: TradingSignal
    ) -> Tuple[bool, str]:
        """
        უნდა გაიგზავნოს თუ არა სიგნალი?

        Returns:
            (bool, str): (should_send, reason)
        """
        pass

    # ═══════════════════════════════════════════════════════════════════════
    # ENHANCED CONFIDENCE CALCULATION
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_confidence(
        self,
        regime_confidence: float,
        technical_score: float,
        structure_score: float,
        volume_score: float = 50.0,
        multi_tf_alignment: float = 50.0
    ) -> Tuple[ConfidenceLevel, float]:
        """
        ნდობის გამოთვლა - გაუმჯობესებული

        Args:
            regime_confidence: Market regime confidence (0-100)
            technical_score: Technical indicators alignment (0-100)
            structure_score: Market structure quality (0-100)
            volume_score: Volume confirmation (0-100)
            multi_tf_alignment: Multi-timeframe alignment (0-100)

        Returns:
            (ConfidenceLevel, confidence_score)

        Weighting:
        - Regime: 25%
        - Technical: 30%
        - Structure: 20%
        - Volume: 15%
        - Multi-TF: 10%
        """
        confidence_score = (
            regime_confidence * 0.25 +
            technical_score * 0.30 +
            structure_score * 0.20 +
            volume_score * 0.15 +
            multi_tf_alignment * 0.10
        )

        confidence_score = np.clip(confidence_score, 0, 100)

        # Determine level
        if confidence_score >= 90:
            level = ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 75:
            level = ConfidenceLevel.HIGH
        elif confidence_score >= 60:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        return level, confidence_score

    # ═══════════════════════════════════════════════════════════════════════
    # RISK ASSESSMENT - ENHANCED
    # ═══════════════════════════════════════════════════════════════════════

    def _assess_risk_level(
        self,
        volatility_percentile: float,
        volume_trend: str,
        structure_quality: float,
        warning_count: int,
        drawdown_risk: float = 0.0
    ) -> str:
        """
        რისკის დონის შეფასება - გაუმჯობესებული

        Returns:
            "LOW" | "MEDIUM" | "HIGH" | "EXTREME"
        """
        risk_score = 0

        # Volatility contribution (0-40 points)
        if volatility_percentile > 95:
            risk_score += 40
        elif volatility_percentile > 85:
            risk_score += 30
        elif volatility_percentile > 70:
            risk_score += 20
        elif volatility_percentile > 50:
            risk_score += 10

        # Volume trend (0-20 points)
        if volume_trend == "decreasing":
            risk_score += 20
        elif volume_trend == "stable":
            risk_score += 10
        # "increasing" adds 0

        # Structure quality (0-20 points)
        if structure_quality < 30:
            risk_score += 20
        elif structure_quality < 50:
            risk_score += 10

        # Warnings (0-20 points)
        risk_score += min(warning_count * 7, 20)

        # Classify
        if risk_score >= 70:
            return "EXTREME"
        elif risk_score >= 50:
            return "HIGH"
        elif risk_score >= 30:
            return "MEDIUM"
        else:
            return "LOW"

    # ═══════════════════════════════════════════════════════════════════════
    # VOLUME ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════

    def _analyze_volume(
        self,
        current_volume: float,
        avg_volume_20d: float,
        volume_trend_data: List[float]
    ) -> Tuple[str, float]:
        """
        Volume ანალიზი

        Returns:
            (trend: str, percentile: float)
        """
        # Volume percentile
        volume_ratio = current_volume / avg_volume_20d if avg_volume_20d > 0 else 1.0

        if volume_ratio > 2.0:
            percentile = 95
        elif volume_ratio > 1.5:
            percentile = 85
        elif volume_ratio > 1.2:
            percentile = 70
        elif volume_ratio > 0.8:
            percentile = 50
        else:
            percentile = 30

        # Volume trend (last 5 periods)
        if len(volume_trend_data) >= 5:
            recent = volume_trend_data[-5:]
            if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
                trend = "increasing"
            elif all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return trend, percentile

    # ═══════════════════════════════════════════════════════════════════════
    # MULTI-TIMEFRAME ALIGNMENT
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_tf_alignment(
        self,
        tf_1h: str,
        tf_4h: str,
        tf_1d: str
    ) -> float:
        """
        Multi-timeframe alignment score

        Args:
            tf_1h, tf_4h, tf_1d: "bullish", "bearish", "neutral"

        Returns:
            0-100 score (100 = all bullish, 0 = all bearish, 50 = mixed)
        """
        trend_map = {"bullish": 100, "neutral": 50, "bearish": 0}

        score = (
            trend_map.get(tf_1h, 50) * 0.2 +
            trend_map.get(tf_4h, 50) * 0.3 +
            trend_map.get(tf_1d, 50) * 0.5
        )

        return score

    # ═══════════════════════════════════════════════════════════════════════
    # ACTIVITY TRACKING
    # ═══════════════════════════════════════════════════════════════════════

    def record_activity(self):
        """აქტივობის ჩაწერა"""
        from datetime import datetime
        self.signals_generated += 1
        self.total_signals += 1
        self.last_activity = datetime.now()

        logger.debug(
            f"[{self.name}] Activity recorded. "
            f"Total signals: {self.signals_generated}"
        )

    def record_outcome(self, success: bool):
        """Record signal outcome for performance tracking"""
        if success:
            self.successful_signals += 1
        else:
            self.failed_signals += 1

    def get_stats(self) -> Dict:
        """სტატისტიკის მიღება"""
        win_rate = (
            (self.successful_signals / self.total_signals * 100)
            if self.total_signals > 0 else 0
        )

        return {
            'name': self.name,
            'type': self.strategy_type.value,
            'signals_generated': self.signals_generated,
            'total_signals': self.total_signals,
            'successful': self.successful_signals,
            'failed': self.failed_signals,
            'win_rate': f"{win_rate:.1f}%",
            'last_activity': (
                self.last_activity.isoformat() 
                if self.last_activity else 'Never'
            )
        }

    def get_performance_metrics(self) -> Dict:
        """Get detailed performance metrics"""
        return {
            'strategy': self.name,
            'win_rate': (
                self.successful_signals / self.total_signals 
                if self.total_signals > 0 else 0
            ),
            'total_trades': self.total_signals,
            'wins': self.successful_signals,
            'losses': self.failed_signals
        }