"""
AI Trading Bot - Main Entry Point (Production-Ready)
Fixed: Async orchestration, error handling, Railway compatibility
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
# MAIN ORCHESTRATOR
# ========================
async def main():
    """
    Production-grade async orchestration

    Architecture:
    - Telegram bot runs in background task
    - Trading engine runs in background task
    - Both tasks monitored and restarted on failure
    - Graceful shutdown on SIGTERM (Railway compatibility)
    """

    logger.info("🚀 AI Trading Bot ინიციალიზაცია...")

    # Initialize components
    try:
        telegram_handler = TelegramHandler()
        trading_engine = TradingEngine()

        # Count assets
        all_assets = CRYPTO + STOCKS + COMMODITIES
        logger.info(f"✅ ჩატვირთულია {len(all_assets)} აქტივი მონიტორინგისთვის")

    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
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

                # If we get here, telegram stopped unexpectedly
                logger.warning("⚠️ Telegram handler stopped")
                retry_count += 1

                if retry_count < max_retries:
                    await asyncio.sleep(30)  # Wait before retry

            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Telegram error ({retry_count}/{max_retries}): {e}")

                if retry_count < max_retries:
                    await asyncio.sleep(30)

        logger.error(f"🚨 Telegram handler failed after {max_retries} retries")

    async def run_trading_engine():
        """Trading engine wrapper with auto-restart"""
        retry_count = 0
        max_retries = 5

        while not shutdown_event.is_set() and retry_count < max_retries:
            try:
                logger.info("🤖 Starting Trading Engine...")
                await trading_engine.run_forever()

                # If we get here, engine stopped unexpectedly
                logger.warning("⚠️ Trading engine stopped")
                retry_count += 1

                if retry_count < max_retries:
                    await asyncio.sleep(60)  # Wait before retry

            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Trading engine error ({retry_count}/{max_retries}): {e}")

                if retry_count < max_retries:
                    await asyncio.sleep(60)

        logger.error(f"🚨 Trading engine failed after {max_retries} retries")
        shutdown_event.set()  # Shutdown everything if engine dies

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
║ Version: v3.0 (Multi-Source)
║ Crypto: {len(CRYPTO)}
║ Stocks: {len(STOCKS)}
║ Commodities: {len(COMMODITIES)}
║ Total: {len(all_assets)}
║ Scan Cycle: {SCAN_INTERVAL/60:.0f} minutes
║ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
╚════════════════════════════════════════╝
        """)

        # ✅ KEY FIX: Run both tasks concurrently (not sequentially)
        await asyncio.gather(
            run_telegram(),
            run_trading_engine(),
            monitor_shutdown(),
            return_exceptions=True  # Don't crash if one fails
        )

    except KeyboardInterrupt:
        logger.info("⌨️ Keyboard interrupt received")
        shutdown_event.set()

    except Exception as e:
        logger.error(f"❌ Fatal error in main loop: {e}")
        shutdown_event.set()

    finally:
        logger.info("🧹 Cleaning up...")

        # Cleanup telegram
        try:
            await telegram_handler.stop()
        except:
            pass

        logger.info("👋 Bot stopped gracefully")

# ========================
# ENTRY POINT
# ========================
if __name__ == "__main__":
    # Register signal handlers (Railway sends SIGTERM on shutdown)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⌨️ Stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)