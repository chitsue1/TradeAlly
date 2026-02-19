"""
═══════════════════════════════════════════════════════════════════════════════
TRADE ALLY BOT — MAIN v3.0
═══════════════════════════════════════════════════════════════════════════════
Startup sequence:
1. Validate config
2. TradingEngine
3. TelegramHandler
4. Bidirectional link
5. Run all in parallel
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
import logging.handlers
import signal
import sys
from datetime import datetime

from config import validate_config, LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT
from trading_engine import TradingEngine
from telegram_handler import TelegramHandler


# ═══════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════

def setup_logging():
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handlers = [logging.StreamHandler(sys.stdout)]

    try:
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        handlers.append(fh)
    except Exception as e:
        print(f"⚠️ File log failed: {e}")

    for h in handlers:
        if not isinstance(h, logging.handlers.RotatingFileHandler):
            h.setFormatter(fmt)

    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)

    # Quiet noisy libs
    for lib in ("httpx", "telegram", "anthropic", "aiohttp"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    return logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    logger = setup_logging()

    logger.info("=" * 65)
    logger.info("🚀 TRADE ALLY BOT v3.0 — PRODUCTION")
    logger.info(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 65)

    if not validate_config():
        logger.error("❌ Config invalid — check environment variables")
        sys.exit(1)

    # ── 1. Trading Engine ──────────────────────────────────────────────────
    logger.info("\n[1/2] Initializing TradingEngine...")
    engine = TradingEngine()

    # ── 2. Telegram Handler ────────────────────────────────────────────────
    logger.info("\n[2/2] Initializing TelegramHandler...")
    tg = TelegramHandler(trading_engine=engine)

    # ── Bidirectional link ─────────────────────────────────────────────────
    engine.set_telegram_handler(tg)

    logger.info("\n" + "=" * 65)
    logger.info("✅ ALL SYSTEMS READY")
    logger.info("=" * 65 + "\n")

    # ── Graceful shutdown ──────────────────────────────────────────────────
    stop_event = asyncio.Event()

    def _shutdown(sig, frame):
        logger.info(f"\n⚠️  Signal {sig} — shutting down...")
        stop_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # ── Run tasks ─────────────────────────────────────────────────────────
    tasks = [
        asyncio.create_task(engine.run_forever(),     name="engine"),
        asyncio.create_task(tg.start(),               name="telegram"),
        asyncio.create_task(stop_event.wait(),        name="shutdown"),
    ]

    logger.info("🟢 All systems running!\n")

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for task in done:
        if task.exception():
            logger.error(f"💥 Task '{task.get_name()}' crashed: {task.exception()}")

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    logger.info("🔴 Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏸️  Interrupted")
    except Exception as e:
        print(f"\n❌ Fatal: {e}")
        sys.exit(1)
