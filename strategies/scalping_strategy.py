"""
Scalping Strategy
✅ წუთები → საათები
✅ მაღალი ლიკვიდურობა + მოცულობის ზრდა
✅ სწრაფი მოგება, სწრაფი გასვლა
"""

import logging
from typing import Optional, Dict
from datetime import datetime

from .base_strategy import (
    BaseStrategy, TradingSignal, StrategyType,
    ConfidenceLevel, ActionType
)

logger = logging.getLogger(__name__)

class ScalpingStrategy(BaseStrategy):
    """
    სკალპინგის სტრატეგია

    მიზანი: 0.5% - 2.5% მოგება მოკლე დროში

    რა არის "სკალპინგის შესაძლებლობა":
    1. მაღალი ვოლატილობა
    2. მკვეთრი იმპულსი
    3. მოკლევადიანი ჰაიპი
    4. გარღვევის მომენტი

    ⚠️ CRITICAL: სკალპინგი ყოველთვის მოითხოვს გაყიდვის შეტყობინებას!
    """

    def __init__(self):
        super().__init__(
            name="ScalpingStrategy",
            strategy_type=StrategyType.SCALPING
        )

        # Very short cooldown (30 minutes)
        self.last_signal_time = {}
        self.cooldown_minutes = 30

        # Scalping არის high-frequency → მაქსიმუმ 3 სიგნალი დღეში per asset
        self.daily_signal_count = {}
        self.max_daily_signals = 3

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
        სკალპინგის შესაძლებლობის ანალიზი
        """

        # ════════════════════════════════════════════════════════
        # 1. PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════

        # Cooldown + Daily limit
        if not self._check_cooldown(symbol):
            return None

        if not self._check_daily_limit(symbol):
            return None

        # ════════════════════════════════════════════════════════
        # 2. REGIME VALIDATION
        # ════════════════════════════════════════════════════════

        # სკალპინგი შესაძლებელია მაღალ ვოლატილობაში
        if not regime_analysis.is_favorable_for_scalping():
            logger.debug(
                f"[SCALPING] {symbol} არაღელსაყრელი რეჟიმი: "
                f"{regime_analysis.regime.value}"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 3. TECHNICAL VALIDATION
        # ════════════════════════════════════════════════════════

        rsi = technical_data['rsi']
        ema200 = technical_data['ema200']
        bb_low = technical_data['bb_low']
        bb_high = technical_data['bb_high']

        # სკალპინგის პირობები:
        # 1. RSI < 35 (მძლავრი გადაყიდვა)
        # 2. ფასი ბოლინჯერის ძალიან ქვედა ზონაში
        # 3. მაღალი ვოლატილობა (უკვე რეჟიმში შემოწმებული)

        if rsi > 35:
            logger.debug(f"[SCALPING] {symbol} RSI არ არის საკმარისად დაბალი: {rsi:.1f}")
            return None

        # ფასი უნდა იყოს BB low-ს ძალიან ახლოს (oversold bounce)
        if price > bb_low * 1.03:
            logger.debug(f"[SCALPING] {symbol} არ არის BB low-ს ახლოს")
            return None

        # ════════════════════════════════════════════════════════
        # 4. PROFIT TARGET CALCULATION
        # ════════════════════════════════════════════════════════

        # სკალპინგი: 0.5% - 2.5% მოგება
        # Tier-ის მიხედვით:
        if tier == "BLUE_CHIP":
            profit_target = 1.0  # 1%
            hold_time = "30-60 წუთი"
        elif tier == "HIGH_GROWTH":
            profit_target = 1.5  # 1.5%
            hold_time = "20-45 წუთი"
        elif tier == "MEME":
            profit_target = 2.5  # 2.5%
            hold_time = "15-30 წუთი"
        else:
            profit_target = 1.5
            hold_time = "20-45 წუთი"

        # ════════════════════════════════════════════════════════
        # 5. CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════

        technical_score = 0

        if rsi < 25:
            technical_score += 50
        elif rsi < 30:
            technical_score += 35

        if price <= bb_low:
            technical_score += 40
        elif price <= bb_low * 1.02:
            technical_score += 25

        if regime_analysis.volatility_percentile > 80:
            technical_score += 10

        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_alignment=technical_score,
            structural_confidence=70  # სკალპინგი არ საჭიროებს სტრუქტურულობას
        )

        # Minimum confidence threshold (სკალპინგი უფრო რისკიანია)
        if confidence_score < 65:
            logger.debug(
                f"[SCALPING] {symbol} confidence ძალიან დაბალია: "
                f"{confidence_score:.0f}%"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 6. REASONING CONSTRUCTION
        # ════════════════════════════════════════════════════════

        primary_reason = (
            f"{symbol} მაღალ ვოლატილობაში იმყოფება და "
            f"გადაყიდულ ზონაშია. სწრაფი bounce-ის მაღალი ალბათობა."
        )

        supporting_reasons = [
            f"ძლიერი გადაყიდვა (RSI: {rsi:.1f})",
            f"ბოლინჯერის ქვედა ზოლთან",
            f"მაღალი ვოლატილობა ({regime_analysis.volatility_percentile:.0f} პერცენტილი)"
        ]

        risk_factors = [
            "⚠️ სკალპინგი არის მაღალი რისკი - სწრაფი გადაწყვეტილებები",
            "💨 პოზიცია არ უნდა დარჩეს ღია დიდხანს"
        ]

        for warning in regime_analysis.warning_flags:
            risk_factors.append(warning)

        # ════════════════════════════════════════════════════════
        # 7. RISK ASSESSMENT
        # ════════════════════════════════════════════════════════

        # სკალპინგი ყოველთვის HIGH ან EXTREME რისკია
        if regime_analysis.volatility_percentile > 90:
            risk_level = "EXTREME"
        else:
            risk_level = "HIGH"

        # ════════════════════════════════════════════════════════
        # 8. SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.SCALPING,
            entry_price=price,
            target_price=price * (1 + profit_target / 100),
            stop_loss_price=price * 0.97,  # -3% tight stop-loss
            expected_hold_duration=hold_time,
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
            requires_sell_notification=True  # ✅ CRITICAL!
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

        # Confidence threshold (უფრო მკაცრი)
        if signal.confidence_score < 65:
            return False, f"confidence ძალიან დაბალია ({signal.confidence_score:.0f}%)"

        # Update tracking
        self.last_signal_time[symbol] = datetime.now()

        today = datetime.now().date()
        if symbol not in self.daily_signal_count:
            self.daily_signal_count[symbol] = {}

        if today not in self.daily_signal_count[symbol]:
            self.daily_signal_count[symbol][today] = 0

        self.daily_signal_count[symbol][today] += 1

        return True, "სკალპინგის პირობები დაკმაყოფილებულია"

    # ════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ════════════════════════════════════════════════════════════

    def _check_cooldown(self, symbol: str) -> bool:
        """Cooldown შემოწმება (30 წუთი)"""
        if symbol not in self.last_signal_time:
            return True

        last_time = self.last_signal_time[symbol]
        minutes_since = (datetime.now() - last_time).total_seconds() / 60

        if minutes_since < self.cooldown_minutes:
            logger.debug(
                f"[SCALPING] {symbol} cooldown ({minutes_since:.1f}min / "
                f"{self.cooldown_minutes}min)"
            )
            return False

        return True

    def _check_daily_limit(self, symbol: str) -> bool:
        """დღიური ლიმიტის შემოწმება (მაქს 3)"""
        today = datetime.now().date()

        if symbol not in self.daily_signal_count:
            return True

        if today not in self.daily_signal_count[symbol]:
            return True

        count = self.daily_signal_count[symbol][today]

        if count >= self.max_daily_signals:
            logger.debug(
                f"[SCALPING] {symbol} დღიური ლიმიტი მიღწეულია "
                f"({count}/{self.max_daily_signals})"
            )
            return False

        return True