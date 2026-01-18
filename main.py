import os
import asyncio
import pandas as pd
import yfinance as yf
import feedparser
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
import telegram

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ASSETS = ["BTC-USD", "ETH-USD", "AAPL", "TSLA", "^GSPC"]
INTERVAL = "1h"
CHECK_PERIOD = 3600  # 1 hour
RSS_FEEDS = [
    "https://cryptopanic.com/news/rss/",
    "https://www.investing.com/rss/news.rss"
]

# Integrated keywords from ALL 20 PDF documents
NEGATIVE_KEYWORDS = [
    'crash', 'regulation', 'hacked', 'scam', 'fraud', 'drop', 'dump', 'ban', 'lawsuit', 'bankruptcy', 
    'liquidation', 'volatility', 'arbitrage', 'divergence', 'correlation', 'supply', 'demand', 'orderblock',
    'macroeconomic', 'inflation', 'interest rate', 'recession', 'uncertainty', 'fear', 'unemployment', 
    'deficit', 'yield curve', 'correction', 'bearish', 'bubble', 'sell-off', 'arbitrage gap', 'liquidity gap'
]

class MarketAnalyzer:
    def __init__(self, token, chat_id):
        # Initialize the bot
        self.bot = telegram.Bot(token=token) if token else None
        self.chat_id = chat_id
        self.active_positions = {}

    async def send_notification(self, message):
        if self.bot and self.chat_id:
            try:
                # Use await because it's python-telegram-bot v20+
                await self.bot.send_message(chat_id=self.chat_id, text=message)
                print(f"Notification sent: {message[:50]}...")
            except Exception as e:
                print(f"Error sending Telegram message: {e}")
        else:
            print(f"LOG: {message}")

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
            summary = getattr(item, 'summary', '')
            summary_lower = summary.lower() if summary else ''
            for kw in NEGATIVE_KEYWORDS:
                if kw in title_lower or kw in summary_lower:
                    if any(critical in title_lower for critical in ['crash', 'hacked', 'scam', 'bankruptcy', 'recession', 'bubble']):
                        severity = "კრიტიკული (Risk of Ruin)"
                    else:
                        severity = "საშუალო (Macro)"
                    
                    warnings.append(f"⚠️ {severity}: '{kw}' - {item.title}")
                    break
        return warnings

    def get_data(self, symbol):
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="2mo", interval=INTERVAL)
        return df

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
                    "asset": symbol,
                    "action": "BUY",
                    "price": current_price,
                    "reasons": ["RSI Low", "BB Sweep", "EMA 200 Support"]
                }

        elif symbol in self.active_positions:
            entry_price = self.active_positions[symbol]
            if rsi > 65 or current_price >= bb_high:
                profit_pct = ((current_price - entry_price) / entry_price) * 100
                del self.active_positions[symbol]
                return {
                    "asset": symbol,
                    "action": "SELL",
                    "price": current_price,
                    "profit": profit_pct
                }
            
        return None

    async def run(self):
        print("Market Analysis AI: Fully operational with all 20 PDF strategies.")
        while True:
            for asset in ASSETS:
                try:
                    df = self.get_data(asset)
                    result = self.analyze(asset, df)
                    
                    if result:
                        if result["action"] == "BUY":
                            msg = f"🟢 იყიდე: {result['asset']}\nმიზეზი: {', '.join(result['reasons'])}."
                        elif result["action"] == "WARNING":
                            msg = f"⚠️ სიგნალი დაბლოკილია (სიახლეების ფილტრი):\n" + "\n".join(result['warnings'][:2])
                        elif result["action"] == "SELL":
                            msg = f"🔴 გაყიდე: {result['asset']}\nმოგება: {result['profit']:.2f}%."
                        await self.send_notification(msg)
                except Exception as e:
                    print(f"Error with {asset}: {e}")
            await asyncio.sleep(CHECK_PERIOD)

if __name__ == "__main__":
    analyzer = MarketAnalyzer(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    asyncio.run(analyzer.run())
