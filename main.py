"""
═══════════════════════════════════════════════════════════════════════════════
TRADE ALLY BOT — MAIN v3.1 FIXED
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
import logging.handlers
import sys
from datetime import datetime

from config import validate_config, LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT


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
        h.setFormatter(fmt)

    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)

    for lib in ("httpx", "telegram", "anthropic", "aiohttp"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    return logging.getLogger(__name__)


async def main():
    logger = setup_logging()

    logger.info("=" * 65)
    logger.info("🚀 TRADE ALLY BOT v3.1 — PRODUCTION")
    logger.info(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 65)

    if not validate_config():
        logger.error("❌ Config invalid — set env variables in Railway dashboard")
        sys.exit(1)

    # Import here — AFTER logging is set up, so errors are visible
    try:
        from trading_engine import TradingEngine
        logger.info("✅ TradingEngine imported")
    except Exception as e:
        logger.error(f"❌ TradingEngine import failed: {e}")
        sys.exit(1)

    try:
        from telegram_handler import TelegramHandler
        logger.info("✅ TelegramHandler imported")
    except Exception as e:
        logger.error(f"❌ TelegramHandler import failed: {e}")
        sys.exit(1)

    logger.info("[1/2] Initializing TradingEngine...")
    try:
        engine = TradingEngine()
    except Exception as e:
        logger.error(f"❌ TradingEngine init failed: {e}")
        sys.exit(1)

    logger.info("[2/2] Initializing TelegramHandler...")
    try:
        tg = TelegramHandler(trading_engine=engine)
    except Exception as e:
        logger.error(f"❌ TelegramHandler init failed: {e}")
        sys.exit(1)

    engine.set_telegram_handler(tg)

    logger.info("=" * 65)
    logger.info("✅ ALL SYSTEMS READY — starting...")
    logger.info("=" * 65)

    # Run engine + telegram concurrently
    try:
        await asyncio.gather(
            engine.run_forever(),
            tg.start(),
        )
    except KeyboardInterrupt:
        logger.info("⚠️ KeyboardInterrupt — shutting down")
    except Exception as e:
        logger.error(f"❌ Fatal runtime error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏸️ Interrupted")
    except Exception as e:
        print(f"\n❌ Fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
