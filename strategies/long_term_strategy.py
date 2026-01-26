import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class LongTermStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__("Long-Term", config)

    async def analyze(self, symbol, data, sentiment, regime):
        score = 0
        reasons = []

        # RSI Check
        if data['rsi'] < 30:
            score += 40
            reasons.append(f"📉 Oversold (RSI: {data['rsi']:.1f})")
        
        # EMA Check
        if data['price'] > data['ema200']:
            score += 20
            reasons.append("📈 Bullish Trend (Above EMA200)")
            
        # Bollinger Check
        if data['price'] <= data['bb_low']:
            score += 25
            reasons.append("🎯 At lower Bollinger Band")

        # Sentiment Check
        if sentiment['fg_index'] < 30:
            score += 15
            reasons.append("😱 Market Fear")

        return score, reasons
