"""
═══════════════════════════════════════════════════════════════════════════════
POSITION MONITOR - PRODUCTION v1.0
═══════════════════════════════════════════════════════════════════════════════

✅ მუდმივი ზეწნა:
- Price updates (real-time)
- Exit condition checks
- Performance tracking
- Telegram alerts

AUTHOR: Trading System Architecture Team
DATE: 2024-02-14
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class PositionMonitor:
    """
    POSITION MONITOR

    ✅ მუდმივი ზეწნა active positions
    ✅ სიგნალი გასვლაზე
    ✅ Performance tracking
    """

    def __init__(
        self,
        exit_handler,
        data_provider,
        telegram_handler,
        analytics_db,
        scan_interval: int = 60
    ):
        """
        ინიციალიზაცია

        Args:
            exit_handler: ExitSignalsHandler ობიექტი
            data_provider: Market data provider
            telegram_handler: Telegram bot handler
            analytics_db: Analytics database
            scan_interval: წამში (default: 60s)
        """

        self.exit_handler = exit_handler
        self.data_provider = data_provider
        self.telegram_handler = telegram_handler
        self.analytics_db = analytics_db
        self.scan_interval = scan_interval

        self.is_monitoring = False
        self.monitoring_task = None

        logger.info(
            f"✅ PositionMonitor initialized | "
            f"Scan interval: {scan_interval}s"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # MONITORING LOOP
    # ═══════════════════════════════════════════════════════════════════════

    async def start_monitoring(self):
        """დაიწყოს მონიტორინგი"""

        if self.is_monitoring:
            logger.warning("⚠️ Monitoring ყველა უკვე გაშვებული")
            return

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info("🔍 Position monitoring დაიწყო")

    async def stop_monitoring(self):
        """შეწყვიტოს მონიტორინგი"""

        self.is_monitoring = False

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("🛑 Position monitoring შეწყდა")

    async def _monitoring_loop(self):
        """მთავარი მონიტორინგის loop"""

        while self.is_monitoring:
            try:
                await self._check_all_positions()
                await asyncio.sleep(self.scan_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Monitoring error: {e}")
                await asyncio.sleep(10)

    async def _check_all_positions(self):
        """ყველა active position-ის შემოწმება"""

        active_symbols = list(self.exit_handler.active_positions.keys())

        if not active_symbols:
            return  # No positions to monitor

        logger.debug(f"🔍 Monitoring {len(active_symbols)} positions...")

        for symbol in active_symbols:
            try:
                await self._check_single_position(symbol)
            except Exception as e:
                logger.error(f"❌ Error checking {symbol}: {e}")
                continue

    async def _check_single_position(self, symbol: str):
        """ერთი position-ის შემოწმება"""

        # ════════════════════════════════════════════════════════════════════
        # 1. ფასის მიღება
        # ════════════════════════════════════════════════════════════════════

        if not self.data_provider:
            return

        try:
            market_data = await self.data_provider.fetch_with_fallback(symbol)
            if not market_data:
                return

            current_price = market_data.price
            current_time = datetime.now().isoformat()

        except Exception as e:
            logger.debug(f"⚠️ Failed to fetch price for {symbol}: {e}")
            return

        # ════════════════════════════════════════════════════════════════════
        # 2. Price update
        # ════════════════════════════════════════════════════════════════════

        self.exit_handler.update_price(symbol, current_price, current_time)

        # ════════════════════════════════════════════════════════════════════
        # 3. Exit condition check
        # ════════════════════════════════════════════════════════════════════

        exit_reason, exit_price = self.exit_handler.check_exit_condition(
            symbol=symbol,
            current_price=current_price,
            current_time=current_time
        )

        if exit_reason is None:
            # No exit condition met, position still open
            return

        # ════════════════════════════════════════════════════════════════════
        # 4. EXIT DETECTED! Analyze & Close
        # ════════════════════════════════════════════════════════════════════

        logger.warning(
            f"🎯 EXIT CONDITION DETECTED: {symbol}\n"
            f"   Reason: {exit_reason.value}\n"
            f"   Price: ${exit_price:.4f}"
        )

        await self._handle_position_exit(
            symbol=symbol,
            exit_reason=exit_reason,
            exit_price=exit_price,
            exit_time=current_time
        )

    # ═══════════════════════════════════════════════════════════════════════
    # EXIT HANDLING
    # ═══════════════════════════════════════════════════════════════════════

    async def _handle_position_exit(
        self,
        symbol: str,
        exit_reason,
        exit_price: float,
        exit_time: str
    ):
        """Position exit დამუშავება"""

        # ════════════════════════════════════════════════════════════════════
        # 1. ANALYZE EXIT
        # ════════════════════════════════════════════════════════════════════

        exit_analysis = self.exit_handler.analyze_exit(
            symbol=symbol,
            exit_reason=exit_reason,
            exit_price=exit_price,
            exit_time=exit_time
        )

        if not exit_analysis:
            logger.error(f"❌ Failed to analyze exit for {symbol}")
            return

        # ════════════════════════════════════════════════════════════════════
        # 2. SEND TELEGRAM MESSAGE
        # ════════════════════════════════════════════════════════════════════

        if self.telegram_handler:
            try:
                from sell_signal_message_generator import SellSignalMessageGenerator

                # დეტალური message
                message = SellSignalMessageGenerator.generate_sell_message(
                    symbol=symbol,
                    exit_analysis=exit_analysis
                )

                await self.telegram_handler.broadcast_signal(
                    message=message,
                    asset=symbol
                )

                logger.info(f"📤 SELL signal sent: {symbol}")

            except Exception as e:
                logger.error(f"❌ Failed to send Telegram message: {e}")

        # ════════════════════════════════════════════════════════════════════
        # 3. RECORD IN ANALYTICS
        # ════════════════════════════════════════════════════════════════════

        if self.analytics_db:
            try:
                pos = self.exit_handler.active_positions.get(symbol)
                if pos and pos['signal_id']:
                    self.analytics_db.record_performance(
                        signal_id=pos['signal_id'],
                        outcome='SUCCESS' if exit_analysis.profit_pct > 0 else 'FAILURE',
                        final_profit_pct=exit_analysis.profit_pct,
                        exit_reason=exit_reason.value
                    )

                    logger.info(f"📊 Performance recorded: {symbol}")

            except Exception as e:
                logger.error(f"❌ Failed to record performance: {e}")

        # ════════════════════════════════════════════════════════════════════
        # 4. CLOSE POSITION
        # ════════════════════════════════════════════════════════════════════

        self.exit_handler.close_position(symbol, exit_analysis)

        logger.info(f"✅ Position closed: {symbol}")

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION SUMMARY
    # ═══════════════════════════════════════════════════════════════════════

    def get_position_status_report(self) -> str:
        """Position status report"""

        active = self.exit_handler.active_positions

        if not active:
            return "📭 **არ არის აქტიური positions**"

        msg = f"📊 **აქტიური Positions:** {len(active)}\n\n"

        for symbol, pos in active.items():
            status = pos['status']
            entry = pos['entry_price']
            target = pos['target_price']
            stop = pos['stop_loss_price']

            msg += f"**{symbol}** ({status})\n"
            msg += f"├─ Entry:  ${entry:.4f}\n"
            msg += f"├─ Target: ${target:.4f}\n"
            msg += f"├─ Stop:   ${stop:.4f}\n"
            msg += f"└─ Conf:   {pos['signal_confidence']:.0f}%\n\n"

        return msg

    def get_closed_positions_summary(self) -> str:
        """დახურული positions-ების summary"""

        from sell_signal_message_generator import SellSignalMessageGenerator
        return SellSignalMessageGenerator.generate_position_summary(
            self.exit_handler.exit_history
        )

    # ═══════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════════

    def get_monitoring_statistics(self) -> Dict:
        """მონიტორინგის სტატისტიკა"""

        return {
            'is_monitoring': self.is_monitoring,
            'scan_interval': self.scan_interval,
            'active_positions': len(self.exit_handler.active_positions),
            'closed_positions': len(self.exit_handler.exit_history),
            'exit_stats': self.exit_handler.get_exit_statistics()
        }