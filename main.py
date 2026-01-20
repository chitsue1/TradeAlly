"""
AI Trading Bot - Main Entry Point (Twelve Data Optimized)
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

from config import *
from trading_engine import TradingEngine
from telegram_handler import TelegramHandler

class AITradingBot:
    def __init__(self):
        logger.info("🚀 AI Trading Bot ინიციალიზაცია...")
        os.makedirs(PDF_FOLDER, exist_ok=True)

        self.trading_engine = TradingEngine()
        self.telegram_handler = TelegramHandler(self.trading_engine)

        # ყველა აქტივის გაერთიანება ერთ სიაში სკანირებისთვის
        self.all_assets = CRYPTO + STOCKS + COMMODITIES
        logger.info(f"✅ ჩატვირთულია {len(self.all_assets)} აქტივი მონიტორინგისთვის")

    async def analyze_and_notify(self):
        """Main analysis loop - Twelve Data-ზე ოპტიმიზირებული"""
        active_subscribers = self.telegram_handler.get_active_subscribers()

        if not active_subscribers:
            logger.info("⏸️ არ არის აქტიური გამომწერები - სკანირება შეჩერებულია")
            return

        sentiment_data = await self.trading_engine.get_market_sentiment()

        logger.info(f"\n🧠 AI სკანირება იწყება: {len(self.all_assets)} აქტივი | Fear&Greed: {sentiment_data['fg_index']}")

        scanned = 0
        errors = 0

        for asset in self.all_assets:
            try:
                # 1. მონაცემების წამოღება (Twelve Data)
                data = await self.trading_engine.fetch_data(asset)

                if not data:
                    errors += 1
                    await asyncio.sleep(ASSET_DELAY)
                    continue

                scanned += 1

                # 2. პოზიციის შემოწმება (Exit ლოგიკა)
                if asset in self.trading_engine.active_positions:
                    await self.check_exit_conditions(asset, data, sentiment_data)
                else:
                    # 3. ანალიზი შესვლისთვის (Entry ლოგიკა)
                    ai_score, ai_reasons = await self.trading_engine.ai_analyze_signal(
                        asset, data, sentiment_data
                    )

                    if ai_score >= AI_ENTRY_THRESHOLD:
                        # სიახლეების ვალიდაცია
                        is_clean = await self.trading_engine.get_comprehensive_news(asset)
                        if is_clean:
                            await self.create_buy_signal(asset, data, sentiment_data, ai_score, ai_reasons)
                        else:
                            logger.info(f"📰 უარყოფითი სიახლეები, გამოტოვება: {asset}")

                # 4. კრიტიკული დაყოვნება Twelve Data-ს ლიმიტისთვის
                await asyncio.sleep(ASSET_DELAY)

            except Exception as e:
                logger.error(f"❌ შეცდომა {asset}-ზე: {e}")
                errors += 1
                await asyncio.sleep(ASSET_DELAY)

        logger.info(f"✅ ციკლი დასრულდა - სკანირებული: {scanned}/{len(self.all_assets)}")

    async def create_buy_signal(self, asset, data, sentiment, ai_score, ai_reasons):
        """სიგნალის შექმნა და დაგზავნა"""
        self.trading_engine.active_positions[asset] = {
            "entry_price": data['price'],
            "entry_time": asyncio.get_event_loop().time(),
            "entry_rsi": data['rsi'],
            "ai_score": ai_score
        }

        estimated_tp = self.trading_engine.calculate_dynamic_tp(data, sentiment)
        reasons_text = "\n".join([f"• {r}" for r in ai_reasons])
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

        await self.telegram_handler.broadcast_signal(message, asset)
        self.trading_engine.stats['total_signals'] += 1
        logger.info(f"🟢 BUY სიგნალი: {asset}")

    async def check_exit_conditions(self, asset, data, sentiment):
        """გასვლის პირობების შემოწმება"""
        position = self.trading_engine.active_positions[asset]
        profit_percent = ((data['price'] - position['entry_price']) / position['entry_price']) * 100
        hours_held = (asyncio.get_event_loop().time() - position['entry_time']) / 3600

        should_exit = False
        reason = ""

        if profit_percent <= -STOP_LOSS_PERCENT:
            should_exit, reason = True, f"🔴 STOP-LOSS ({profit_percent:.2f}%)"
        elif profit_percent >= TAKE_PROFIT_PERCENT:
            should_exit, reason = True, f"🟢 TAKE-PROFIT (+{profit_percent:.2f}%)"
        elif hours_held >= MAX_HOLD_HOURS:
            should_exit, reason = True, "⏰ დროის ლიმიტი"
        elif data['rsi'] > 75:
            should_exit, reason = True, f"📈 RSI Overbought ({data['rsi']:.1f})"

        if should_exit:
            await self.create_sell_signal(asset, position['entry_price'], data['price'], profit_percent, hours_held, reason)

    async def create_sell_signal(self, asset, entry_price, exit_price, profit_percent, hours_held, reason):
        balance_1usd = 1.0 * (1 + (profit_percent / 100))
        emoji = "🔴" if profit_percent < 0 else "🟢"

        message = SELL_SIGNAL_TEMPLATE.format(
            emoji=emoji, asset=asset, asset_type=self.trading_engine.get_asset_type(asset),
            entry_price=entry_price, exit_price=exit_price, profit=profit_percent,
            balance=balance_1usd, hours=hours_held, reason=reason
        )

        if profit_percent > 0: self.trading_engine.stats['successful_trades'] += 1
        else: self.trading_engine.stats['failed_trades'] += 1

        del self.trading_engine.active_positions[asset]
        await self.telegram_handler.broadcast_signal(message, asset)

    async def send_startup_message(self):
        startup_msg = (
            "💎 AI Trading Bot v2.0 (Twelve Data Edition) Акტიურია\n"
            f"📊 მონიტორინგი: {len(self.all_assets)} აქტივი\n"
            f"⏱️ ციკლი: ~{(len(self.all_assets) * ASSET_DELAY) / 60:.1f} წუთი"
        )
        try: await self.telegram_handler.bot.send_message(chat_id=ADMIN_ID, text=startup_msg)
        except: pass
        logger.info(startup_msg)

    async def run(self):
        try:
            await self.telegram_handler.start()
            await self.send_startup_message()
            while True:
                await self.analyze_and_notify()
                await asyncio.sleep(SCAN_INTERVAL)
        except Exception as e:
            logger.error(f"🚨 კრიტიკული შეცდომა: {e}")

async def main():
    bot = AITradingBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
