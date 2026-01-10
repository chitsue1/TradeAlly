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
# Negative keywords inspired by PDF books (Risk, Ruin, Liquidity, Volatility)
NEGATIVE_KEYWORDS = ['crash', 'regulation', 'hacked', 'scam', 'fraud', 'drop', 'dump', 'ban', 'lawsuit', 'bankruptcy', 'liquidation', 'volatility']

class MarketAnalyzer:
    def __init__(self, token, chat_id):
        # Using python-telegram-bot v20+ async Bot
        self.bot = telegram.Bot(token=token) if token else None
        self.chat_id = chat_id
        self.balance_tracker = {}  # Symbol -> Current balance starting from 1.0
        self.active_positions = {} # Symbol -> Entry price

    async def send_notification(self, message):
        if self.bot and self.chat_id:
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=message)
                print(f"Notification sent: {message[:50]}...")
            except Exception as e:
                print(f"Error sending Telegram message: {e}")
        else:
            print(f"LOG: {message}")

    def get_news_sentiment(self):
        """
        Analyze last 5 news items for negative sentiment based on PDF frameworks
        (Risk of Ruin, Liquidity Sweeps, and Arbitrage stability).
        """
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
                    # Severity assessment from PDF frameworks
                    if any(critical in title_lower for critical in ['crash', 'hacked', 'scam', 'bankruptcy', 'liquidation']):
                        severity = "კრიტიკული რისკი (გაკოტრების ალბათობა)"
                    else:
                        severity = "საშუალო რისკი (ბაზრის არასტაბილურობა)"
                    
                    warnings.append(f"⚠️ {severity}: '{kw}' - {item.title}")
                    break
        return warnings

    def get_data(self, symbol):
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1mo", interval=INTERVAL)
        return df

    def analyze(self, symbol, df):
        if df.empty or len(df) < 200:
            return None
        
        close = df['Close']
        current_price = close.iloc[-1]
        
        # Indicators from John Murphy and strategy PDFs
        ema_200 = EMAIndicator(close=close, window=200).ema_indicator().iloc[-1]
        rsi = RSIIndicator(close=close, window=14).rsi().iloc[-1]
        bb = BollingerBands(close=close, window=20, window_dev=2)
        bb_low = bb.bollinger_lband().iloc[-1]
        bb_high = bb.bollinger_hband().iloc[-1]
        atr = AverageTrueRange(high=df['High'], low=df['Low'], close=close, window=14).average_true_range().iloc[-1]
        
        volatility_ratio = (atr / current_price) * 100
        if volatility_ratio < 0.1: 
            return None

        market_trend = "UP" if current_price > ema_200 else "DOWN"

        if market_trend == "UP" and symbol not in self.active_positions:
            if rsi < 35 and current_price <= bb_low:
                news_warnings = self.get_news_sentiment()
                if news_warnings:
                    return {
                        "asset": symbol,
                        "action": "WARNING",
                        "warnings": news_warnings
                    }
                
                reasons = [
                    "RSI მიუთითებს გადაყიდვაზე (მომენტუმის შესუსტება)",
                    "ფასი ლიკვიდურობის ზონაშია (ბოლინჯერის ქვედა ზოლი)",
                    "გრძელვადიანი ტრენდი დადებითია (EMA 200-ს ზემოთ)"
                ]
                self.active_positions[symbol] = current_price
                return {
                    "asset": symbol,
                    "action": "BUY",
                    "price": current_price,
                    "reasons": reasons
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
        print("Market Analysis AI Active (EMA-200 + News Context Filter)")
        while True:
            for asset in ASSETS:
                try:
                    df = self.get_data(asset)
                    result = self.analyze(asset, df)
                    
                    if result:
                        if result["action"] == "BUY":
                            message = (
                                f"🟢 იყიდე: {result['asset']}\n"
                                f"მიზეზი: {', '.join(result['reasons'])}."
                            )
                        elif result["action"] == "WARNING":
                            message = (
                                f"⚠️ გაფრთხილება: {result['asset']} - ყიდვის სიგნალი შეჩერებულია ნეგატიური ფონის გამო:\n"
                                + "\n".join(result['warnings'][:3])
                            )
                        elif result["action"] == "SELL":
                            current_bal = self.balance_tracker.get(result['asset'], 1.0)
                            new_bal = current_bal * (1 + result['profit'] / 100)
                            self.balance_tracker[result['asset']] = new_bal
                            
                            message = (
                                f"🔴 გაყიდე: {result['asset']}\n"
                                f"მოგება: {result['profit']:.2f}%\n"
                                f"1$-ის ბალანსი იქნებოდა: {new_bal:.4f}$."
                            )
                                
                        await self.send_notification(message)
                except Exception as e:
                    print(f"Error analyzing {asset}: {e}")
            
            print(f"Cycle complete. Waiting {CHECK_PERIOD} seconds...")
            await asyncio.sleep(CHECK_PERIOD)

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Warning: Telegram configuration missing. Logging to console only.")
    
    analyzer = MarketAnalyzer(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    asyncio.run(analyzer.run())
