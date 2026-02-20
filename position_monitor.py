"""
═══════════════════════════════════════════════════════════════════════════════
POSITION MONITOR v2.0
═══════════════════════════════════════════════════════════════════════════════
✅ ახალი v2.0:
- AI Exit Evaluator ინტეგრაცია (partial exit რეკომენდაცია)
- SignalMemory outcome update (exit-ის შემდეგ მეხსიერება განახლდება)
- Target progress trigger: 70%-ზე AI exit eval გამოძახება
- Hold time warning: tier-based max hold
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict

from config import get_tier_risk, ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

# AI Exit Evaluator — optional
try:
    from ai_exit_evaluator import AIExitEvaluator
    AI_EXIT_AVAILABLE = True
except Exception as e:
    AI_EXIT_AVAILABLE = False
    logger.warning(f"⚠️ AIExitEvaluator not available: {e}")

# Signal Memory — optional
try:
    from signal_memory import SignalMemory
    MEMORY_AVAILABLE = True
except Exception as e:
    MEMORY_AVAILABLE = False
    logger.warning(f"⚠️ SignalMemory not available: {e}")


class PositionMonitor:

    def __init__(
        self,
        exit_handler,
        data_provider,
        telegram_handler,
        analytics_db,
        scan_interval: int = 60
    ):
        self.exit_handler     = exit_handler
        self.data_provider    = data_provider
        self.telegram_handler = telegram_handler
        self.analytics_db     = analytics_db
        self.scan_interval    = scan_interval
        self.is_monitoring    = False
        self.monitoring_task  = None

        # AI Exit Evaluator
        self.ai_exit = None
        if AI_EXIT_AVAILABLE and ANTHROPIC_API_KEY:
            try:
                self.ai_exit = AIExitEvaluator(api_key=ANTHROPIC_API_KEY)
                logger.info("✅ AIExitEvaluator ready")
            except Exception as e:
                logger.warning(f"⚠️ AIExitEvaluator init failed: {e}")

        # Signal Memory
        self.signal_memory = None
        if MEMORY_AVAILABLE:
            try:
                self.signal_memory = SignalMemory()
                logger.info("✅ SignalMemory ready")
            except Exception as e:
                logger.warning(f"⚠️ SignalMemory init failed: {e}")

        # Track which positions already got AI exit advice (avoid spam)
        self._exit_advised: set = set()

        logger.info(f"✅ PositionMonitor v2.0 | interval={scan_interval}s | "
                    f"AI Exit: {'✅' if self.ai_exit else '❌'} | "
                    f"Memory: {'✅' if self.signal_memory else '❌'}")

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    async def start_monitoring(self):
        if self.is_monitoring:
            return
        self.is_monitoring   = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("🔍 Position monitoring started")

    async def stop_monitoring(self):
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Position monitoring stopped")

    async def _monitoring_loop(self):
        while self.is_monitoring:
            try:
                await self._check_all_positions()
                await asyncio.sleep(self.scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Monitoring loop error: {e}")
                await asyncio.sleep(10)

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION CHECK
    # ═══════════════════════════════════════════════════════════════════════

    async def _check_all_positions(self):
        symbols = list(self.exit_handler.active_positions.keys())
        if not symbols:
            return
        logger.debug(f"🔍 Monitoring {len(symbols)} positions")
        for symbol in symbols:
            try:
                await self._check_single_position(symbol)
            except Exception as e:
                logger.error(f"❌ Error checking {symbol}: {e}")

    async def _check_single_position(self, symbol: str):
        if not self.data_provider:
            return

        try:
            md = await self.data_provider.fetch_with_fallback(symbol)
            if not md:
                return
            current_price = md.price
            current_time  = datetime.now().isoformat()
        except Exception as e:
            logger.debug(f"⚠️ Price fetch failed {symbol}: {e}")
            return

        self.exit_handler.update_price(symbol, current_price, current_time)

        # ── 1. Exit condition check ───────────────────────────────────────
        exit_reason, exit_price = self.exit_handler.check_exit_condition(
            symbol=symbol,
            current_price=current_price,
            current_time=current_time
        )

        if exit_reason is not None:
            await self._handle_position_exit(symbol, exit_reason, exit_price, current_time)
            return

        # ── 2. AI Partial Exit check ──────────────────────────────────────
        await self._check_partial_exit(symbol, current_price, md)

    # ═══════════════════════════════════════════════════════════════════════
    # AI PARTIAL EXIT
    # ═══════════════════════════════════════════════════════════════════════

    async def _check_partial_exit(self, symbol: str, current_price: float, md):
        """
        target-ის 70%-ზე მიღწევისას AI-ს ეკითხება:
        HOLD_ALL / TAKE_PARTIAL / TAKE_FULL
        """
        if not self.ai_exit:
            return
        if symbol in self._exit_advised:
            return  # უკვე ვუთხარით ამ position-ზე

        pos = self.exit_handler.active_positions.get(symbol)
        if not pos:
            return

        entry_price  = pos["entry_price"]
        target_price = pos["target_price"]
        stop_loss    = pos["stop_loss_price"]
        strategy     = pos.get("strategy_type", "swing")

        profit_pct     = (current_price - entry_price) / entry_price * 100
        max_profit_pct = (target_price - entry_price)  / entry_price * 100
        progress       = profit_pct / max_profit_pct * 100 if max_profit_pct > 0 else 0

        # Trigger: 70%+ of target reached
        if progress < 70:
            return

        # Hold duration
        try:
            entry_dt  = datetime.fromisoformat(pos["entry_time"])
            hold_h    = (datetime.now() - entry_dt).total_seconds() / 3600
        except Exception:
            hold_h = 0

        tier = self._get_tier(symbol)

        # Symbol history for AI context
        history_str = ""
        if self.signal_memory:
            history_str = self.signal_memory.get_summary(symbol)

        indicators = {
            "rsi":                 md.rsi,
            "macd_histogram":      md.macd_histogram,
            "macd_histogram_prev": getattr(md, "macd_histogram_prev", md.macd_histogram),
            "volume":              getattr(md, "volume", 1_000_000),
            "avg_volume_20d":      getattr(md, "avg_volume_20d", 1_000_000),
        }

        try:
            evaluation = await self.ai_exit.evaluate_exit(
                symbol=symbol,
                entry_price=entry_price,
                current_price=current_price,
                target_price=target_price,
                stop_loss=stop_loss,
                strategy=strategy,
                tier=tier,
                hold_hours=hold_h,
                indicators=indicators,
                symbol_history=history_str,
            )

            # Only send if actionable
            from ai_exit_evaluator import ExitAdvice
            if evaluation.advice in (ExitAdvice.TAKE_PARTIAL, ExitAdvice.TAKE_FULL):
                msg = self.ai_exit.format_telegram_message(
                    symbol=symbol,
                    profit_pct=profit_pct,
                    evaluation=evaluation,
                    entry_price=entry_price,
                    current_price=current_price,
                )

                if self.telegram_handler:
                    await self.telegram_handler.broadcast_signal(
                        message=msg, asset=symbol
                    )
                    logger.info(f"📊 Partial exit advice sent: {symbol} {evaluation.advice.value}")

            # Mark as advised — no repeat for this position
            self._exit_advised.add(symbol)

        except Exception as e:
            logger.error(f"❌ AI exit eval error {symbol}: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # FULL EXIT
    # ═══════════════════════════════════════════════════════════════════════

    async def _handle_position_exit(
        self, symbol: str, exit_reason, exit_price: float, exit_time: str
    ):
        exit_analysis = self.exit_handler.analyze_exit(
            symbol=symbol,
            exit_reason=exit_reason,
            exit_price=exit_price,
            exit_time=exit_time
        )
        if not exit_analysis:
            return

        # ── Telegram SELL message ─────────────────────────────────────────
        if self.telegram_handler:
            try:
                from sell_signal_message_generator import SellSignalMessageGenerator
                msg = SellSignalMessageGenerator.generate_sell_message(
                    symbol=symbol, exit_analysis=exit_analysis
                )
                await self.telegram_handler.broadcast_signal(message=msg, asset=symbol)
                logger.info(f"📤 SELL signal sent: {symbol}")
            except Exception as e:
                logger.error(f"❌ Sell message error: {e}")

        # ── Analytics ────────────────────────────────────────────────────
        if self.analytics_db:
            try:
                pos = self.exit_handler.active_positions.get(symbol)
                if pos and pos.get("signal_id"):
                    self.analytics_db.record_performance(
                        signal_id=pos["signal_id"],
                        outcome="SUCCESS" if exit_analysis.profit_pct > 0 else "FAILURE",
                        final_profit_pct=exit_analysis.profit_pct,
                        exit_reason=exit_reason.value
                    )
            except Exception as e:
                logger.error(f"❌ Analytics record error: {e}")

        # ── Signal Memory update ──────────────────────────────────────────
        if self.signal_memory:
            try:
                self.signal_memory.update_outcome(
                    symbol=symbol,
                    exit_price=exit_price,
                    profit_pct=exit_analysis.profit_pct,
                    win=exit_analysis.profit_pct > 0,
                    exit_reason=exit_reason.value,
                )
                logger.debug(f"📝 Memory updated: {symbol}")
            except Exception as e:
                logger.error(f"❌ Memory update error: {e}")

        # ── Close position ────────────────────────────────────────────────
        self.exit_handler.close_position(symbol, exit_analysis)
        self._exit_advised.discard(symbol)  # reset for next trade
        logger.info(f"✅ Position closed: {symbol}")

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _get_tier(self, symbol: str) -> str:
        from config import get_tier
        return get_tier(symbol)

    def get_position_status_report(self) -> str:
        active = self.exit_handler.active_positions
        if not active:
            return "📭 არ არის აქტიური positions"

        msg = f"📊 აქტიური Positions: {len(active)}\n\n"
        for symbol, pos in active.items():
            entry  = pos["entry_price"]
            target = pos["target_price"]
            stop   = pos["stop_loss_price"]
            msg += (
                f"{symbol}\n"
                f"├─ Entry:  ${entry:.4f}\n"
                f"├─ Target: ${target:.4f}\n"
                f"└─ Stop:   ${stop:.4f}\n\n"
            )
        return msg

    def get_monitoring_statistics(self) -> Dict:
        return {
            "is_monitoring":    self.is_monitoring,
            "scan_interval":    self.scan_interval,
            "active_positions": len(self.exit_handler.active_positions),
            "closed_positions": len(self.exit_handler.exit_history),
            "exit_stats":       self.exit_handler.get_exit_statistics(),
        }
