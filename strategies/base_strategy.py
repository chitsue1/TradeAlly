"""
Base Strategy Module - CORRECTED & COMPLETE
✅ TradingSignal with to_message() INSIDE the class
✅ All enums and dataclasses properly structured
✅ Full analytics integration
✅ Signal validation
"""

import logging
import numpy as np
import sqlite3
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# 1. ENUMS
# ════════════════════════════════════════════════════════════════

class StrategyType(Enum):
    LONG_TERM = "long_term"
    SCALPING = "scalping"
    SWING = "swing"
    OPPORTUNISTIC = "opportunistic"

class ActionType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class ConfidenceLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

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

# ════════════════════════════════════════════════════════════════
# 2. TRADING SIGNAL - ✅ CORRECTED
# ════════════════════════════════════════════════════════════════

@dataclass
class TradingSignal:
    """
    ✅ CORRECTED: to_message() is now INSIDE the class
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

    # Legacy support properties
    @property
    def signal_type(self) -> str:
        return self.action.value

    @property
    def price(self) -> float:
        return self.entry_price

    # ✅ CRITICAL: to_message() method INSIDE the class
    def to_message(self) -> str:
        """
        Convert TradingSignal to Telegram message format

        ✅ This method is REQUIRED for send_signal() to work!
        """
        emoji = "🟢" if self.action == ActionType.BUY else "🔴"

        # Calculate percentage gains
        target_gain = ((self.target_price / self.entry_price) - 1) * 100
        stop_loss_pct = ((self.stop_loss_price / self.entry_price) - 1) * 100

        message = f"""
{emoji} **{self.action.value.upper()} SIGNAL**

**Asset:** {self.symbol}
**Strategy:** {self.strategy_type.value.replace('_', ' ').title()}

**📊 Price Info:**
• Entry: ${self.entry_price:.4f}
• Target: ${self.target_price:.4f} (+{target_gain:.1f}%)
• Stop Loss: ${self.stop_loss_price:.4f} ({stop_loss_pct:.1f}%)

**🎯 Expected:**
• Min Profit: +{self.expected_profit_min:.1f}%
• Max Profit: +{self.expected_profit_max:.1f}%
• Hold Duration: {self.expected_hold_duration}

**📈 Confidence:**
• Level: {self.confidence_level.value.upper()}
• Score: {self.confidence_score:.0f}%
• Risk: {self.risk_level}

**💡 Reasoning:**
{self.primary_reason}

**✅ Supporting Factors:**
{chr(10).join(f'• {reason}' for reason in self.supporting_reasons[:3])}

**⚠️ Risk Factors:**
{chr(10).join(f'• {risk}' for risk in self.risk_factors[:2])}

**🧠 Market Regime:** {self.market_regime}
**🕐 Signal Time:** {self.entry_timestamp}
        """

        return message.strip()


# ════════════════════════════════════════════════════════════════
# 3. REGIME ANALYSIS
# ════════════════════════════════════════════════════════════════

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
    ბაზისური კლასი ყველა სტრატეგიისთვის

    ✅ Fixed get_statistics() to return both formats
    ✅ Added _validate_signal() for signal validation
    """

    def __init__(self, name: str, strategy_type: StrategyType):
        self.name = name
        self.strategy_type = strategy_type
        self.db_path = "trading_bot_memory.db"
        self._init_stats_db()

    def _init_stats_db(self):
        """ქმნის ბაზას სტატისტიკისთვის"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_stats (
                    strategy_name TEXT PRIMARY KEY,
                    total_signals INTEGER DEFAULT 0,
                    last_active TIMESTAMP
                )
            """)
            conn.commit()

    def record_activity(self):
        """ინახავს აქტივობას როცა სიგნალი გენერირდება"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO strategy_stats (strategy_name, total_signals, last_active)
                VALUES (?, 1, ?)
                ON CONFLICT(strategy_name) DO UPDATE SET
                    total_signals = total_signals + 1,
                    last_active = excluded.last_active
            """, (self.name, datetime.now().isoformat()))
            conn.commit()

    def get_statistics(self) -> Dict[str, Any]:
        """
        ✅ FIXED: Returns both "total_signals" and "signals" for compatibility
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT total_signals, last_active FROM strategy_stats WHERE strategy_name = ?", 
                    (self.name,)
                )
                row = cursor.fetchone()

                if row:
                    total = row[0] or 0
                    last = row[1] or "Never"

                    return {
                        "total_signals": total,      # ✅ New format
                        "signals": total,             # ✅ Legacy support
                        "last_signal": last,
                        "last_active": last,
                        "strategy_name": self.name,
                        "strategy_type": self.strategy_type.value,
                        "status": "active" if total > 0 else "waiting"
                    }
                else:
                    return {
                        "total_signals": 0,
                        "signals": 0,
                        "last_signal": "Never",
                        "last_active": "Never",
                        "strategy_name": self.name,
                        "strategy_type": self.strategy_type.value,
                        "status": "initialized"
                    }

        except Exception as e:
            logger.error(f"❌ Error in {self.name}.get_statistics(): {e}")
            return {
                "total_signals": 0,
                "signals": 0,
                "last_signal": "Error",
                "strategy_name": self.name,
                "status": "error"
            }

    def _calculate_confidence(
        self, 
        regime_confidence: float, 
        technical_alignment: float, 
        structural_confidence: float
    ) -> tuple[ConfidenceLevel, float]:
        """Confidence calculation"""
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
        """Risk level assessment"""
        if volatility_percentile > 85 or warning_count >= 3:
            return "EXTREME"
        if volatility_percentile > 65 or not is_structural:
            return "HIGH"
        if volatility_percentile > 35:
            return "MEDIUM"
        return "LOW"

    def _validate_signal(self, signal: TradingSignal) -> tuple[bool, str]:
        """
        ✅ Signal validation before sending

        Checks:
        - Price logic (target > entry > stop)
        - Risk/Reward ratio
        - Confidence threshold
        """
        # Price logic check
        if signal.target_price <= signal.entry_price:
            return False, "Target price must be higher than entry price"

        if signal.stop_loss_price >= signal.entry_price:
            return False, "Stop loss must be lower than entry price"

        # Risk/Reward ratio
        potential_profit = (signal.target_price - signal.entry_price) / signal.entry_price
        potential_loss = (signal.entry_price - signal.stop_loss_price) / signal.entry_price

        if potential_loss > 0:
            risk_reward_ratio = potential_profit / potential_loss
            if risk_reward_ratio < 1.5:
                return False, f"Poor R/R ratio: {risk_reward_ratio:.2f} (min 1.5)"

        # Confidence check
        if signal.confidence_score < 50:
            return False, f"Confidence too low: {signal.confidence_score:.1f}%"

        # Extreme risk + low confidence block
        if signal.risk_level == "EXTREME" and signal.confidence_score < 75:
            return False, "EXTREME risk with low confidence blocked"

        return True, "Signal validated ✅"