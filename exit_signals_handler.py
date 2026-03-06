"""
EXIT SIGNALS HANDLER - PRODUCTION v2.0 FIXED
P1 FIX #5: Trailing stop — target-ის 50%+ progress-ზე ჩაირთვება
v1.0 შენარჩუნებული: TARGET_HIT, STOP_LOSS, TIMEOUT, ExitAnalysis, 100$ sim
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ExitReason(Enum):
    TARGET_HIT    = "target_hit"
    STOP_LOSS     = "stop_loss"
    TIMEOUT       = "timeout"
    MANUAL        = "manual"
    PARTIAL_EXIT  = "partial_exit"
    TRAILING_STOP = "trailing_stop"   # ✅ P1/#5 NEW


class ExitSignalType(Enum):
    FULL_EXIT    = "full_exit"
    PARTIAL_EXIT = "partial_exit"
    TAKE_PROFIT  = "take_profit"


@dataclass
class ExitAnalysis:
    exit_reason:               ExitReason
    exit_price:                float
    exit_time:                 str
    entry_price:               float
    profit_usd:                float
    profit_pct:                float
    initial_investment:        float = 100.0
    final_value:               float = 0.0
    simulated_profit_usd:      float = 0.0
    simulated_profit_pct:      float = 0.0
    expected_profit_min:       float = 0.0
    expected_profit_max:       float = 0.0
    expectation_met:           bool  = False
    max_profit_during_hold:    float = 0.0
    max_profit_pct_during_hold: float = 0.0
    hold_duration_hours:       float = 0.0
    hold_duration_human:       str   = ""
    signal_confidence:         float = 0.0
    ai_approved:               bool  = False
    realistic_target_met:      bool  = False


class ExitSignalsHandler:
    """
    EXIT SIGNALS HANDLER v2.0 FIXED
    ✅ P1/#5 — Trailing stop: activates when profit >= 50% of target
               Trail distance = 40% of profit gained so far
    """

    def __init__(self):
        self.active_positions: Dict = {}
        self.exit_history:     list = []
        self.price_history:    Dict = {}
        logger.info("✅ ExitSignalsHandler v2.0 initialized (trailing stop enabled)")

    # ─── Position Registration ────────────────────────────────────────────

    def register_position(
        self,
        symbol:             str,
        entry_price:        float,
        target_price:       float,
        stop_loss_price:    float,
        entry_time:         str,
        signal_confidence:  float,
        expected_profit_min: float,
        expected_profit_max: float,
        strategy_type:      str,
        signal_id:          Optional[int] = None,
        ai_approved:        bool = False,
    ):
        self.active_positions[symbol] = {
            "entry_price":        entry_price,
            "target_price":       target_price,
            "stop_loss_price":    stop_loss_price,
            "entry_time":         entry_time,
            "signal_confidence":  signal_confidence,
            "expected_profit_min": expected_profit_min,
            "expected_profit_max": expected_profit_max,
            "strategy_type":      strategy_type,
            "signal_id":          signal_id,
            "ai_approved":        ai_approved,
            "max_price":          entry_price,
            "min_price":          entry_price,
            "status":             "OPEN",
            # ✅ P1/#5 — trailing stop state
            "trailing_active":    False,
            "trailing_stop":      stop_loss_price,  # will be updated dynamically
        }

        self.price_history.setdefault(symbol, [])
        self.price_history[symbol].append({
            "price": entry_price, "time": entry_time, "type": "ENTRY"
        })

        logger.info(
            f"📝 Position registered: {symbol}\n"
            f"   Entry: ${entry_price:.4f} | Target: ${target_price:.4f} | "
            f"Stop: ${stop_loss_price:.4f}"
        )

    # ─── Price Update ─────────────────────────────────────────────────────

    def update_price(self, symbol: str, current_price: float, timestamp: str):
        if symbol not in self.active_positions:
            return
        pos = self.active_positions[symbol]
        if current_price > pos["max_price"]:
            pos["max_price"] = current_price
        if current_price < pos["min_price"]:
            pos["min_price"] = current_price

        # ✅ P1/#5 — update trailing stop if active
        self._update_trailing_stop(pos, current_price)

        self.price_history.setdefault(symbol, []).append({
            "price": current_price, "time": timestamp, "type": "UPDATE"
        })

    def _update_trailing_stop(self, pos: Dict, current_price: float):
        """
        ✅ P1/#5 — Trailing stop logic:
        Activates when profit >= 50% of target distance.
        Trail = 40% of max profit gained (locks in 60% of peak gains).
        """
        entry  = pos["entry_price"]
        target = pos["target_price"]
        profit_dist = target - entry  # total target range
        if profit_dist <= 0:
            return

        current_profit = current_price - entry
        progress = current_profit / profit_dist  # 0..1..2

        if progress >= 0.50:
            # Activate trailing stop
            if not pos["trailing_active"]:
                pos["trailing_active"] = True
                logger.info(
                    f"🎯 Trailing stop ACTIVATED: {pos.get('symbol', '?')} @ "
                    f"${current_price:.4f} ({progress*100:.0f}% of target)"
                )

            # Trail = max_price - 40% of (max_price - entry)
            max_profit_gained = pos["max_price"] - entry
            trail_dist        = max_profit_gained * 0.40
            new_trail         = pos["max_price"] - trail_dist

            # Only move trailing stop UP, never down
            if new_trail > pos["trailing_stop"]:
                pos["trailing_stop"] = new_trail
                logger.debug(
                    f"⬆️ Trailing stop raised: ${new_trail:.4f} "
                    f"(max: ${pos['max_price']:.4f})"
                )

    # ─── Exit Condition Detection ─────────────────────────────────────────

    def check_exit_condition(
        self,
        symbol:        str,
        current_price: float,
        current_time:  str,
    ) -> Tuple[Optional[ExitReason], Optional[float]]:

        if symbol not in self.active_positions:
            return None, None

        pos = self.active_positions[symbol]
        pos["symbol"] = symbol  # ensure symbol stored for logging

        # 1. TARGET HIT
        if current_price >= pos["target_price"]:
            logger.info(f"🎯 {symbol} TARGET HIT: ${current_price:.4f}")
            return ExitReason.TARGET_HIT, current_price

        # 2. ✅ P1/#5 — TRAILING STOP (checked before fixed stop loss)
        if pos["trailing_active"] and current_price <= pos["trailing_stop"]:
            locked_pct = (pos["trailing_stop"] - pos["entry_price"]) / pos["entry_price"] * 100
            logger.info(
                f"🎯 {symbol} TRAILING STOP: ${current_price:.4f} "
                f"| Locked: +{locked_pct:.1f}%"
            )
            return ExitReason.TRAILING_STOP, current_price

        # 3. FIXED STOP LOSS
        if current_price <= pos["stop_loss_price"]:
            logger.warning(f"🛑 {symbol} STOP LOSS: ${current_price:.4f}")
            return ExitReason.STOP_LOSS, current_price

        # 4. TIMEOUT
        max_hold = {
            "long_term":     504,   # 21 days
            "swing":         240,   # 10 days
            "scalping":      1,     # 1 hour
            "opportunistic": 168,   # 7 days
        }
        try:
            entry_dt  = datetime.fromisoformat(pos["entry_time"])
            curr_dt   = datetime.fromisoformat(current_time)
            hold_hrs  = (curr_dt - entry_dt).total_seconds() / 3600
            max_hrs   = max_hold.get(pos["strategy_type"], 240)
            if hold_hrs > max_hrs:
                logger.warning(f"⏰ {symbol} TIMEOUT: {hold_hrs:.1f}h / {max_hrs}h")
                return ExitReason.TIMEOUT, current_price
        except Exception:
            pass

        return None, None

    # ─── Exit Analysis (updated to include TRAILING_STOP reason) ──────────

    def analyze_exit(
        self,
        symbol:       str,
        exit_reason:  ExitReason,
        exit_price:   float,
        exit_time:    str,
        current_price_history: Dict = None,
    ) -> Optional[ExitAnalysis]:

        if symbol not in self.active_positions:
            return None

        pos         = self.active_positions[symbol]
        entry_price = pos["entry_price"]
        entry_time  = datetime.fromisoformat(pos["entry_time"])
        exit_dt     = datetime.fromisoformat(exit_time)

        profit_pct  = ((exit_price - entry_price) / entry_price) * 100
        profit_usd  = exit_price - entry_price

        init_inv    = 100.0
        shares      = init_inv / entry_price
        final_val   = shares * exit_price
        sim_profit  = final_val - init_inv
        sim_pct     = (sim_profit / init_inv) * 100

        exp_min = pos["expected_profit_min"]
        exp_max = pos["expected_profit_max"]

        max_price    = pos["max_price"]
        max_pct      = ((max_price - entry_price) / entry_price) * 100

        hold_dur     = exit_dt - entry_time
        hold_hrs     = hold_dur.total_seconds() / 3600

        trail_note = ""
        if exit_reason == ExitReason.TRAILING_STOP:
            trail_note = f" [trailing stop locked +{profit_pct:.1f}%]"

        logger.info(
            f"📊 EXIT: {symbol}{trail_note}\n"
            f"   Entry: ${entry_price:.4f} → Exit: ${exit_price:.4f}\n"
            f"   Profit: {profit_pct:+.2f}% | Max during hold: {max_pct:+.2f}%\n"
            f"   $100 sim: ${sim_profit:+.2f} ({sim_pct:+.2f}%)\n"
            f"   Hold: {self._fmt(hold_dur)} | Reason: {exit_reason.value}"
        )

        return ExitAnalysis(
            exit_reason=exit_reason,
            exit_price=exit_price,
            exit_time=exit_time,
            entry_price=entry_price,
            profit_usd=profit_usd,
            profit_pct=profit_pct,
            initial_investment=init_inv,
            final_value=final_val,
            simulated_profit_usd=sim_profit,
            simulated_profit_pct=sim_pct,
            expected_profit_min=exp_min,
            expected_profit_max=exp_max,
            expectation_met=(exp_min <= profit_pct <= exp_max),
            max_profit_during_hold=(max_price - entry_price),
            max_profit_pct_during_hold=max_pct,
            hold_duration_hours=hold_hrs,
            hold_duration_human=self._fmt(hold_dur),
            signal_confidence=pos["signal_confidence"],
            ai_approved=pos["ai_approved"],
            realistic_target_met=(profit_pct >= exp_min * 0.8),
        )

    def _fmt(self, dur: timedelta) -> str:
        s = dur.total_seconds()
        d = int(s // 86400); h = int((s%86400)//3600); m = int((s%3600)//60)
        parts = []
        if d: parts.append(f"{d}d")
        if h: parts.append(f"{h}h")
        if m: parts.append(f"{m}m")
        return " ".join(parts) if parts else "< 1m"

    def close_position(self, symbol: str, exit_analysis: ExitAnalysis):
        if symbol not in self.active_positions:
            return
        pos = self.active_positions[symbol]
        pos["status"] = "CLOSED"
        self.exit_history.append({
            "symbol":      symbol,
            "entry_price": pos["entry_price"],
            "exit_price":  exit_analysis.exit_price,
            "entry_time":  pos["entry_time"],
            "exit_time":   exit_analysis.exit_time,
            "profit_pct":  exit_analysis.profit_pct,
            "exit_reason": exit_analysis.exit_reason.value,
            "strategy":    pos["strategy_type"],
            "analysis":    exit_analysis,
        })
        del self.active_positions[symbol]
        logger.info(f"✅ Position closed: {symbol}")

    def get_exit_statistics(self) -> Dict:
        if not self.exit_history:
            return {"total_exits":0,"successful":0,"failed":0,
                    "win_rate":0,"avg_profit":0,"best_trade":0,"worst_trade":0}
        profits    = [e["profit_pct"] for e in self.exit_history]
        successful = sum(1 for p in profits if p > 0)
        return {
            "total_exits": len(self.exit_history),
            "successful":  successful,
            "failed":      len(profits) - successful,
            "win_rate":    successful / len(self.exit_history) * 100,
            "avg_profit":  sum(profits) / len(profits),
            "best_trade":  max(profits),
            "worst_trade": min(profits),
            "total_profit": sum(profits),
        }

    def get_active_positions_summary(self) -> str:
        if not self.active_positions:
            return "📭 არ არის აქტიური positions"
        s = "📊 **აქტიური Positions:**\n\n"
        for sym, pos in self.active_positions.items():
            trail = f" 🎯 trail:${pos['trailing_stop']:.4f}" if pos.get("trailing_active") else ""
            s += (f"**{sym}**\n"
                  f"├─ Entry:  ${pos['entry_price']:.4f}\n"
                  f"├─ Target: ${pos['target_price']:.4f}\n"
                  f"└─ Stop:   ${pos['stop_loss_price']:.4f}{trail}\n\n")
        return s