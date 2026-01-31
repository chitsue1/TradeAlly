import logging
from .base_strategy import BaseStrategy, StrategyType

logger = logging.getLogger(__name__)

class OpportunisticStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__("Opportunistic", StrategyType.OPPORTUNISTIC)

    async def analyze(self, symbol, price, regime_analysis, technical_data, tier, existing_position):
        return None

    def should_send_signal(self, symbol, signal):
        if signal.confidence_score < 50:
            return False, "Low confidence"
        return True, "Valid signal"
