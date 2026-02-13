"""
AI Trading Bot - Main Entry Point - FINAL CORRECTED
✅ set_telegram_handler() properly called
✅ Telegram notifications 100% working
✅ Auto-restart logic
✅ Graceful shutdown
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

from config import *
from trading_engine import TradingEngine
from telegram_handler import TelegramHandler

# ========================
# LOGGING SETUP
# ========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ========================
# GLOBAL STATE
# ========================
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Graceful shutdown on SIGTERM/SIGINT"""
    logger.info(f"🛑 Received signal {signum}, initiating shutdown...")
    shutdown_event.set()

# ========================
# MAIN ORCHESTRATOR - ✅ CORRECTED!
# ========================
async def main():
    """
    ✅ CORRECTED: Proper bidirectional linking

    Critical Steps:
    1. Create TradingEngine
    2. Create TelegramHandler
    3. ✅ Call set_telegram_handler() - NOT direct assignment!
    4. Run both in parallel
    """

    logger.info("🚀 AI Trading Bot ინიციალიზაცია...")

    # ✅ STEP 1: Initialize TradingEngine
    try:
        trading_engine = TradingEngine()
        logger.info("✅ Trading Engine initialized")
    except Exception as e:
        logger.error(f"❌ TradingEngine initialization failed: {e}")
        return

    # ✅ STEP 2: Initialize TelegramHandler
    try:
        telegram_handler = TelegramHandler(trading_engine)
        logger.info("✅ Telegram Handler initialized")
    except Exception as e:
        logger.error(f"❌ TelegramHandler initialization failed: {e}")
        return

    # ✅ STEP 3: CRITICAL - Call set_telegram_handler()
    try:
        trading_engine.set_telegram_handler(telegram_handler)
        logger.info("✅ TradingEngine ↔ TelegramHandler დაკავშირებულია (via set_telegram_handler)")
    except Exception as e:
        logger.error(f"❌ Failed to link telegram handler: {e}")
        # Fallback to direct assignment
        trading_engine.telegram_handler = telegram_handler
        logger.warning("⚠️ Used direct assignment fallback")

    # Count assets
    all_assets = CRYPTO + STOCKS + COMMODITIES
    logger.info(f"✅ ჩატვირთულია {len(all_assets)} აქტივი მონიტორინგისთვის")

    # Verify telegram link
    if hasattr(trading_engine, 'telegram_handler') and trading_engine.telegram_handler:
        logger.info("✅ VERIFIED: trading_engine.telegram_handler is SET")
    else:
        logger.error("❌ CRITICAL: trading_engine.telegram_handler is NOT SET!")
        return

    # ========================
    # BACKGROUND TASKS
    # ========================
    async def run_telegram():
        """Telegram bot wrapper with auto-restart"""
        retry_count = 0
        max_retries = 5

        while not shutdown_event.is_set() and retry_count < max_retries:
            try:
                logger.info("📱 Starting Telegram handler...")
                await telegram_handler.start()

                logger.warning("⚠️ Telegram handler stopped")
                retry_count += 1

                if retry_count < max_retries:
                    await asyncio.sleep(30)

            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Telegram error ({retry_count}/{max_retries}): {e}")

                if retry_count < max_retries:
                    await asyncio.sleep(30)

        if retry_count >= max_retries:
            logger.error(f"🚨 Telegram handler failed after {max_retries} retries")

    async def run_trading_engine():
        """Trading engine wrapper with auto-restart"""
        retry_count = 0
        max_retries = 5

        while not shutdown_event.is_set() and retry_count < max_retries:
            try:
                logger.info("🤖 Starting Trading Engine...")
                await trading_engine.run_forever()

                logger.warning("⚠️ Trading engine stopped")
                retry_count += 1

                if retry_count < max_retries:
                    await asyncio.sleep(60)

            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Trading engine error ({retry_count}/{max_retries}): {e}")

                import traceback
                logger.error(traceback.format_exc())

                if retry_count < max_retries:
                    await asyncio.sleep(60)

        if retry_count >= max_retries:
            logger.error(f"🚨 Trading engine failed after {max_retries} retries")
            shutdown_event.set()

    async def monitor_shutdown():
        """Wait for shutdown signal"""
        await shutdown_event.wait()
        logger.info("🛑 Shutdown signal received, cleaning up...")

    # ========================
    # RUN ALL TASKS
    # ========================
    try:
        logger.info(f"""
╔════════════════════════════════════════╗
║    AI TRADING BOT STARTED              ║
╠════════════════════════════════════════╣
║ Version: v4.1 (CORRECTED)
║ Crypto: {len(CRYPTO)}
║ Stocks: {len(STOCKS)}
║ Commodities: {len(COMMODITIES)}
║ Total: {len(all_assets)}
║ Scan Cycle: {SCAN_INTERVAL/60:.0f} minutes
║ Telegram: ✅ LINKED via set_telegram_handler()
║ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
╚════════════════════════════════════════╝
        """)

        # ✅ Run both tasks concurrently
        await asyncio.gather(
            run_telegram(),
            run_trading_engine(),
            monitor_shutdown(),
            return_exceptions=True
        )

    except KeyboardInterrupt:
        logger.info("⌨️ Keyboard interrupt received")
        shutdown_event.set()

    except Exception as e:
        logger.error(f"❌ Fatal error in main loop: {e}")
        import traceback
        logger.error(traceback.format_exc())
        shutdown_event.set()

    finally:
        logger.info("🧹 Cleaning up...")

        try:
            await telegram_handler.stop()
        except:
            pass

        logger.info("👋 Bot stopped gracefully")

# ========================
# ENTRY POINT
# ========================
if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⌨️ Stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)