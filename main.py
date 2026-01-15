import os
import asyncio
import pandas as pd
import yfinance as yf
import feedparser
import telegram
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
import time
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
import json

# --- CONFIGURATION ---
TELEGRAM_TOKEN = "8458601706:AAHlZaQS7NsnDENNn610cRknqOyJdW6InyA"

# 🆕 ახალი: subscribers ფაილი სადაც ყველა მომხმარებელი ინახება
SUBSCRIBERS_FILE = "subscribers.json"

# ოპტიმიზირებული აქტივების სია: 90 აქტივი (40 კრიპტო, 28 აქცია, 22 საქონელი)

# 40 კრიპტო
CRYPTO = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "DOT-USD",
    "AVAX-USD", "MATIC-USD", "LINK-USD", "UNI-USD", "ATOM-USD", "LTC-USD", "XLM-USD", 
    "BCH-USD", "ALGO-USD", "VET-USD", "ICP-USD", "FIL-USD", "HBAR-USD", "APT-USD", 
    "TRX-USD", "NEAR-USD", "INJ-USD", "ARB-USD", "OP-USD", "RNDR-USD", "IMX-USD", "PEPE-USD",
    "TIA-USD", "SEI-USD", "SUI-USD", "KAS-USD", "JTO-USD", "PYTH-USD", "BLUR-USD", 
    "LDO-USD", "RUNE-USD", "FET-USD"
]

# 28 აქცია
STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "TSM", "JPM", "BAC",
    "UNH", "JNJ", "WMT", "HD", "XOM", "CVX", "AMD", "INTC", "ASML", "SMCI", "AVGO",
    "ARM", "LLY", "NVO", "COST", "PANW", "CRWD", "UBER"
]

# 22 საქონელი
COMMODITIES = [
    "GC=F", "SI=F", "CL=F", "NG=F", "ZC=F", "ZW=F", "ZS=F", "ES=F", "NQ=F",
    "DX=F", "6E=F", "HG=F", "ZN=F", "ZF=F", "VX=F", "RTY=F", "YM=F",
    "PL=F", "PA=F", "KC=F", "SB=F", "USO"
]

ASSETS = CRYPTO + STOCKS + COMMODITIES

INTERVAL = "1h"
SCAN_INTERVAL = 90
ASSET_DELAY = 4
NOTIFICATION_COOLDOWN = 7200

# გაფართოებული ნიუსების წყაროები
RSS_FEEDS = [
    "https://cryptopanic.com/news/rss/",
    "https://cointelegraph.com/rss",
    "https://www.investing.com/rss/news.rss",
    "https://www.cnbc.com/id/10000311/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.kitco.com/rss/KitcoNews.xml"
]

class ProTraderBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.bot = self.application.bot
        self.active_positions = {}
        self.last_notifications = {}
        self.request_count = 0
        self.start_time = time.time()

        # 🆕 ახალი: subscribers-ის მენეჯმენტი
        self.subscribers = self.load_subscribers()

        # 🆕 ახალი: ბრძანებების დამატება
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("stop", self.cmd_stop))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))

    # 🆕 ახალი ფუნქცია: subscribers-ის ჩატვირთვა ფაილიდან
    def load_subscribers(self):
        """იტვირთავს subscribers-ის სიას ფაილიდან"""
        try:
            if os.path.exists(SUBSCRIBERS_FILE):
                with open(SUBSCRIBERS_FILE, 'r') as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            print(f"⚠️ Error loading subscribers: {e}")
            return set()

    # 🆕 ახალი ფუნქცია: subscribers-ის შენახვა ფაილში
    def save_subscribers(self):
        """ინახავს subscribers-ის სიას ფაილში"""
        try:
            with open(SUBSCRIBERS_FILE, 'w') as f:
                json.dump(list(self.subscribers), f)
        except Exception as e:
            print(f"⚠️ Error saving subscribers: {e}")

    # 🆕 ახალი ფუნქცია: /start ბრძანება
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """მომხმარებელი რეგისტრირდება სიგნალებისთვის"""
        user_id = update.effective_chat.id
        username = update.effective_user.username or "User"

        if user_id not in self.subscribers:
            self.subscribers.add(user_id)
            self.save_subscribers()

            welcome_msg = (
                f"🎉 გამარჯობა @{username}!\n\n"
                f"✅ წარმატებით დარეგისტრირდი!\n\n"
                f"📊 ახლა მიიღებ ყველა ტრეიდინგ სიგნალს:\n"
                f"🔸 {len(CRYPTO)} კრიპტოვალუტა\n"
                f"🔸 {len(STOCKS)} აქცია\n"
                f"🔸 {len(COMMODITIES)} საქონელი/ფიუჩერსი\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📡 სულ: {len(ASSETS)} აქტივი\n"
                f"⏱️ სრული ციკლი: ~{len(ASSETS) * ASSET_DELAY / 60:.0f}წთ\n\n"
                f"📌 ბრძანებები:\n"
                f"/start - რეგისტრაცია\n"
                f"/stop - გამორთვა\n"
                f"/stats - სტატისტიკა"
            )

            await update.message.reply_text(welcome_msg)
            print(f"✅ ახალი subscriber: {user_id} (@{username}) - სულ: {len(self.subscribers)}")
        else:
            await update.message.reply_text(
                f"👋 @{username}, შენ უკვე ხარ დარეგისტრირებული!\n\n"
                f"📊 მიიღებ ყველა სიგნალს რეალურ დროში."
            )

    # 🆕 ახალი ფუნქცია: /stop ბრძანება
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """მომხმარებელი გამოიწერს სიგნალებიდან"""
        user_id = update.effective_chat.id
        username = update.effective_user.username or "User"

        if user_id in self.subscribers:
            self.subscribers.remove(user_id)
            self.save_subscribers()
            await update.message.reply_text(
                f"👋 @{username}, წარმატებით გამოიწერე!\n\n"
                f"თუ ისევ გინდა სიგნალების მიღება, დაწერე /start"
            )
            print(f"❌ Subscriber removed: {user_id} (@{username}) - დარჩა: {len(self.subscribers)}")
        else:
            await update.message.reply_text("⚠️ შენ არ ხარ დარეგისტრირებული. დაწერე /start რეგისტრაციისთვის.")

    # 🆕 ახალი ფუნქცია: /stats ბრძანება
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """აჩვენებს ბოტის სტატისტიკას"""
        stats_msg = (
            f"📊 ბოტის სტატისტიკა:\n\n"
            f"👥 მომხმარებლები: {len(self.subscribers)}\n"
            f"📈 აქტიური პოზიციები: {len(self.active_positions)}\n"
            f"📡 მონიტორინგი: {len(ASSETS)} აქტივი\n"
            f"⏱️ ციკლის ხანგრძლივობა: ~{len(ASSETS) * ASSET_DELAY / 60:.0f}წთ"
        )
        await update.message.reply_text(stats_msg)

    def get_asset_type(self, symbol):
        """განსაზღვრავს აქტივის კატეგორიას"""
        if symbol in CRYPTO:
            return "💎 CRYPTO"
        elif symbol in STOCKS:
            return "📈 STOCK"
        elif symbol in COMMODITIES:
            return "🏆 COMMODITY"
        else:
            return "📊 ASSET"

    async def get_comprehensive_news(self, asset_name):
        """აანალიზებს ნიუსებს კონკრეტული აქტივისთვის"""
        negative_impact = 0
        keywords = ['crash', 'hacked', 'scam', 'fraud', 'lawsuit', 'bankruptcy', 'bearish', 
                    'plunge', 'collapse', 'ban', 'regulation', 'crackdown', 'seizure']

        for url in RSS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]:
                    title = entry.get('title', '').lower()
                    summary = entry.get('summary', '').lower()
                    content = title + ' ' + summary

                    if asset_name.lower() in content:
                        if any(word in content for word in keywords):
                            negative_impact += 1
            except: 
                continue

        return negative_impact == 0

    async def fetch_data(self, symbol):
        """იღებს მონაცემებს და ითვლის ინდიკატორებს - Rate Limit Protection"""
        try:
            # Rate limit tracker (60 requests per minute max)
            self.request_count += 1
            if self.request_count > 50 and (time.time() - self.start_time) < 60:
                print(f"⏸️ Rate limit precaution - pausing 10 seconds...")
                await asyncio.sleep(10)
                self.request_count = 0
                self.start_time = time.time()

            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1mo", interval=INTERVAL)

            if len(df) < 200: 
                return None

            close = df['Close']
            ema200 = EMAIndicator(close, window=200).ema_indicator().iloc[-1]
            rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
            bb = BollingerBands(close, window=20, window_dev=2)

            return {
                "price": close.iloc[-1],
                "ema200": ema200,
                "rsi": rsi,
                "bb_low": bb.bollinger_lband().iloc[-1],
                "bb_high": bb.bollinger_hband().iloc[-1]
            }
        except Exception as e:
            print(f"⚠️ Error fetching {symbol}: {e}")
            return None

    async def analyze_and_notify(self):
        cycle_start = time.time()
        print(f"\n🕵️ სკანირება დაწყებულია: {len(ASSETS)} აქტივი...")
        print(f"👥 აქტიური მომხმარებლები: {len(self.subscribers)}")
        print(f"⏱️ მოსალოდნელი დრო: ~{len(ASSETS) * ASSET_DELAY / 60:.1f} წუთი\n")

        processed = 0
        for asset in ASSETS:
            processed += 1
            print(f"📊 [{processed}/{len(ASSETS)}] სკანირდება: {asset}...")

            data = await self.fetch_data(asset)
            if not data: 
                await asyncio.sleep(ASSET_DELAY)
                continue

            # გამოცდილი ტრეიდერის ლოგიკა: 
            # 1. ტრენდი არის Bullish (ფასი > EMA200)
            # 2. ფასი არის გადაყიდული (RSI < 38) ან ეხება ბოლინჯერის ქვედა ზღვარს
            if data['price'] > data['ema200'] and (data['rsi'] < 38 or data['price'] <= data['bb_low']):
                if asset not in self.active_positions:
                    print(f"  🔍 BUY სიგნალი - ვამოწმებ ნიუსებს...")
                    is_clean = await self.get_comprehensive_news(asset)
                    if is_clean:
                        self.active_positions[asset] = data['price']
                        asset_type = self.get_asset_type(asset)
                        msg = (f"🟢 იყიდე: {asset} [{asset_type}]\n"
                               f"ფასი: ${data['price']:.2f}\n"
                               f"RSI: {data['rsi']:.1f}\n"
                               f"EMA200: ${data['ema200']:.2f}\n\n"
                               f"მიზეზი: ფასი ინარჩუნებს ზრდის ტრენდს (EMA200) და ამჟამად იმყოფება ხელსაყრელ დაბალ წერტილზე (RSI: {data['rsi']:.1f}). "
                               f"ნიუსების ფონი სტაბილურია, რაც ზრდის ალბათობას.")
                        await self.broadcast_message(msg, asset)
                    else:
                        print(f"  ⚠️ ნეგატიური ნიუსების გამო დაბლოკილია")

            # გაყიდვის ლოგიკა
            elif asset in self.active_positions:
                if data['rsi'] > 65 or data['price'] >= data['bb_high']:
                    entry_price = self.active_positions[asset]
                    profit = ((data['price'] - entry_price) / entry_price) * 100
                    balance_1usd = 1.0 * (1 + (profit / 100))
                    asset_type = self.get_asset_type(asset)

                    msg = (f"🔴 გაყიდე: {asset} [{asset_type}]\n"
                           f"შესვლის ფასი: ${entry_price:.2f}\n"
                           f"გასასვლელი ფასი: ${data['price']:.2f}\n"
                           f"მოგება: {profit:.2f}%\n"
                           f"1$-ის ბალანსი: ${balance_1usd:.4f}")

                    del self.active_positions[asset]
                    await self.broadcast_message(msg, asset)
                    print(f"  💰 SELL სიგნალი - მოგება: {profit:.2f}%")

            # Yahoo Finance-ის დასაცავად - 4 წამიანი პაუზა თითოეულ აქტივს შორის
            await asyncio.sleep(ASSET_DELAY)

        cycle_duration = time.time() - cycle_start
        print(f"\n✅ ციკლი დასრულდა: {cycle_duration/60:.1f} წუთში")
        print(f"📊 აქტიური პოზიციები: {len(self.active_positions)}\n")

    # 🆕 ახალი ფუნქცია: ყველა subscriber-ზე გაგზავნა
    async def broadcast_message(self, message, asset):
        """გაგზავნის შეტყობინებას ყველა დარეგისტრირებულ მომხმარებელზე"""
        now = time.time()
        if now - self.last_notifications.get(asset, 0) > NOTIFICATION_COOLDOWN:
            success_count = 0
            failed_count = 0

            # ყველა subscriber-ისთვის გაგზავნა
            for user_id in list(self.subscribers):
                try:
                    await self.bot.send_message(chat_id=user_id, text=message)
                    success_count += 1
                    await asyncio.sleep(0.05)  # Telegram rate limit-ის თავიდან ასაცილებლად
                except Exception as e:
                    failed_count += 1
                    print(f"  ⚠️ Failed to send to {user_id}: {e}")
                    # თუ მომხმარებელმა დაბლოკა ბოტი, წაშალე subscribers-იდან
                    if "bot was blocked" in str(e).lower():
                        self.subscribers.discard(user_id)
                        self.save_subscribers()
                        print(f"  ❌ Removed blocked user: {user_id}")

            self.last_notifications[asset] = now
            print(f"  ✉️ Broadcast: {success_count} წარმატებული, {failed_count} წარუმატებელი")

    async def start(self):
        # 🆕 ახალი: ბოტის polling დაწყება background-ში
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

        startup_msg = (
            "💎 გამოცდილი ტრეიდერის ბოტი ჩაირთო. "
            "გლობალური ბაზრის მონიტორინგი დაწყებულია.\n\n"
            f"📊 მონიტორინგის მასშტაბი:\n"
            f"🔸 {len(CRYPTO)} კრიპტოვალუტა\n"
            f"🔸 {len(STOCKS)} აქცია\n"
            f"🔸 {len(COMMODITIES)} საქონელი/ფიუჩერსი\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📡 სულ: {len(ASSETS)} აქტივი\n"
            f"⏱️ თითო აქტივს შორის: {ASSET_DELAY}წმ\n"
            f"🔄 სრული ციკლის ხანგრძლივობა: ~{len(ASSETS) * ASSET_DELAY / 60:.0f}წთ\n\n"
            f"👥 აქტიური subscribers: {len(self.subscribers)}\n\n"
            f"📌 დაწერე /start რეგისტრაციისთვის"
        )

        # 🆕 ახალი: გაგზავნა ყველა subscriber-ზე
        for user_id in self.subscribers:
            try:
                await self.bot.send_message(chat_id=user_id, text=startup_msg)
            except Exception as e:
                print(f"⚠️ Failed to notify {user_id}: {e}")

        print(startup_msg)
        print("\n" + "="*50 + "\n")

        while True:
            await self.analyze_and_notify()
            print(f"😴 შესვენება {SCAN_INTERVAL} წამი შემდეგ ციკლამდე...\n")
            await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    print("🚀 ბოტი იწყება...\n")
    bot = ProTraderBot()
    asyncio.run(bot.start())