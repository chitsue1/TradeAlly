"""
AI Trading Bot - Main Entry Point
ძმაკაცო, აქ ყველაფერი ერთად უერთდება! 🚀
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our modules
from config import *
from trading_engine import TradingEngine
from telegram_handler import TelegramHandler


class AITradingBot:
    """Main bot orchestrator"""

    def __init__(self):
        logger.info("🚀 AI Trading Bot ინიციალიზაცია...")

        # Create directories
        os.makedirs(PDF_FOLDER, exist_ok=True)

        # Initialize components
        self.trading_engine = TradingEngine()
        self.telegram_handler = TelegramHandler(self.trading_engine)

        logger.info("✅ ყველა კომპონენტი ჩატვირთულია")

    async def analyze_and_notify(self):
        """Main analysis loop"""
        active_subscribers = self.telegram_handler.get_active_subscribers()

        if not active_subscribers:
            logger.info("⏸️ არ არის აქტიური გამომწერები - სკანირება შეჩერებულია")
            return

        # Get sentiment once per cycle
        try:
            sentiment_data = await self.trading_engine.get_market_sentiment()
            logger.info(
                f"\n🧠 AI სკანირება: {len(CRYPTO)} crypto | "
                f"Fear&Greed: {sentiment_data['fg_index']} ({sentiment_data['fg_class']})"
            )
        except Exception as e:
            logger.error(f"Sentiment fetch error: {e}")
            # Default fallback sentiment
            sentiment_data = {"fg_index": 50, "fg_class": "ნეიტრალური", "market_trend": 0}

        # Scan only CRYPTO
        scanned = 0
        errors = 0

        for asset in CRYPTO:
            try:
                # Fetch data
                data = await self.trading_engine.fetch_data(asset)

                if not data:
                    errors += 1
                    if errors > 5:
                        logger.warning("⚠️ ბევრი შეცდომა - 30s დაყოვნება")
                        await asyncio.sleep(30)
                        errors = 0
                    await asyncio.sleep(ASSET_DELAY)
                    continue

                scanned += 1

                # Check existing positions
                if asset in self.trading_engine.active_positions:
                    await self.check_exit_conditions(asset, data, sentiment_data)
                else:
                    # Analyze for entry
                    ai_score, ai_reasons = await self.trading_engine.ai_analyze_signal(
                        asset, data, sentiment_data
                    )

                    # Entry threshold
                    if ai_score >= AI_ENTRY_THRESHOLD:
                        # News validation
                        is_clean = await self.trading_engine.get_comprehensive_news(asset)

                        if is_clean:
                            await self.create_buy_signal(asset, data, sentiment_data, ai_score, ai_reasons)
                        else:
                            logger.info(f"📰 უარყოფითი სიახლეები: {asset}")

                await asyncio.sleep(ASSET_DELAY)

            except IndexError as e:
                logger.error(f"Index error {asset}: {e}")
                errors += 1
                continue
            except KeyError as e:
                logger.error(f"Key error {asset}: {e}")
                errors += 1
                continue
            except Exception as e:
                logger.error(f"ანალიზის შეცდომა {asset}: {e}")
                errors += 1
                continue

        logger.info(f"✅ ციკლი დასრულდა - სკანირებული: {scanned}/{len(CRYPTO)} - პაუზა {SCAN_INTERVAL}s")

    async def create_buy_signal(self, asset, data, sentiment, ai_score, ai_reasons):
        """Create and broadcast buy signal"""
        # Create position
        self.trading_engine.active_positions[asset] = {
            "entry_price": data['price'],
            "entry_time": asyncio.get_event_loop().time(),
            "entry_rsi": data['rsi'],
            "ai_score": ai_score
        }

        # Calculate dynamic TP
        estimated_tp = self.trading_engine.calculate_dynamic_tp(data, sentiment)

        # Format reasons
        reasons_text = "\n".join([f"• {r}" for r in ai_reasons[:6]])

        # Build message
        asset_type = self.trading_engine.get_asset_type(asset)

        message = BUY_SIGNAL_TEMPLATE.format(
            asset=asset,
            asset_type=asset_type,
            price=data['price'],
            rsi=data['rsi'],
            ema200=data['ema200'],
            ai_score=ai_score,
            fg_index=sentiment['fg_index'],
            fg_class=sentiment['fg_class'],
            reasons=reasons_text,
            sl_percent=STOP_LOSS_PERCENT,
            tp_percent=TAKE_PROFIT_PERCENT,
            estimated_tp=estimated_tp
        )

        # Broadcast
        await self.telegram_handler.broadcast_signal(message, asset)

        # Update stats
        self.trading_engine.stats['total_signals'] += 1

        logger.info(f"🟢 BUY სიგნალი: {asset} | Score: {ai_score}")

    async def check_exit_conditions(self, asset, data, sentiment):
        """Check exit conditions for active position"""
        position = self.trading_engine.active_positions[asset]
        entry_price = position['entry_price']
        current_price = data['price']
        profit_percent = ((current_price - entry_price) / entry_price) * 100

        # Calculate hours held
        current_time = asyncio.get_event_loop().time()
        hours_held = (current_time - position['entry_time']) / 3600

        should_exit = False
        exit_reason = ""

        # 1. Stop Loss
        if profit_percent <= -STOP_LOSS_PERCENT:
            should_exit = True
            exit_reason = f"🔴 STOP-LOSS (-{abs(profit_percent):.2f}%)"

        # 2. Take Profit
        elif profit_percent >= TAKE_PROFIT_PERCENT:
            should_exit = True
            exit_reason = f"🟢 TAKE-PROFIT (+{profit_percent:.2f}%)"

        # 3. Enhanced exits
        elif profit_percent < -3 and data["rsi"] < 25:
            should_exit = True
            exit_reason = f"⚠️ ძლიერი ვარდნა + RSI ({data['rsi']:.1f})"

        elif hours_held >= MAX_HOLD_HOURS:
            should_exit = True
            exit_reason = f"⏰ დროის ლიმიტი ({MAX_HOLD_HOURS}სთ)"

        elif data["rsi"] > 75:
            should_exit = True
            exit_reason = f"📈 RSI ძალიან overbought ({data['rsi']:.1f})"

        elif data["price"] >= data["bb_high"] and data["rsi"] > 65:
            should_exit = True
            exit_reason = "📈 Bollinger ზედა ზოლი + RSI"

        # 4. AI patterns
        elif not should_exit:
            for k in self.trading_engine.trading_knowledge.get("patterns", []):
                if "bearish" in k.lower() and ("reversal" in k.lower() or "top" in k.lower()):
                    if data["rsi"] > 70:
                        should_exit = True
                        exit_reason = "🧠 AI: Bearish Reversal"
                        break

        # 5. Trailing stop
        elif not should_exit and profit_percent > 15:
            trailing_stop = entry_price * 1.12
            if current_price < trailing_stop:
                should_exit = True
                exit_reason = f"📊 Trailing Stop (+{profit_percent:.2f}%)"

        # 6. Extreme greed
        elif not should_exit and sentiment['fg_index'] > 85 and profit_percent > 5:
            should_exit = True
            exit_reason = f"🚨 ექსტრემალური სიხარბე ({sentiment['fg_index']})"

        if should_exit:
            await self.create_sell_signal(asset, entry_price, current_price, profit_percent, hours_held, exit_reason)

    async def create_sell_signal(self, asset, entry_price, exit_price, profit_percent, hours_held, reason):
        """Create and broadcast sell signal"""
        balance_1usd = 1.0 * (1 + (profit_percent / 100))
        asset_type = self.trading_engine.get_asset_type(asset)
        emoji = "🔴" if profit_percent < 0 else "🟢"

        message = SELL_SIGNAL_TEMPLATE.format(
            emoji=emoji,
            asset=asset,
            asset_type=asset_type,
            entry_price=entry_price,
            exit_price=exit_price,
            profit=profit_percent,
            balance=balance_1usd,
            hours=hours_held,
            reason=reason
        )

        # Update stats
        if profit_percent > 0:
            self.trading_engine.stats['successful_trades'] += 1
        else:
            self.trading_engine.stats['failed_trades'] += 1

        self.trading_engine.stats['total_profit_percent'] += profit_percent

        # Remove position
        del self.trading_engine.active_positions[asset]

        # Broadcast
        await self.telegram_handler.broadcast_signal(message, asset)

        logger.info(f"🔔 SELL სიგნალი: {asset} | მოგება: {profit_percent:+.2f}%")

    async def send_startup_message(self):
        """Send startup notification to all subscribers"""
        ai_info = (
            f"{len(self.trading_engine.trading_knowledge.get('patterns', []))} ნიმუში"
            if self.trading_engine.trading_knowledge.get("patterns")
            else "ბაზა"
        )

        startup_msg = (
            "💎 AI Trading Bot აქტიურია\n"
            f"🧠 AI: {ai_info}\n\n"
            "📊 მონიტორინგი:\n"
            f"🔸 {len(CRYPTO)} კრიპტო\n\n"
            "━━━━━━━━━━━━━━━━\n"
            f"📡 სულ: {len(CRYPTO)} აქტივი\n"
            f"⏱️ ციკლი: ~{len(CRYPTO) * ASSET_DELAY / 60:.0f}წთ\n"
            f"👥 გამომწერები: {len(self.telegram_handler.subscriptions)}\n\n"
            "🚀 AI-powered ანალიზი აქტიურია!"
        )

        # Send to all subscribers
        for user_id in self.telegram_handler.subscriptions.keys():
            try:
                await self.telegram_handler.bot.send_message(
                    chat_id=user_id,
                    text=startup_msg
                )
            except:
                pass

        logger.info(startup_msg)
        logger.info("\n" + "=" * 50 + "\n")

    async def run(self):
        """Main run loop"""
        try:
            # Start Telegram bot
            await self.telegram_handler.start()

            # Send startup notification
            await self.send_startup_message()

            # Main loop
            while True:
                try:
                    await self.analyze_and_notify()
                    await asyncio.sleep(SCAN_INTERVAL)
                except Exception as e:
                    logger.error(f"🚨 Loop error: {e}")
                    await asyncio.sleep(60)

        except KeyboardInterrupt:
            logger.info("👋 ბოტი ჩერდება...")
        except Exception as e:
            logger.error(f"🚨 კრიტიკული შეცდომა: {e}")
            raise
        finally:
            # Cleanup resources
            await self.trading_engine.cleanup()


async def main():
    """Entry point"""
    print("""
    ╔══════════════════════════════════════╗
    ║   🤖 AI Trading Bot v2.0            ║
    ║   Made with ❤️ by Claude            ║
    ╚══════════════════════════════════════╝
    """)

    # Initialize and run
    bot = AITradingBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 ნახვამდის!")
    except Exception as e:
        logger.error(f"🚨 Fatal error: {e}")
        sys.exit(1)