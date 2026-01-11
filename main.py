import os
import asyncio
import pandas as pd
import yfinance as yf
import feedparser
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
import telegram
import time

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ASSETS = ["BTC-USD", "ETH-USD", "AAPL", "TSLA", "^GSPC"]
INTERVAL = "1h"
SCAN_INTERVAL = 1  # ამოწმებს ყოველ 1 წამში
NOTIFICATION_COOLDOWN = 300  # აგზავნის მესიჯს მინიმუმ 5 წუთიანი ინტერვალით

RSS_FEEDS = [
    "https://cryptopanic.com/news/rss/",
    "https://www.investing.com/rss/news.rss"
]

NEGATIVE_KEYWORDS = [
    'crash', 'regulation', 'hacked', 'scam', 'fraud', 'drop', 'dump', 'ban',
    'lawsuit', 'bankruptcy', 'liquidation', 'volatility', 'arbitrage',
    'divergence', 'correlation', 'supply', 'demand', 'orderblock',
    'macroeconomic', 'inflation', 'interest rate', 'recession', 'uncertainty',
    'fear', 'unemployment', 'deficit', 'yield curve', 'correction', 'bearish',
    'bubble', 'sell-off', 'arbitrage gap', 'liquidity gap'
]

class MarketAnalyzer:
    def __init__(self, token, chat_id):
        self.bot = telegram.Bot(token=token) if token else None
        self.chat_id = chat_id
        self.active_positions = {}
        self.last_notification_time = {} # მეხსიერება სპამის წინააღმდეგ

    async def send_notification(self, message, asset_key):
        current_time = time.time()
        # ვამოწმებთ გავიდა თუ არა 5 წუთი ბოლო მესიჯიდან ამ ასეტზე
        last_time = self.last_notification_time.get(asset_key, 0)

        if current_time - last_time >= NOTIFICATION_COOLDOWN:
            if self.bot and self.chat_id:
                try:
                    await self.bot.send_message(chat_id=self.chat_id, text=message)
                    self.last_notification_time[asset_key] = current_time
                    print(f"შეტყობინება გაიგზავნა {asset_key}-ზე")
                except Exception as e:
                    print(f"Telegram error: {e}")
        else:
            print(f"სკანირება გრძელდება... {asset_key} პირობებშია, მაგრამ დაცულია 5 წუთიანი ინტერვალი.")

    def get_news_sentiment(self):
        news_items = []
        for url in RSS_FEEDS:
            try:
                feed = feedparser.parse(url)
                if feed.entries:
                    news_items.extend(feed.entries[:5])
            except Exception as e:
                print(f"Error fetching RSS {url}: {e}")

        warnings = []
        for item in news_items:
            title_lower = item.title.lower()
            for kw in NEGATIVE_KEYWORDS:
                if kw in title_lower:
                    severity = "კრიტიკული" if any(c in title_lower for c in ['crash', 'hacked', 'scam']) else "საშუალო"
                    warnings.append(f"⚠️ {severity}: '{kw}' - {item.title}")
                    break
        return warnings

    def get_data(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="2mo", interval=INTERVAL)
            return df
        except:
            return pd.DataFrame()

    def analyze(self, symbol, df):
        if df.empty or len(df) < 200:
            return None

        close = df['Close']
        current_price = close.iloc[-1]
        ema_200 = EMAIndicator(close=close, window=200).ema_indicator().iloc[-1]
        rsi = RSIIndicator(close=close, window=14).rsi().iloc[-1]
        bb = BollingerBands(close=close, window=20, window_dev=2)
        bb_low = bb.bollinger_lband().iloc[-1]
        bb_high = bb.bollinger_hband().iloc[-1]
        atr = AverageTrueRange(high=df['High'], low=df['Low'], close=close, window=14).average_true_range().iloc[-1]

        if (atr / current_price) * 100 < 0.1:
            return None

        market_trend = "UP" if current_price > ema_200 else "DOWN"

        if market_trend == "UP" and symbol not in self.active_positions:
            if rsi < 35 and current_price <= bb_low:
                news_warnings = self.get_news_sentiment()
                if news_warnings:
                    return {"asset": symbol, "action": "WARNING", "warnings": news_warnings}

                self.active_positions[symbol] = current_price
                return {
                    "asset": symbol, "action": "BUY", "price": current_price,
                    "reasons": ["RSI Low", "BB Sweep", "EMA 200 Support"]
                }

        elif symbol in self.active_positions:
            entry_price = self.active_positions[symbol]
            if rsi > 65 or current_price >= bb_high:
                profit_pct = ((current_price - entry_price) / entry_price) * 100
                del self.active_positions[symbol]
                return {
                    "asset": symbol, "action": "SELL", "price": current_price, "profit": profit_pct
                }
        return None

    async def run(self):
        print("Market Analysis AI: ჩართულია უწყვეტი სკანირების რეჟიმი.")
        # სატესტო მესიჯი
        if self.bot and self.chat_id:
            await self.bot.send_message(chat_id=self.chat_id, text="🚀 ბოტი წარმატებით ჩაირთო და დაიწყო უწყვეტი სკანირება!")

        while True:
            for asset in ASSETS:
                try:
                    df = self.get_data(asset)
                    result = self.analyze(asset, df)

                    if result:
                        msg = None
                        if result["action"] == "BUY":
                            msg = f"🟢 იყიდე: {result['asset']}\nმიზეზი: {', '.join(result['reasons'])}."
                        elif result["action"] == "WARNING":
                            warnings_str = "\n".join(result['warnings'][:2])
                            msg = f"⚠️ სიგნალი დაბლოკილია (სიახლეების ფილტრი):\n{warnings_str}"
                        elif result["action"] == "SELL":
                            current_balance = 1.0 * (1 + (result['profit'] / 100))
                            msg = f"🔴 გაყიდე: {result['asset']}\nმოგება: {result['profit']:.2f}%\n1$-ის ბალანსი: ${current_balance:.4f}"

                        if msg:
                            await self.send_notification(msg, asset)
                except Exception as e:
                    print(f"Error with {asset}: {e}")

            # მცირე პაუზა, რომ Yahoo Finance-მა არ დაგვბლოკოს
            await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    analyzer = MarketAnalyzer(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    asyncio.run(analyzer.run())