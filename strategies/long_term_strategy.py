"""
Long-Term Investment Strategy
✅ კვირები → თვეები → წლები
✅ სტრუქტურული ტრენდების იდენტიფიცირება
✅ არა სპამი - მხოლოდ რეალური შესაძლებლობები
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

# მნიშვნელოვანია: base_strategy-ში უნდა გქონდეს ყველა ეს Enum
from .base_strategy import (
    BaseStrategy, 
    TradingSignal, 
    StrategyType, 
    ConfidenceLevel, 
    ActionType
)

logger = logging.getLogger(__name__)

class LongTermStrategy(BaseStrategy):
    """
    გრძელვადიანი ინვესტიციის სტრატეგია

    მიზანი: სტაბილური, სტრუქტურული ტრენდების დაჭერა

    რა არის "გრძელვადიანი შესაძლებლობა":
    1. სტრუქტურული აღმავალი ტრენდი
    2. ფასი სტრატეგიულ ზონაშია
    3. არა ექსტრემალური ვოლატილობა
    4. მაღალი ალბათობა, რომ ასეთი ფასი დიდხანს არ შენარჩუნდება
    """

    def __init__(self):
        # BaseStrategy-ს გადაეცემა სახელი და ტიპი
        super().__init__(
            name="LongTermInvestment",
            strategy_type=StrategyType.LONG_TERM
        )

        # Cooldown tracking (არ გააგზავნო ხშირად)
        self.last_signal_time = {}
        self.cooldown_hours = 48  # 2 days minimum between signals

    def analyze(
        self,
        symbol: str,
        price: float,
        regime_analysis: Any,
        technical_data: Dict,
        tier: str,
        existing_position: Optional[object] = None
    ) -> Optional[TradingSignal]:
        """
        გრძელვადიანი შესაძლებლობის ანალიზი
        """

        # ════════════════════════════════════════════════════════
        # 1. PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════

        # არის თუ არა ღია პოზიცია?
        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                # გრძელვადიანი → მხოლოდ 1 შესვლა
                logger.debug(f"[LONG_TERM] {symbol} უკვე აქვს პოზიცია")
                return None

        # Cooldown check
        if not self._check_cooldown(symbol):
            return None

        # ════════════════════════════════════════════════════════
        # 2. REGIME VALIDATION
        # ════════════════════════════════════════════════════════

        # გრძელვადიანი ინვესტიცია შესაძლებელია მხოლოდ ხელსაყრელ რეჟიმში
        if not regime_analysis.is_favorable_for_long_term():
            logger.debug(
                f"[LONG_TERM] {symbol} არაღელსაყრელი რეჟიმი: "
                f"{regime_analysis.regime.value}"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 3. TECHNICAL VALIDATION
        # ════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        ema200 = technical_data.get('ema200', price)
        bb_low = technical_data.get('bb_low', price)

        # ძირითადი პირობები:
        # 1. RSI < 45 (არა გადახურებული)
        # 2. ფასი EMA200-ის ზემოთ ან ახლოს (ტრენდი აღმავალია)
        # 3. ფასი ბოლინჯერის ქვედა ნახევარშია (შედარებით იაფი)

        if rsi > 45:
            logger.debug(f"[LONG_TERM] {symbol} RSI ძალიან მაღალია: {rsi:.1f}")
            return None

        if price < ema200 * 0.95:  # 5% ქვევით მაქსიმუმ
            logger.debug(f"[LONG_TERM] {symbol} ძალიან შორსაა EMA200-დან ქვევით")
            return None

        # ════════════════════════════════════════════════════════
        # 4. TIER-BASED EXPECTATIONS
        # ════════════════════════════════════════════════════════

        tier_config = self._get_tier_config(tier)

        # ════════════════════════════════════════════════════════
        # 5. CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════

        # Technical alignment score
        technical_score = 0
        if rsi < 30:
            technical_score += 40
        elif rsi < 35:
            technical_score += 25
        elif rsi < 40:
            technical_score += 15

        if price > ema200:
            technical_score += 30
        elif price > ema200 * 0.98:
            technical_score += 20

        if price <= bb_low * 1.05:
            technical_score += 30

        # Confidence calculation - იძახებს BaseStrategy-ს მეთოდს
        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_alignment=technical_score,
            structural_confidence=100 if regime_analysis.is_structural else 40
        )

        # Minimum confidence threshold
        if confidence_score < 60:
            logger.debug(
                f"[LONG_TERM] {symbol} confidence ძალიან დაბალია: "
                f"{confidence_score:.0f}%"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 6. REASONING CONSTRUCTION
        # ════════════════════════════════════════════════════════

        primary_reason = self._build_primary_reason(
            symbol, regime_analysis, tier
        )

        supporting_reasons = []

        if regime_analysis.is_structural:
            supporting_reasons.append("სტრუქტურული აღმავალი ტრენდი")

        if rsi < 30:
            supporting_reasons.append(f"გადაყიდულია (RSI: {rsi:.1f})")
        elif rsi < 35:
            supporting_reasons.append(f"დაბალი RSI ({rsi:.1f})")

        if price > ema200:
            supporting_reasons.append("ფასი EMA200-ზე მაღლა (აღმავალი ტრენდი)")

        if price <= bb_low * 1.05:
            supporting_reasons.append("ბოლინჯერის ქვედა ზონაში")

        # Risk factors
        risk_factors = []

        if regime_analysis.volatility_percentile > 70:
            risk_factors.append(
                f"მაღალი ვოლატილობა ({regime_analysis.volatility_percentile:.0f} პერცენტილი)"
            )

        for warning in regime_analysis.warning_flags:
            risk_factors.append(warning)

        if not risk_factors:
            risk_factors.append("არ არის მნიშვნელოვანი რისკი")

        # ════════════════════════════════════════════════════════
        # 7. RISK ASSESSMENT
        # ════════════════════════════════════════════════════════

        risk_level = self._assess_risk_level(
            volatility_percentile=regime_analysis.volatility_percentile,
            is_structural=regime_analysis.is_structural,
            warning_count=len(regime_analysis.warning_flags)
        )

        # ════════════════════════════════════════════════════════
        # 8. SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.LONG_TERM,
            entry_price=price,
            target_price=price * (1 + tier_config['target_percent'] / 100),
            stop_loss_price=price * 0.90,  # -10% stop-loss
            expected_hold_duration=tier_config['hold_duration'],
            entry_timestamp=datetime.now().isoformat(),
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            risk_level=risk_level,
            primary_reason=primary_reason,
            supporting_reasons=supporting_reasons,
            risk_factors=risk_factors,
            expected_profit_min=tier_config['target_percent'] * 0.7,
            expected_profit_max=tier_config['target_percent'],
            market_regime=regime_analysis.regime.value,
            requires_sell_notification=False  # გრძელვადიანი → არა
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
        if signal.confidence_score < 60:
            return False, f"confidence ძალიან დაბალია ({signal.confidence_score:.0f}%)"

        # Extreme risk check
        if signal.risk_level == "EXTREME":
            return False, "ექსტრემალური რისკი - სიგნალი დაბლოკილია"

        # Update last signal time
        self.last_signal_time[symbol] = datetime.now()

        return True, "ყველა პირობა დაკმაყოფილებულია"

    # ════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ════════════════════════════════════════════════════════════

    def _check_cooldown(self, symbol: str) -> bool:
        """Cooldown შემოწმება"""
        if symbol not in self.last_signal_time:
            return True

        last_time = self.last_signal_time[symbol]
        hours_since = (datetime.now() - last_time).total_seconds() / 3600

        if hours_since < self.cooldown_hours:
            logger.debug(
                f"[LONG_TERM] {symbol} cooldown ({hours_since:.1f}h / "
                f"{self.cooldown_hours}h)"
            )
            return False

        return True

    def _get_tier_config(self, tier: str) -> Dict:
        """Tier-ის კონფიგურაცია"""
        configs = {
            "BLUE_CHIP": {
                "target_percent": 15.0,
                "hold_duration": "2-4 კვირა"
            },
            "HIGH_GROWTH": {
                "target_percent": 30.0,
                "hold_duration": "3-6 კვირა"
            },
            "MEME": {
                "target_percent": 50.0,
                "hold_duration": "1-2 კვირა"
            },
            "NARRATIVE": {
                "target_percent": 40.0,
                "hold_duration": "2-5 კვირა"
            },
            "EMERGING": {
                "target_percent": 60.0,
                "hold_duration": "3-8 კვირა"
            }
        }
        return configs.get(tier, configs["HIGH_GROWTH"])

    def _build_primary_reason(
        self,
        symbol: str,
        regime_analysis: Any,
        tier: str
    ) -> str:
        """მთავარი მიზეზის ფორმულირება"""
        reason = (
            f"{symbol} სტრუქტურულ აღმავალ ტრენდში იმყოფება "
            f"და ახლოსაა გრძელვადიან მხარდაჭერასთან. "
        )

        if tier == "BLUE_CHIP":
            reason += "Blue Chip აქტივი - სტაბილური ზრდის პოტენციალი."
        elif tier == "HIGH_GROWTH":
            reason += "High Growth აქტივი - მაღალი ზრდის პოტენციალი."
        elif tier == "MEME":
            reason += "Meme Coin - მაღალი ვოლატილობა, სწრაფი მოგების პოტენციალი."
        self.record_activity()

        return reason