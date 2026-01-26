import logging
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class TradingSignal:
    def __init__(self, symbol, entry_price, action, strategy_type, confidence_score, reasons):
        self.symbol = symbol
        self.entry_price = entry_price
        self.action = action
        self.strategy_type = strategy_type
        self.confidence_score = confidence_score
        self.reasons = reasons

    def to_message(self):
        return f"🎯 {self.action.upper()} {self.symbol}\nStrategy: {self.strategy_type}\nPrice: ${self.entry_price:.4f}\nConfidence: {self.confidence_score:.0f}%\nReasons: {', '.join(self.reasons)}"

class BaseStrategy:
    def __init__(self, name, config=None):
        self.name = name
        self.config = config or {}
        self.signals_history = []

    async def analyze(self, symbol, price, regime_analysis, technical_data, tier, existing_position):
        pass

    def should_send_signal(self, symbol, signal):
        # Basic logic: don't send if confidence is too low
        if signal.confidence_score < 50:
            return False, "Low confidence"
        return True, "Valid signal"

    def log_signal(self, signal):
        self.signals_history.append(signal)

    def get_statistics(self):
        return {"total_signals": len(self.signals_history)}
