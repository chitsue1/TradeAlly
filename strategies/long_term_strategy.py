import logging
from datetime import datetime
from .base_strategy import BaseStrategy, TradingSignal, StrategyType, ActionType, ConfidenceLevel

logger = logging.getLogger(__name__)

class LongTermStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__("Long-Term", StrategyType.LONG_TERM)

    async def analyze(self, symbol, price, regime_analysis, technical_data, tier, existing_position):
        score = 0
        reasons = []
        data = technical_data

        # RSI Check
        if data['rsi'] < 30:
            score += 40
            reasons.append(f"📉 Oversold (RSI: {data['rsi']:.1f})")
        
        # EMA Check
        if price > data['ema200']:
            score += 20
            reasons.append("📈 Bullish Trend (Above EMA200)")
            
        # Bollinger Check
        if price <= data['bb_low']:
            score += 25
            reasons.append("🎯 At lower Bollinger Band")

        if score < 50:
            return None

        # Calculate confidence
        conf_level, conf_score = self._calculate_confidence(
            regime_analysis.confidence,
            score,
            80 if regime_analysis.is_structural else 40
        )

        # Risk assessment
        risk = self._assess_risk_level(
            regime_analysis.volatility_percentile,
            regime_analysis.is_structural,
            len(regime_analysis.warning_flags)
        )

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=self.strategy_type,
            entry_price=price,
            target_price=price * 1.2,  # 20% target
            stop_loss_price=price * 0.9, # 10% stop loss
            expected_hold_duration="3-6 Months",
            entry_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            confidence_level=conf_level,
            confidence_score=conf_score,
            risk_level=risk,
            primary_reason="Long-term structural alignment",
            supporting_reasons=reasons,
            risk_factors=regime_analysis.warning_flags,
            expected_profit_min=15.0,
            expected_profit_max=40.0,
            market_regime=regime_analysis.regime.value
        )

        # Validate
        is_valid, msg = self._validate_signal(signal)
        if not is_valid:
            logger.debug(f"Signal invalidated: {msg}")
            return None

        return signal

    def should_send_signal(self, symbol, signal):
        # Basic logic: don't send if confidence is too low
        if signal.confidence_score < 50:
            return False, "Low confidence"
        return True, "Valid signal"
