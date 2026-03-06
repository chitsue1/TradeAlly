"""
BASE STRATEGY FRAMEWORK - v3.0 FIXED
P2/#8: confidence score — base_score starts at 0 (was hidden +50 floor via structure_score=50, volume_score=50)
       All strategy min_confidence thresholds raised +5 to compensate for lower raw scores.
v2.0 unchanged in all other logic: multi-TF calculation, risk assessment, volume analysis
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    LONG_TERM    = "long_term"
    SWING        = "swing"
    SCALPING     = "scalping"
    OPPORTUNISTIC = "opportunistic"


class ConfidenceLevel(Enum):
    LOW       = "low"        # 40-59%
    MEDIUM    = "medium"     # 60-74%
    HIGH      = "high"       # 75-89%
    VERY_HIGH = "very_high"  # 90%+


class ActionType(Enum):
    BUY  = "buy"
    SELL = "sell"
    HOLD = "hold"


class MarketRegime(Enum):
    STRONG_UPTREND   = "strong_uptrend"
    UPTREND          = "uptrend"
    RANGING          = "ranging"
    DOWNTREND        = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    HIGH_VOLATILITY  = "high_volatility"


import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market_structure_builder import MarketStructure


@dataclass
class TradingSignal:
    symbol:                 str
    action:                 ActionType
    strategy_type:          StrategyType
    entry_price:            float
    target_price:           float
    stop_loss_price:        float
    expected_hold_duration: str
    entry_timestamp:        str
    confidence_level:       ConfidenceLevel
    confidence_score:       float
    risk_level:             str
    primary_reason:         str
    supporting_reasons:     List[str]
    risk_factors:           List[str]
    expected_profit_min:    float
    expected_profit_max:    float
    market_regime:          str
    market_structure:       Optional[MarketStructure] = None
    requires_sell_notification: bool = False
    timeframe_context:      Dict[str, str] = field(default_factory=dict)
    technical_scores:       Dict[str, float] = field(default_factory=dict)

    @property
    def price(self) -> float:
        return self.entry_price

    @property
    def risk_reward_ratio(self) -> float:
        risk   = abs(self.entry_price - self.stop_loss_price)
        reward = abs(self.target_price - self.entry_price)
        return reward / risk if risk > 0 else 0

    def to_message(self) -> str:
        if self.action == ActionType.BUY:
            return self._format_buy_message()
        return self._format_basic_message()

    def _format_buy_message(self) -> str:
        strategy_names  = {"long_term":"Long-Term Investment","swing":"Swing Trade","scalping":"Scalping","opportunistic":"Breakout Play"}
        strategy_badges = {"long_term":"🔵","swing":"🟢","scalping":"⚡","opportunistic":"🔥"}
        badge   = strategy_badges.get(self.strategy_type.value, "📊")
        sname   = strategy_names.get(self.strategy_type.value, "Trade")
        pp      = ((self.target_price - self.entry_price)   / self.entry_price) * 100
        lp      = abs((self.stop_loss_price - self.entry_price) / self.entry_price) * 100

        msg  = f"{badge} {sname}\n"
        msg += f"📈 იყიდეთ {self.symbol}\n\n"
        msg += f"💡 რატომ ახლა?\n{self.primary_reason}\n\n"
        if self.supporting_reasons:
            msg += "📊 ტექნიკური ფაქტორები:\n"
            for r in self.supporting_reasons[:5]:
                msg += f"  {r}\n"
            msg += "\n"
        msg += "💰 სავაჭრო გეგმა:\n"
        msg += f"• შესვლა: ${self.entry_price:.4f}\n"
        msg += f"• სამიზნე: ${self.target_price:.4f} (+{pp:.1f}%)\n"
        msg += f"• Stop-Loss: ${self.stop_loss_price:.4f} (-{lp:.1f}%)\n"
        msg += f"• R:R Ratio: 1:{self.risk_reward_ratio:.2f}\n"
        if self.expected_profit_min and self.expected_profit_max:
            msg += f"• მოსალოდნელი: {self.expected_profit_min:.1f}% - {self.expected_profit_max:.1f}%\n"
        msg += f"• Holding: {self.expected_hold_duration}\n\n"
        risk_emoji = {"LOW":"🟢","MEDIUM":"🟡","HIGH":"🟠","EXTREME":"🔴"}.get(self.risk_level,"⚪")
        msg += f"Confidence: {self.confidence_score:.0f}% | Risk: {risk_emoji} {self.risk_level}\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += "არ გესმით რა არის RSI, EMA, Stop-Loss? გამოიყენეთ: /guide"
        return msg

    def _format_basic_message(self) -> str:
        emoji   = "🟢" if self.action == ActionType.BUY else "🔴"
        tg      = ((self.target_price   / self.entry_price) - 1) * 100
        sp      = ((self.stop_loss_price / self.entry_price) - 1) * 100
        return (
            f"{emoji} **{self.action.value.upper()} SIGNAL** | {self.strategy_type.value.upper()}\n\n"
            f"**Asset:** {self.symbol}\n\n"
            f"**Price Levels:**\n"
            f"• Entry: ${self.entry_price:.4f}\n"
            f"• Target: ${self.target_price:.4f} (+{tg:.1f}%)\n"
            f"• Stop: ${self.stop_loss_price:.4f} ({sp:.1f}%)\n"
            f"• R:R: 1:{self.risk_reward_ratio:.2f}\n\n"
            f"**Reason:** {self.primary_reason}\n\n"
            f"Confidence: {self.confidence_score:.0f}% | Risk: {self.risk_level}"
        ).strip()


class BaseStrategy(ABC):

    def __init__(self, name: str, strategy_type: StrategyType):
        self.name               = name
        self.strategy_type      = strategy_type
        self.signals_generated  = 0
        self.last_activity      = None
        self.total_signals      = 0
        self.successful_signals = 0
        self.failed_signals     = 0

    @abstractmethod
    def analyze(self, symbol, price, regime_analysis, technical_data, tier,
                existing_position=None, market_structure=None) -> Optional[TradingSignal]:
        pass

    @abstractmethod
    def should_send_signal(self, symbol, signal) -> Tuple[bool, str]:
        pass

    # ─── P2/#8 — FIXED confidence calculation (no hidden +50 floor) ───────

    def _calculate_confidence(
        self,
        regime_confidence:  float,
        technical_score:    float,
        structure_score:    float,
        volume_score:       float = 0.0,   # ✅ was 50.0 default → now 0.0
        multi_tf_alignment: float = 50.0,
    ) -> Tuple[ConfidenceLevel, float]:
        """
        ✅ P2/#8 FIXED:
        - volume_score default changed 50.0 → 0.0
          (callers that don't pass volume will get 0 contribution, not fake 50)
        - structure_score callers should also start from 0 (not 50),
          each strategy's own scoring handles this
        - Weights unchanged: regime 25% + tech 30% + struct 20% + vol 15% + tf 10%
        """
        confidence_score = (
            regime_confidence  * 0.25 +
            technical_score    * 0.30 +
            structure_score    * 0.20 +
            volume_score       * 0.15 +
            multi_tf_alignment * 0.10
        )
        confidence_score = float(np.clip(confidence_score, 0, 100))

        if confidence_score >= 90:   level = ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 75: level = ConfidenceLevel.HIGH
        elif confidence_score >= 60: level = ConfidenceLevel.MEDIUM
        else:                        level = ConfidenceLevel.LOW

        return level, confidence_score

    def _assess_risk_level(
        self,
        volatility_percentile: float,
        volume_trend:          str,
        structure_quality:     float,
        warning_count:         int,
        drawdown_risk:         float = 0.0,
    ) -> str:
        rs = 0
        if   volatility_percentile > 95: rs += 40
        elif volatility_percentile > 85: rs += 30
        elif volatility_percentile > 70: rs += 20
        elif volatility_percentile > 50: rs += 10
        if   volume_trend == "decreasing": rs += 20
        elif volume_trend == "stable":     rs += 10
        if   structure_quality < 30: rs += 20
        elif structure_quality < 50: rs += 10
        rs += min(warning_count * 7, 20)
        if   rs >= 70: return "EXTREME"
        elif rs >= 50: return "HIGH"
        elif rs >= 30: return "MEDIUM"
        return "LOW"

    def _analyze_volume(
        self, current_volume: float, avg_volume_20d: float, volume_trend_data: List[float]
    ) -> Tuple[str, float]:
        vol_ratio = current_volume / avg_volume_20d if avg_volume_20d > 0 else 1.0
        if   vol_ratio > 2.0: percentile = 95
        elif vol_ratio > 1.5: percentile = 85
        elif vol_ratio > 1.2: percentile = 70
        elif vol_ratio > 0.8: percentile = 50
        else:                 percentile = 30
        if len(volume_trend_data) >= 5:
            r = volume_trend_data[-5:]
            if all(r[i] <= r[i+1] for i in range(len(r)-1)):  trend = "increasing"
            elif all(r[i] >= r[i+1] for i in range(len(r)-1)): trend = "decreasing"
            else:                                               trend = "stable"
        else:
            trend = "stable"
        return trend, percentile

    def _calculate_tf_alignment(self, tf_1h: str, tf_4h: str, tf_1d: str) -> float:
        tm = {"bullish": 100, "neutral": 50, "bearish": 0}
        return tm.get(tf_1h, 50)*0.2 + tm.get(tf_4h, 50)*0.3 + tm.get(tf_1d, 50)*0.5

    def record_activity(self):
        from datetime import datetime
        self.signals_generated += 1
        self.total_signals     += 1
        self.last_activity      = datetime.now()

    def record_outcome(self, success: bool):
        if success: self.successful_signals += 1
        else:       self.failed_signals     += 1

    def get_stats(self) -> Dict:
        wr = (self.successful_signals / self.total_signals * 100) if self.total_signals > 0 else 0
        return {
            "name": self.name, "type": self.strategy_type.value,
            "signals_generated": self.signals_generated,
            "total_signals":     self.total_signals,
            "successful":        self.successful_signals,
            "failed":            self.failed_signals,
            "win_rate":          f"{wr:.1f}%",
            "last_activity":     self.last_activity.isoformat() if self.last_activity else "Never",
        }