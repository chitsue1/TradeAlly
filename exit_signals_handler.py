"""
═══════════════════════════════════════════════════════════════════════════════
EXIT SIGNALS HANDLER - PRODUCTION v1.0
═══════════════════════════════════════════════════════════════════════════════

🎯 სიზუსტე:
✅ რეალ-დროში position monitoring
✅ Target/Stop Loss დეტექცია
✅ Profit/Loss გაანგარიშება
✅ Performance Analytics
✅ 100$ ეკვივალენტი რეპორტი

AUTHOR: Trading System Architecture Team
DATE: 2024-02-14
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from dataclasses import dataclass
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════

class ExitReason(Enum):
    """გაყიდვის მიზეზი"""
    TARGET_HIT = "target_hit"
    STOP_LOSS = "stop_loss"
    TIMEOUT = "timeout"
    MANUAL = "manual"
    PARTIAL_EXIT = "partial_exit"

class ExitSignalType(Enum):
    """გაყიდვის ტიპი"""
    FULL_EXIT = "full_exit"
    PARTIAL_EXIT = "partial_exit"
    TAKE_PROFIT = "take_profit"

@dataclass
class ExitAnalysis:
    """გაყიდვის დეტალური ანალიზი"""
    # Exit details
    exit_reason: ExitReason
    exit_price: float
    exit_time: str

    # P&L
    entry_price: float
    profit_usd: float
    profit_pct: float

    # Simulation (100$ base)
    initial_investment: float = 100.0
    final_value: float = 0.0
    simulated_profit_usd: float = 0.0
    simulated_profit_pct: float = 0.0

    # Strategy performance
    expected_profit_min: float = 0.0
    expected_profit_max: float = 0.0
    expectation_met: bool = False

    # Additional metrics
    max_profit_during_hold: float = 0.0
    max_profit_pct_during_hold: float = 0.0
    hold_duration_hours: float = 0.0
    hold_duration_human: str = ""

    # Signal quality
    signal_confidence: float = 0.0
    ai_approved: bool = False
    realistic_target_met: bool = False

# ═══════════════════════════════════════════════════════════════════════════
# EXIT SIGNALS HANDLER
# ═══════════════════════════════════════════════════════════════════════════

class ExitSignalsHandler:
    """
    EXIT SIGNALS HANDLER - PRODUCTION GRADE

    ✅ სიზუსტე:
    - Position monitoring (real-time)
    - Exit condition detection
    - Profit/Loss calculation
    - 100$ simulation
    - Performance analytics
    """

    def __init__(self):
        self.active_positions = {}  # symbol -> position data
        self.exit_history = []  # closed positions
        self.price_history = {}  # price tracking for max profit

        logger.info("✅ ExitSignalsHandler initialized")

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════

    def register_position(
        self,
        symbol: str,
        entry_price: float,
        target_price: float,
        stop_loss_price: float,
        entry_time: str,
        signal_confidence: float,
        expected_profit_min: float,
        expected_profit_max: float,
        strategy_type: str,
        signal_id: Optional[int] = None,
        ai_approved: bool = False
    ):
        """ახალი position რეგისტრაცია"""

        self.active_positions[symbol] = {
            'entry_price': entry_price,
            'target_price': target_price,
            'stop_loss_price': stop_loss_price,
            'entry_time': entry_time,
            'signal_confidence': signal_confidence,
            'expected_profit_min': expected_profit_min,
            'expected_profit_max': expected_profit_max,
            'strategy_type': strategy_type,
            'signal_id': signal_id,
            'ai_approved': ai_approved,
            'max_price': entry_price,  # Track highest price
            'min_price': entry_price,  # Track lowest price
            'status': 'OPEN'
        }

        # Initialize price history
        if symbol not in self.price_history:
            self.price_history[symbol] = []

        self.price_history[symbol].append({
            'price': entry_price,
            'time': entry_time,
            'type': 'ENTRY'
        })

        logger.info(
            f"📝 Position registered: {symbol}\n"
            f"   Entry: ${entry_price:.4f}\n"
            f"   Target: ${target_price:.4f} ({expected_profit_max:.1f}%)\n"
            f"   Stop: ${stop_loss_price:.4f}"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MONITORING
    # ═══════════════════════════════════════════════════════════════════════

    def update_price(self, symbol: str, current_price: float, timestamp: str):
        """ფასის განახლება (მუდმივი ზეწნა)"""

        if symbol not in self.active_positions:
            return

        pos = self.active_positions[symbol]

        # Track price extremes
        if current_price > pos['max_price']:
            pos['max_price'] = current_price
        if current_price < pos['min_price']:
            pos['min_price'] = current_price

        # Add to history
        if symbol in self.price_history:
            self.price_history[symbol].append({
                'price': current_price,
                'time': timestamp,
                'type': 'UPDATE'
            })

    # ═══════════════════════════════════════════════════════════════════════
    # EXIT CONDITION DETECTION
    # ═══════════════════════════════════════════════════════════════════════

    def check_exit_condition(
        self,
        symbol: str,
        current_price: float,
        current_time: str
    ) -> Tuple[Optional[ExitReason], Optional[float]]:
        """
        EXIT პირობის შემოწმება

        Returns:
            (exit_reason, exit_price) ან (None, None) თუ არ არის exit
        """

        if symbol not in self.active_positions:
            return None, None

        pos = self.active_positions[symbol]

        # ✅ 1. TARGET HIT
        if current_price >= pos['target_price']:
            logger.info(f"🎯 {symbol} TARGET HIT: ${current_price:.4f}")
            return ExitReason.TARGET_HIT, current_price

        # 🔴 2. STOP LOSS HIT
        if current_price <= pos['stop_loss_price']:
            logger.warning(f"🛑 {symbol} STOP LOSS HIT: ${current_price:.4f}")
            return ExitReason.STOP_LOSS, current_price

        # ⏰ 3. TIMEOUT (მაქსიმალური hold duration)
        entry_time = datetime.fromisoformat(pos['entry_time'])
        current_time_dt = datetime.fromisoformat(current_time)
        hold_hours = (current_time_dt - entry_time).total_seconds() / 3600

        # Long-term: 72h, Swing: 240h, Scalping: 1h, Opportunistic: 168h
        max_hold_hours = {
            'long_term': 72 * 7,  # 1 კვირა
            'swing': 240,         # 10 დღე
            'scalping': 1,        # 1 საათი
            'opportunistic': 168  # 7 დღე
        }

        strategy = pos['strategy_type']
        max_hours = max_hold_hours.get(strategy, 240)

        if hold_hours > max_hours:
            logger.warning(
                f"⏰ {symbol} TIMEOUT: {hold_hours:.1f}h / {max_hours}h"
            )
            return ExitReason.TIMEOUT, current_price

        return None, None

    # ═══════════════════════════════════════════════════════════════════════
    # EXIT ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════

    def analyze_exit(
        self,
        symbol: str,
        exit_reason: ExitReason,
        exit_price: float,
        exit_time: str,
        current_price_history: Dict = None
    ) -> Optional[ExitAnalysis]:
        """
        გაყიდვის დეტალური ანალიზი
        """

        if symbol not in self.active_positions:
            return None

        pos = self.active_positions[symbol]
        entry_price = pos['entry_price']
        entry_time = datetime.fromisoformat(pos['entry_time'])
        exit_time_dt = datetime.fromisoformat(exit_time)

        # ════════════════════════════════════════════════════════════════════
        # 1. PROFIT/LOSS CALCULATION
        # ════════════════════════════════════════════════════════════════════

        profit_pct = ((exit_price - entry_price) / entry_price) * 100

        # Assume 1 unit was bought (for USD profit calculation)
        # In reality, this would be: position_size * profit_pct / 100
        profit_usd = 1.0 * (exit_price - entry_price)

        # ════════════════════════════════════════════════════════════════════
        # 2. 100$ SIMULATION
        # ════════════════════════════════════════════════════════════════════

        initial_investment = 100.0
        shares_bought = initial_investment / entry_price
        final_value = shares_bought * exit_price
        simulated_profit_usd = final_value - initial_investment
        simulated_profit_pct = (simulated_profit_usd / initial_investment) * 100

        # ════════════════════════════════════════════════════════════════════
        # 3. EXPECTATION ANALYSIS
        # ════════════════════════════════════════════════════════════════════

        expected_min = pos['expected_profit_min']
        expected_max = pos['expected_profit_max']
        expectation_met = expected_min <= profit_pct <= expected_max
        realistic_target_met = profit_pct >= (expected_min * 0.8)  # 80% of min

        # ════════════════════════════════════════════════════════════════════
        # 4. MAX PROFIT DURING HOLD
        # ════════════════════════════════════════════════════════════════════

        max_price = pos['max_price']
        max_profit_pct = ((max_price - entry_price) / entry_price) * 100
        max_profit_usd = 1.0 * (max_price - entry_price)

        # ════════════════════════════════════════════════════════════════════
        # 5. HOLD DURATION
        # ════════════════════════════════════════════════════════════════════

        hold_duration = exit_time_dt - entry_time
        hold_hours = hold_duration.total_seconds() / 3600
        hold_duration_human = self._format_duration(hold_duration)

        # ════════════════════════════════════════════════════════════════════
        # 6. BUILD EXIT ANALYSIS
        # ════════════════════════════════════════════════════════════════════

        exit_analysis = ExitAnalysis(
            # Exit details
            exit_reason=exit_reason,
            exit_price=exit_price,
            exit_time=exit_time,

            # P&L
            entry_price=entry_price,
            profit_usd=profit_usd,
            profit_pct=profit_pct,

            # Simulation
            initial_investment=initial_investment,
            final_value=final_value,
            simulated_profit_usd=simulated_profit_usd,
            simulated_profit_pct=simulated_profit_pct,

            # Expectations
            expected_profit_min=expected_min,
            expected_profit_max=expected_max,
            expectation_met=expectation_met,

            # Max profit
            max_profit_during_hold=max_profit_usd,
            max_profit_pct_during_hold=max_profit_pct,

            # Duration
            hold_duration_hours=hold_hours,
            hold_duration_human=hold_duration_human,

            # Quality
            signal_confidence=pos['signal_confidence'],
            ai_approved=pos['ai_approved'],
            realistic_target_met=realistic_target_met
        )

        logger.info(
            f"📊 EXIT ANALYSIS: {symbol}\n"
            f"   Entry: ${entry_price:.4f} → Exit: ${exit_price:.4f}\n"
            f"   Profit: {profit_pct:+.2f}% (${profit_usd:+.2f})\n"
            f"   100$ Simulation: ${simulated_profit_usd:+.2f} ({simulated_profit_pct:+.2f}%)\n"
            f"   Max during hold: {max_profit_pct:+.2f}%\n"
            f"   Hold: {hold_duration_human}\n"
            f"   Expected: {expected_min:.1f}% - {expected_max:.1f}% | Met: {expectation_met}"
        )

        return exit_analysis

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _format_duration(self, duration: timedelta) -> str:
        """ხანგრძლივობის ლამაზი ფორმატირება"""
        total_seconds = duration.total_seconds()

        days = int(total_seconds // 86400)
        hours = int((total_seconds % 86400) // 3600)
        minutes = int((total_seconds % 3600) // 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")

        return " ".join(parts) if parts else "< 1m"

    def close_position(self, symbol: str, exit_analysis: ExitAnalysis):
        """Position დახურვა"""

        if symbol not in self.active_positions:
            return

        pos = self.active_positions[symbol]
        pos['status'] = 'CLOSED'
        pos['exit_analysis'] = exit_analysis

        # Move to history
        self.exit_history.append({
            'symbol': symbol,
            'entry_price': pos['entry_price'],
            'exit_price': exit_analysis.exit_price,
            'entry_time': pos['entry_time'],
            'exit_time': exit_analysis.exit_time,
            'profit_pct': exit_analysis.profit_pct,
            'exit_reason': exit_analysis.exit_reason.value,
            'strategy': pos['strategy_type'],
            'analysis': exit_analysis
        })

        # Remove from active
        del self.active_positions[symbol]

        logger.info(f"✅ Position closed: {symbol}")

    # ═══════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════════

    def get_exit_statistics(self) -> Dict:
        """სტატისტიკა დახურული positions-ების შესახებ"""

        if not self.exit_history:
            return {
                'total_exits': 0,
                'successful': 0,
                'failed': 0,
                'avg_profit': 0,
                'best_trade': 0,
                'worst_trade': 0
            }

        profits = [e['profit_pct'] for e in self.exit_history]
        successful = sum(1 for p in profits if p > 0)
        failed = len(profits) - successful

        return {
            'total_exits': len(self.exit_history),
            'successful': successful,
            'failed': failed,
            'win_rate': (successful / len(self.exit_history) * 100) if self.exit_history else 0,
            'avg_profit': sum(profits) / len(profits) if profits else 0,
            'best_trade': max(profits) if profits else 0,
            'worst_trade': min(profits) if profits else 0,
            'total_profit': sum(profits)
        }

    def get_active_positions_summary(self) -> str:
        """აქტიური positions-ების summary"""

        if not self.active_positions:
            return "📭 არ არის აქტიური positions"

        summary = "📊 **აქტიური Positions:**\n\n"

        for symbol, pos in self.active_positions.items():
            summary += f"**{symbol}**\n"
            summary += f"├─ Entry: ${pos['entry_price']:.4f}\n"
            summary += f"├─ Target: ${pos['target_price']:.4f}\n"
            summary += f"├─ Stop: ${pos['stop_loss_price']:.4f}\n"
            summary += f"└─ Status: {pos['status']}\n\n"

        return summary