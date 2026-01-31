"""
Scalping Strategy - Realistic Edition
✅ 5-10% მოგების სწრაფი დაჭერა
✅ უფრო რბილი Entry პირობები
✅ Per-symbol cooldown (არა გლობალური!)
✅ 30 წუთიანი hold → ავტომატური exit
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
    სკალპინგის სტრატეგია - რეალისტური ვერსია

    🎯 მიზანი: 5-10% სწრაფი მოგება 30 წუთში

    📊 Entry Criteria (უფრო რბილი):
    1. RSI < 40 (არა 35!)
    2. ფასი BB-ის ქვედა 50%-ში (არა მხოლოდ ძალიან ქვევით)
    3. ვოლატილობა მაღალია (50+ პერცენტილი)

    ⏱️ Cooldown Logic:
    - თითოეულ კრიპტოზე ცალკე tracking
    - გაიყიდა → ახალი BUY შესაძლებელია
    - არ გაიყიდა → არა ახალი BUY იმავე კრიპტოზე
    """

    def __init__(self):
        super().__init__(
            name="ScalpingStrategy",
            strategy_type=StrategyType.SCALPING
        )

        # ════════════════════════════════════════════════════════
        # PER-SYMBOL TRACKING
        # ════════════════════════════════════════════════════════

        # აქტიური scalping პოზიციები
        self.active_scalp_positions = set()  # {symbol1, symbol2, ...}

        # ბოლო სიგნალის დრო (backup tracking)
        self.last_signal_time = {}  # symbol → datetime

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

        ✅ უფრო რბილი პირობები - იშვიათად არ არის!
        """

        # ════════════════════════════════════════════════════════
        # 1. PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════

        # ✅ აქვს თუ არა უკვე აქტიური scalp პოზიცია?
        if symbol in self.active_scalp_positions:
            logger.debug(
                f"[SCALPING] {symbol} უკვე აქვს აქტიური პოზიცია - "
                f"ველოდებით exit-ს (30წთ)"
            )
            return None

        # ✅ არის თუ არა existing position?
        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                self.active_scalp_positions.add(symbol)
                logger.debug(f"[SCALPING] {symbol} existing position detected")
                return None

        # ════════════════════════════════════════════════════════
        # 2. REGIME VALIDATION - უფრო რბილი!
        # ════════════════════════════════════════════════════════

        # ✅ CHANGED: არა მხოლოდ "is_favorable_for_scalping"
        # სკალპინგი შესაძლებელია როცა ვოლატილობა 50%+ არის

        if regime_analysis.volatility_percentile < 50:
            logger.debug(
                f"[SCALPING] {symbol} ვოლატილობა ძალიან დაბალია: "
                f"{regime_analysis.volatility_percentile:.0f}%"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 3. TECHNICAL VALIDATION - უფრო რბილი!
        # ════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        ema200 = technical_data.get('ema200', price)
        bb_low = technical_data.get('bb_low', price)
        bb_high = technical_data.get('bb_high', price)

        # ✅ CHANGED: RSI < 40 (იყო 35!)
        if rsi > 40:
            logger.debug(
                f"[SCALPING] {symbol} RSI ძალიან მაღალია: {rsi:.1f} "
                f"(მაქს. 40)"
            )
            return None

        # ✅ CHANGED: ფასი BB-ის ქვედა 50%-ში (არა მხოლოდ ძალიან ქვევით!)
        bb_range = bb_high - bb_low
        bb_position = (price - bb_low) / bb_range if bb_range > 0 else 0.5

        if bb_position > 0.5:  # ზედა ნახევარში არის
            logger.debug(
                f"[SCALPING] {symbol} ფასი BB-ის ზედა ნახევარშია "
                f"({bb_position*100:.0f}%)"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 4. PROFIT TARGET - 5-10% რეალისტური!
        # ════════════════════════════════════════════════════════

        if tier == "BLUE_CHIP":
            profit_target = 5.0  # 5%
            hold_time = "20-30 წუთი"
        elif tier == "HIGH_GROWTH":
            profit_target = 7.0  # 7%
            hold_time = "15-30 წუთი"
        elif tier == "MEME":
            profit_target = 10.0  # 10%
            hold_time = "10-20 წუთი"
        elif tier == "NARRATIVE":
            profit_target = 8.0  # 8%
            hold_time = "15-25 წუთი"
        else:
            profit_target = 7.0
            hold_time = "15-30 წუთი"

        # ════════════════════════════════════════════════════════
        # 5. CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════

        technical_score = 0

        # RSI scoring (რბილი)
        if rsi < 25:
            technical_score += 50
        elif rsi < 30:
            technical_score += 40
        elif rsi < 35:
            technical_score += 30
        elif rsi < 40:
            technical_score += 20

        # BB position
        if bb_position < 0.2:  # ძალიან ქვევით
            technical_score += 40
        elif bb_position < 0.35:
            technical_score += 30
        elif bb_position < 0.5:
            technical_score += 20

        # Volatility boost
        if regime_analysis.volatility_percentile > 70:
            technical_score += 15
        elif regime_analysis.volatility_percentile > 50:
            technical_score += 10

        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_alignment=technical_score,
            structural_confidence=60  # სკალპინგი - საშუალო
        )

        # ✅ CHANGED: Confidence threshold 55% (იყო 65!)
        if confidence_score < 55:
            logger.debug(
                f"[SCALPING] {symbol} confidence დაბალია: "
                f"{confidence_score:.0f}% (მინ. 55%)"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 6. REASONING CONSTRUCTION
        # ════════════════════════════════════════════════════════

        primary_reason = (
            f"{symbol} მაღალ ვოლატილობაშია და დროებით oversold ზონაში. "
            f"სწრაფი bounce-ის პოტენციალი 5-10% მოგებისთვის."
        )

        supporting_reasons = []

        if rsi < 30:
            supporting_reasons.append(f"🔵 გადაყიდულია (RSI: {rsi:.1f})")
        elif rsi < 40:
            supporting_reasons.append(f"🔵 დროებით oversold (RSI: {rsi:.1f})")

        if bb_position < 0.35:
            supporting_reasons.append(
                f"📉 ბოლინჯერის ქვედა ზონაში ({bb_position*100:.0f}%)"
            )

        supporting_reasons.append(
            f"⚡ მაღალი ვოლატილობა "
            f"({regime_analysis.volatility_percentile:.0f} პერცენტილი)"
        )

        risk_factors = [
            "⚠️ სკალპინგი - სწრაფი exit საჭიროა (30 წუთი)",
            "💨 მაღალი რისკი, მაღალი მოგება"
        ]

        for warning in regime_analysis.warning_flags[:2]:
            risk_factors.append(f"⚠️ {warning}")

        # ════════════════════════════════════════════════════════
        # 7. RISK ASSESSMENT
        # ════════════════════════════════════════════════════════

        if regime_analysis.volatility_percentile > 85:
            risk_level = "EXTREME"
        elif regime_analysis.volatility_percentile > 65:
            risk_level = "HIGH"
        else:
            risk_level = "MEDIUM"

        # ════════════════════════════════════════════════════════
        # 8. SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.SCALPING,
            entry_price=price,
            target_price=price * (1 + profit_target / 100),
            stop_loss_price=price * 0.95,  # -5% stop-loss (უფრო რბილი)
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
            requires_sell_notification=True  # ✅ სწრაფი exit!
        )

        return signal

    def should_send_signal(
        self,
        symbol: str,
        signal: TradingSignal
    ) -> tuple[bool, str]:
        """
        უნდა გაიგზავნოს სიგნალი?

        ✅ უფრო რბილი validation
        """

        # ✅ Confidence threshold 55% (იყო 65!)
        if signal.confidence_score < 55:
            return False, f"confidence დაბალია ({signal.confidence_score:.0f}% < 55%)"

        # ✅ Extreme risk block (მხოლოდ ექსტრემალური)
        if signal.risk_level == "EXTREME" and signal.confidence_score < 65:
            return False, "EXTREME რისკი დაბალი confidence-ით"

        # ✅ Double-check active position
        if symbol in self.active_scalp_positions:
            return False, "აქტიური scalp პოზიცია უკვე არსებობს"

        # ✅ Mark as active
        self.active_scalp_positions.add(symbol)
        self.last_signal_time[symbol] = datetime.now()

        logger.info(
            f"[SCALPING] ✅ {symbol} დაემატა active scalp positions-ში. "
            f"Auto-exit: 30 წუთში"
        )

        return True, "სკალპინგის პირობები დაკმაყოფილებულია"

    # ════════════════════════════════════════════════════════════
    # ✅ NEW: POSITION CLEANUP
    # ════════════════════════════════════════════════════════════

    def mark_position_closed(self, symbol: str):
        """
        გამოძახება როცა scalp პოზიცია იხურება

        ✅ ახლა ახალი BUY შესაძლებელია
        """
        if symbol in self.active_scalp_positions:
            self.active_scalp_positions.remove(symbol)
            logger.info(
                f"[SCALPING] ✅ {symbol} scalp პოზიცია დახურულია. "
                f"ახალი BUY შესაძლებელია."
            )

    def clear_position(self, symbol: str):
        """Alias for mark_position_closed"""
        self.mark_position_closed(symbol)

    def get_active_positions(self) -> set:
        """აქტიური scalp პოზიციების სია"""
        return self.active_scalp_positions.copy()