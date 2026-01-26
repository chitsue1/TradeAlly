"""
Opportunistic Strategy
✅ საათები → რამდენიმე დღე
✅ სპონტანური მოვლენები
✅ არასტანდარტული სიტუაციები
"""

import logging
from typing import Optional, Dict
from datetime import datetime

from .base_strategy import (
    BaseStrategy, TradingSignal, StrategyType,
    ConfidenceLevel, ActionType
)

logger = logging.getLogger(__name__)

class OpportunisticStrategy(BaseStrategy):
    """
    ოპორტუნისტული სტრატეგია

    მიზანი: არასტანდარტული, სპონტანური შესაძლებლობების დაჭერა

    რა არის "ოპორტუნისტული შესაძლებლობა":
    1. ბაზარზე ხდება არასტანდარტული მოვლენა
    2. ფასი გამოდის შეკუმშვიდან (consolidation → breakout)
    3. მოძრაობა არ ჯდება ჩვეულებრივ ტრენდში
    4. სპონტანური ვოლატილობის ზრდა

    ⚠️ ეს სიგნალი არ არის ხშირი - მხოლოდ განსაკუთრებულ სიტუაციებში
    """

    def __init__(self):
        super().__init__(
            name="OpportunisticStrategy",
            strategy_type=StrategyType.OPPORTUNISTIC
        )

        # ძალიან იშვიათი სიგნალები → გრძელი cooldown
        self.last_signal_time = {}
        self.cooldown_hours = 72  # 3 days

        # Max 1 signal per week per asset
        self.weekly_signal_count = {}

    def analyze(
        self,
        symbol: str,
        price: float,
        regime_analysis,
        technical_data: Dict,
        tier: str,
        existing_position: Optional[object] = None
    ) -> Optional[TradingSignal]:
        """
        ოპორტუნისტული შესაძლებლობის ანალიზი
        """

        # ════════════════════════════════════════════════════════
        # 1. PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════

        # Cooldown + Weekly limit
        if not self._check_cooldown(symbol):
            return None

        if not self._check_weekly_limit(symbol):
            return None

        # ════════════════════════════════════════════════════════
        # 2. REGIME VALIDATION - SPONTANEOUS EVENT
        # ════════════════════════════════════════════════════════

        # ოპორტუნისტული სიგნალი მხოლოდ სპონტანურ/breakout რეჟიმში
        from market_regime import MarketRegime

        valid_regimes = [
            MarketRegime.SPONTANEOUS_EVENT,
            MarketRegime.BREAKOUT_PENDING,
            MarketRegime.HIGH_VOLATILITY
        ]

        if regime_analysis.regime not in valid_regimes:
            logger.debug(
                f"[OPPORTUNISTIC] {symbol} არ არის სპონტანური რეჟიმი: "
                f"{regime_analysis.regime.value}"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 3. TECHNICAL VALIDATION - UNUSUAL CONDITIONS
        # ════════════════════════════════════════════════════════

        rsi = technical_data['rsi']
        ema200 = technical_data['ema200']
        bb_low = technical_data['bb_low']
        bb_high = technical_data['bb_high']

        # ოპორტუნისტული პირობები (ერთ-ერთი უნდა დაკმაყოფილდეს):

        is_breakout = self._detect_breakout(price, bb_low, bb_high)
        is_spontaneous_move = regime_analysis.regime == MarketRegime.SPONTANEOUS_EVENT
        is_extreme_oversold = rsi < 20

        if not (is_breakout or is_spontaneous_move or is_extreme_oversold):
            logger.debug(
                f"[OPPORTUNISTIC] {symbol} არ აკმაყოფილებს "
                f"არცერთ ოპორტუნისტულ პირობას"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 4. WHY IS THIS SPONTANEOUS?
        # ════════════════════════════════════════════════════════

        spontaneous_reason = self._identify_spontaneous_reason(
            is_breakout,
            is_spontaneous_move,
            is_extreme_oversold,
            regime_analysis
        )

        # ════════════════════════════════════════════════════════
        # 5. CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════

        technical_score = 0

        if is_extreme_oversold:
            technical_score += 40

        if is_breakout:
            technical_score += 35

        if is_spontaneous_move:
            technical_score += 25

        # Volatility boost
        if regime_analysis.volatility_percentile > 75:
            technical_score += 10

        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_alignment=technical_score,
            structural_confidence=50  # ოპორტუნისტული არ არის სტრუქტურული
        )

        # Minimum confidence threshold
        if confidence_score < 55:
            logger.debug(
                f"[OPPORTUNISTIC] {symbol} confidence ძალიან დაბალია: "
                f"{confidence_score:.0f}%"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 6. PROFIT TARGET & HOLD DURATION
        # ════════════════════════════════════════════════════════

        # Tier-ის მიხედვით
        if tier == "BLUE_CHIP":
            profit_target = 8.0
            hold_duration = "1-3 დღე"
        elif tier == "HIGH_GROWTH":
            profit_target = 15.0
            hold_duration = "1-5 დღე"
        elif tier == "MEME":
            profit_target = 30.0
            hold_duration = "საათები - 2 დღე"
        elif tier == "NARRATIVE":
            profit_target = 20.0
            hold_duration = "1-4 დღე"
        else:
            profit_target = 15.0
            hold_duration = "1-5 დღე"

        # ════════════════════════════════════════════════════════
        # 7. REASONING CONSTRUCTION
        # ════════════════════════════════════════════════════════

        primary_reason = (
            f"{symbol} სპონტანურ მოვლენაში იმყოფება. "
            f"{spontaneous_reason}"
        )

        supporting_reasons = []

        if is_breakout:
            supporting_reasons.append("გარღვევა შეკუმშვიდან")

        if is_extreme_oversold:
            supporting_reasons.append(f"ექსტრემალური გადაყიდვა (RSI: {rsi:.1f})")

        if regime_analysis.volatility_percentile > 75:
            supporting_reasons.append(
                f"მკვეთრი ვოლატილობის ზრდა "
                f"({regime_analysis.volatility_percentile:.0f} პერცენტილი)"
            )

        supporting_reasons.extend(regime_analysis.reasoning)

        risk_factors = [
            "⚠️ სპონტანური მოვლენა - არაპროგნოზირებადი",
            "💨 სიტუაცია სწრაფად იცვლება"
        ]

        risk_factors.extend(regime_analysis.warning_flags)

        # ════════════════════════════════════════════════════════
        # 8. RISK ASSESSMENT
        # ════════════════════════════════════════════════════════

        # ოპორტუნისტული ყოველთვის HIGH რისკია
        risk_level = self._assess_risk_level(
            volatility_percentile=regime_analysis.volatility_percentile,
            is_structural=False,  # არასტრუქტურული
            warning_count=len(regime_analysis.warning_flags)
        )

        # Override minimum to HIGH
        if risk_level == "LOW" or risk_level == "MEDIUM":
            risk_level = "HIGH"

        # ════════════════════════════════════════════════════════
        # 9. SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.OPPORTUNISTIC,
            entry_price=price,
            target_price=price * (1 + profit_target / 100),
            stop_loss_price=price * 0.92,  # -8% stop-loss
            expected_hold_duration=hold_duration,
            entry_timestamp=datetime.now().isoformat(),
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            risk_level=risk_level,
            primary_reason=primary_reason,
            supporting_reasons=supporting_reasons,
            risk_factors=risk_factors,
            expected_profit_min=profit_target * 0.5,
            expected_profit_max=profit_target,
            market_regime=regime_analysis.regime.value,
            requires_sell_notification=True  # სპონტანური → კი
        )

        return signal

    def should_send_signal(
        self,
        symbol: str,
        signal: TradingSignal
    ) -> tuple[bool, str]:
        """
        უნდა გაიგზავნოს სიგნალი?
        """

        # Confidence threshold
        if signal.confidence_score < 55:
            return False, f"confidence ძალიან დაბალია ({signal.confidence_score:.0f}%)"

        # Update tracking
        self.last_signal_time[symbol] = datetime.now()

        week = datetime.now().isocalendar()[1]  # ISO week number
        if symbol not in self.weekly_signal_count:
            self.weekly_signal_count[symbol] = {}

        if week not in self.weekly_signal_count[symbol]:
            self.weekly_signal_count[symbol][week] = 0

        self.weekly_signal_count[symbol][week] += 1

        return True, "ოპორტუნისტული შესაძლებლობა იდენტიფიცირებულია"

    # ════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ════════════════════════════════════════════════════════════

    def _check_cooldown(self, symbol: str) -> bool:
        """Cooldown შემოწმება (3 დღე)"""
        if symbol not in self.last_signal_time:
            return True

        last_time = self.last_signal_time[symbol]
        hours_since = (datetime.now() - last_time).total_seconds() / 3600

        if hours_since < self.cooldown_hours:
            logger.debug(
                f"[OPPORTUNISTIC] {symbol} cooldown ({hours_since:.1f}h / "
                f"{self.cooldown_hours}h)"
            )
            return False

        return True

    def _check_weekly_limit(self, symbol: str) -> bool:
        """კვირეული ლიმიტის შემოწმება (მაქს 1)"""
        week = datetime.now().isocalendar()[1]

        if symbol not in self.weekly_signal_count:
            return True

        if week not in self.weekly_signal_count[symbol]:
            return True

        count = self.weekly_signal_count[symbol][week]

        if count >= 1:
            logger.debug(
                f"[OPPORTUNISTIC] {symbol} კვირეული ლიმიტი მიღწეულია"
            )
            return False

        return True

    def _detect_breakout(
        self,
        price: float,
        bb_low: float,
        bb_high: float
    ) -> bool:
        """
        გარღვევის დეტექცია
        """
        bb_range = bb_high - bb_low

        # ფასი ბოლინჯერის ზოლებს გარეთაა?
        is_below = price < bb_low * 0.98
        is_above = price > bb_high * 1.02

        return is_below or is_above

    def _identify_spontaneous_reason(
        self,
        is_breakout: bool,
        is_spontaneous_move: bool,
        is_extreme_oversold: bool,
        regime_analysis
    ) -> str:
        """
        სპონტანურობის მიზეზის იდენტიფიცირება
        """

        if is_breakout:
            return "ფასი გარღვევის რეჟიმში შევიდა - კონსოლიდაციიდან გამოსვლა."

        elif is_extreme_oversold:
            return "ექსტრემალური გადაყიდვა - პანიკური bounce-ის პოტენციალი."

        elif is_spontaneous_move:
            return "არასტანდარტული ბაზრის მოძრაობა - ახალი იმპულსი."

        else:
            return "მაღალი ვოლატილობის სპონტანური ზრდა."