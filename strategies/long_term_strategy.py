"""
Long-Term Investment Strategy - Professional Edition
✅ 1-3 კვირიანი პერსპექტივა (არა წლები!)
✅ Per-symbol cooldown - თითოეული კრიპტო დამოუკიდებლად
✅ გაყიდვამდე ახალი BUY არ გაიგზავნება
✅ სხვა სტრატეგიები (scalping) არ იბლოკება
✅ პროფესიონალური entry timing
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

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
    გრძელვადიანი ინვესტიციის სტრატეგია (1-3 კვირა)

    📊 ფილოსოფია:
    - არა "ყიდე და დაივიწყე 6 თვით"
    - არამედ: "კარგი Entry → დაელოდე 1-3 კვირას → მოგება"

    🎯 Entry Timing (როდის ყიდულობს):
    - სტრუქტურული აღმავალი ტრენდი
    - ფასი დროებით დაბალია (pullback/correction)
    - მაღალი ალბათობა, რომ 1-3 კვირაში გაიზრდება

    ⏱️ Cooldown Logic:
    - თითოეული კრიპტოზე **ცალ-ცალკე** cooldown
    - ერთხელ BUY → მხოლოდ SELL შემდეგ ახალი BUY
    - სხვა სტრატეგიები (scalping) არ იბლოკება
    """

    def __init__(self):
        super().__init__(
            name="LongTermInvestment",
            strategy_type=StrategyType.LONG_TERM
        )

        # ════════════════════════════════════════════════════════
        # TRACKING PER SYMBOL
        # ════════════════════════════════════════════════════════

        # BUY სიგნალის დრო (per symbol)
        self.last_buy_signal = {}  # symbol → datetime

        # Active positions (per symbol) - SELL-მდე ახალი BUY არა
        self.active_long_positions = set()  # {symbol1, symbol2, ...}

        # ✅ Minimum cooldown between signals (დაცვა spam-ისგან)
        self.min_cooldown_hours = 24  # მინიმუმ 24 საათი იგივე კრიპტოზე

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

        🎯 Entry Criteria:
        1. სტრუქტურული აღმავალი ტრენდი (bull regime)
        2. RSI < 45 (დროებითი oversold)
        3. ფასი EMA200-ის ახლოს ან მაღლა
        4. ბოლინჯერის ქვედა ზონაში (კორექციაში)
        """

        # ════════════════════════════════════════════════════════
        # 1. PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════

        # ✅ CHECK 1: არის თუ არა უკვე აქტიური long პოზიცია?
        if symbol in self.active_long_positions:
            logger.debug(
                f"[LONG_TERM] {symbol} უკვე აქვს აქტიური პოზიცია - "
                f"ველოდებით SELL-ს"
            )
            return None

        # ✅ CHECK 2: არის თუ არა existing position trading_engine-იდან?
        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                # თუ უკვე გაგზავნილია BUY, ახალი არ გაიგზავნოს
                self.active_long_positions.add(symbol)
                logger.debug(f"[LONG_TERM] {symbol} existing position detected")
                return None

        # ✅ CHECK 3: Minimum cooldown (anti-spam protection)
        if not self._check_minimum_cooldown(symbol):
            return None

        # ════════════════════════════════════════════════════════
        # 2. REGIME VALIDATION - Bull Market ხელსაყრელია
        # ════════════════════════════════════════════════════════

        if not regime_analysis.is_favorable_for_long_term():
            logger.debug(
                f"[LONG_TERM] {symbol} არახელსაყრელი რეჟიმი: "
                f"{regime_analysis.regime.value}"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 3. TECHNICAL VALIDATION - Entry Timing
        # ════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        ema200 = technical_data.get('ema200', price)
        bb_low = technical_data.get('bb_low', price)
        bb_high = technical_data.get('bb_high', price)

        # ✅ Entry Conditions (პროფესიონალური timing):

        # 1. RSI არ უნდა იყოს გადახურებული
        if rsi > 45:
            logger.debug(
                f"[LONG_TERM] {symbol} RSI ძალიან მაღალია: {rsi:.1f} "
                f"(ველოდებით pullback-ს)"
            )
            return None

        # 2. ფასი EMA200-ის ზემოთ ან ძალიან ახლოს (ტრენდი აღმავალია)
        distance_from_ema = (price - ema200) / ema200

        if distance_from_ema < -0.05:  # 5%-ზე მეტი ქვევით
            logger.debug(
                f"[LONG_TERM] {symbol} ძალიან შორსაა EMA200-დან ქვევით "
                f"({distance_from_ema*100:.1f}%)"
            )
            return None

        # 3. ფასი Bollinger-ის ქვედა ნახევარში (pullback)
        bb_range = bb_high - bb_low
        bb_position = (price - bb_low) / bb_range if bb_range > 0 else 0.5

        if bb_position > 0.6:  # ზედა 40%-ში არის
            logger.debug(
                f"[LONG_TERM] {symbol} ფასი ძალიან მაღალია BB-ში "
                f"(position: {bb_position*100:.0f}%) - ველოდებით pullback-ს"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 4. TIER-BASED CONFIGURATION (1-3 კვირიანი)
        # ════════════════════════════════════════════════════════

        tier_config = self._get_tier_config(tier)

        # ════════════════════════════════════════════════════════
        # 5. CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════

        technical_score = 0

        # RSI scoring (რაც უფრო oversold - მით უკეთესია)
        if rsi < 25:
            technical_score += 50
        elif rsi < 30:
            technical_score += 40
        elif rsi < 35:
            technical_score += 30
        elif rsi < 40:
            technical_score += 20
        elif rsi < 45:
            technical_score += 10

        # EMA200 position (ტრენდის მიმართულება)
        if distance_from_ema > 0.05:  # 5%+ მაღლა
            technical_score += 30
        elif distance_from_ema > 0:  # მაღლა
            technical_score += 25
        elif distance_from_ema > -0.02:  # ახლოს
            technical_score += 15

        # Bollinger position (pullback-ის სიღრმე)
        if bb_position < 0.2:  # ძალიან ქვევით
            technical_score += 30
        elif bb_position < 0.4:  # ქვედა ნახევარში
            technical_score += 20

        # Confidence calculation
        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_alignment=technical_score,
            structural_confidence=100 if regime_analysis.is_structural else 40
        )

        # ✅ Minimum confidence threshold (70% - მაღალი სტანდარტი)
        if confidence_score < 70:
            logger.debug(
                f"[LONG_TERM] {symbol} confidence არასაკმარისია: "
                f"{confidence_score:.0f}% (მინ. 70%)"
            )
            return None

        # ════════════════════════════════════════════════════════
        # 6. REASONING CONSTRUCTION
        # ════════════════════════════════════════════════════════

        primary_reason = self._build_primary_reason(
            symbol, regime_analysis, tier, rsi, distance_from_ema
        )

        supporting_reasons = []

        if regime_analysis.is_structural:
            supporting_reasons.append("📈 სტრუქტურული აღმავალი ტრენდი")

        if rsi < 30:
            supporting_reasons.append(f"🔵 ძლიერი გადაყიდვა (RSI: {rsi:.1f})")
        elif rsi < 40:
            supporting_reasons.append(f"🔵 დროებითი oversold (RSI: {rsi:.1f})")

        if distance_from_ema > 0:
            supporting_reasons.append(
                f"✅ ფასი EMA200-ზე მაღლა ({distance_from_ema*100:+.1f}%) - "
                f"აღმავალი ტრენდი"
            )
        else:
            supporting_reasons.append(
                f"⚖️ ფასი EMA200-ის ახლოსაა ({distance_from_ema*100:+.1f}%)"
            )

        if bb_position < 0.4:
            supporting_reasons.append(
                f"📉 ბოლინჯერის ქვედა ზონაში (pullback/correction)"
            )

        # Risk factors
        risk_factors = []

        if regime_analysis.volatility_percentile > 70:
            risk_factors.append(
                f"⚠️ მაღალი ვოლატილობა "
                f"({regime_analysis.volatility_percentile:.0f} პერცენტილი)"
            )

        for warning in regime_analysis.warning_flags:
            risk_factors.append(f"⚠️ {warning}")

        if not risk_factors:
            risk_factors.append("✅ რისკი კონტროლირებადია")

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
            stop_loss_price=price * 0.92,  # -8% stop-loss (კონსერვატიული)
            expected_hold_duration=tier_config['hold_duration'],
            entry_timestamp=datetime.now().isoformat(),
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            risk_level=risk_level,
            primary_reason=primary_reason,
            supporting_reasons=supporting_reasons,
            risk_factors=risk_factors,
            expected_profit_min=tier_config['target_percent'] * 0.6,
            expected_profit_max=tier_config['target_percent'],
            market_regime=regime_analysis.regime.value,
            requires_sell_notification=True  # ✅ SELL შეტყობინება საჭიროა!
        )

        return signal

    def should_send_signal(
        self,
        symbol: str,
        signal: TradingSignal
    ) -> tuple[bool, str]:
        """
        უნდა გაიგზავნოს სიგნალი?

        ✅ Final validation before sending
        """

        # ✅ 1. Confidence threshold (70%+)
        if signal.confidence_score < 60:
            return False, f"confidence არასაკმარისია ({signal.confidence_score:.0f}% < 60%)"

        # ✅ 2. Extreme risk block
        if signal.risk_level == "EXTREME":
            return False, "EXTREME რისკი - სიგნალი დაბლოკილია"

        # ✅ 3. Double-check active position
        if symbol in self.active_long_positions:
            return False, "აქტიური პოზიცია უკვე არსებობს"

        # ✅ 4. Mark as active position (მხოლოდ აქ!)
        self.active_long_positions.add(symbol)
        self.last_buy_signal[symbol] = datetime.now()

        logger.info(
            f"[LONG_TERM] ✅ {symbol} დაემატა active positions-ში. "
            f"შემდეგი BUY მხოლოდ SELL-ის შემდეგ."
        )

        return True, "ყველა პირობა დაკმაყოფილებულია"

    # ════════════════════════════════════════════════════════════
    # ✅ NEW: SELL NOTIFICATION HANDLER
    # ════════════════════════════════════════════════════════════

    def mark_position_closed(self, symbol: str):
        """
        გამოძახება როცა პოზიცია იხურება (target/stop hit)

        ✅ ახლა ახალი BUY შესაძლებელია
        """
        if symbol in self.active_long_positions:
            self.active_long_positions.remove(symbol)
            logger.info(
                f"[LONG_TERM] ✅ {symbol} პოზიცია დახურულია. "
                f"ახალი BUY შესაძლებელია."
            )

    # ════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ════════════════════════════════════════════════════════════

    def _check_minimum_cooldown(self, symbol: str) -> bool:
        """
        Minimum cooldown - anti-spam protection

        ✅ მინიმუმ 24 საათი უნდა გაიაროს იგივე კრიპტოზე BUY-ებს შორის
        """
        if symbol not in self.last_buy_signal:
            return True

        last_time = self.last_buy_signal[symbol]
        hours_since = (datetime.now() - last_time).total_seconds() / 3600

        if hours_since < self.min_cooldown_hours:
            logger.debug(
                f"[LONG_TERM] {symbol} minimum cooldown active "
                f"({hours_since:.1f}h / {self.min_cooldown_hours}h)"
            )
            return False

        return True

    def _get_tier_config(self, tier: str) -> Dict:
        """
        Tier-ის კონფიგურაცია (1-3 კვირიანი პერსპექტივა)

        ✅ რეალისტური timeframes - არა წლები!
        """
        configs = {
            "BLUE_CHIP": {
                "target_percent": 12.0,      # +12%
                "hold_duration": "2-3 კვირა"
            },
            "HIGH_GROWTH": {
                "target_percent": 20.0,      # +20%
                "hold_duration": "1-3 კვირა"
            },
            "MEME": {
                "target_percent": 35.0,      # +35%
                "hold_duration": "1-2 კვირა"
            },
            "NARRATIVE": {
                "target_percent": 25.0,      # +25%
                "hold_duration": "1-3 კვირა"
            },
            "EMERGING": {
                "target_percent": 30.0,      # +30%
                "hold_duration": "2-3 კვირა"
            }
        }
        return configs.get(tier, configs["HIGH_GROWTH"])

    def _build_primary_reason(
        self,
        symbol: str,
        regime_analysis: Any,
        tier: str,
        rsi: float,
        distance_from_ema: float
    ) -> str:
        """
        მთავარი მიზეზის ფორმულირება

        ✅ კონტექსტური, დეტალური ახსნა
        """

        # Base reason
        reason = f"{symbol} "

        # Regime context
        if regime_analysis.is_structural:
            reason += "სტრუქტურულ აღმავალ ტრენდშია"
        else:
            reason += "აღმავალი მოძრაობის პოტენციალი აქვს"

        # Current situation
        if rsi < 30:
            reason += " და ამჟამად ძლიერ გადაყიდულია"
        elif rsi < 40:
            reason += " და ამჟამად დროებით oversold-ია"
        else:
            reason += " და ამჟამად pullback-ში იმყოფება"

        # Entry timing
        reason += ". "

        if distance_from_ema > 0.03:
            reason += "ფასი EMA200-ზე მაღლა მოძრაობს (+trend), "
        elif distance_from_ema > -0.02:
            reason += "ფასი EMA200-ს ახლოსაა (support zone), "

        reason += "რაც კარგ entry point-ს წარმოადგენს 1-3 კვირიანი პერსპექტივისთვის."

        # Tier context
        if tier == "BLUE_CHIP":
            reason += " (Blue Chip - სტაბილური)"
        elif tier == "HIGH_GROWTH":
            reason += " (High Growth - მაღალი პოტენციალი)"
        elif tier == "MEME":
            reason += " (Meme - მაღალი ვოლატილობა)"
        elif tier == "NARRATIVE":
            reason += " (Narrative - ტრენდზე მყოფი)"
        elif tier == "EMERGING":
            reason += " (Emerging - ახალი ზრდის ფაზა)"

        # Record activity
        self.record_activity()

        return reason

    # ════════════════════════════════════════════════════════════
    # ✅ PUBLIC API for external usage
    # ════════════════════════════════════════════════════════════

    def get_active_positions(self) -> set:
        """აქტიური long პოზიციების სია"""
        return self.active_long_positions.copy()

    def clear_position(self, symbol: str):
        """Alias for mark_position_closed"""
        self.mark_position_closed(symbol)