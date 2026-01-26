import logging
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

class OpportunisticStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__("Opportunistic", config)

    async def analyze(self, symbol, price, regime_analysis, technical_data, tier, existing_position):
        return None
