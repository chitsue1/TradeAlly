import os
import time
import pandas as pd
import yfinance as yf
from ta.trend import SMAIndicator, RSIIndicator
import asyncio
from telegram import Bot

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ASSETS = ["BTC-USD", "ETH-USD", "AAPL", "TSLA", "^GSPC"]
INTERVAL = "1h"
CHECK_PERIOD = 3600 # 1 hour

class MarketAnalyzer:
    def __init__(self, token, chat_id):
        self.bot = Bot(token=token) if token else None
        self.chat_id = chat_id

    async def send_notification(self, message):
        if self.bot and self.chat_id:
            try:
                await self.bot.send_message(chat_id=self.chat_id, text=message)
                print(f"Notification sent: {message[:50]}...")
            except Exception as e:
                print(f"Error sending Telegram message: {e}")
        else:
            print(f"LOG: {message}")

    def get_data(self, symbol):
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval=INTERVAL)
        return df

    def analyze(self, symbol, df):
        if df.empty or len(df) < 20:
            return None
        
        # Technical Indicators
        sma_20 = SMAIndicator(close=df['Close'], window=20).sma_indicator()
        rsi = RSIIndicator(close=df['Close'], window=14).rsi()
        
        current_price = df['Close'].iloc[-1]
        last_sma = sma_20.iloc[-1]
        last_rsi = rsi.iloc[-1]
        
        signal = None
        reasons = []
        
        # Simple Logic for Signal Detection
        if current_price > last_sma and last_rsi < 70:
            signal = "Bullish"
            reasons.append(f"Price ({current_price:.2f}) is above 20 SMA ({last_sma:.2f})")
            reasons.append(f"RSI is at {last_rsi:.2f} (not overbought)")
        elif current_price < last_sma and last_rsi > 30:
            signal = "Bearish"
            reasons.append(f"Price ({current_price:.2f}) is below 20 SMA ({last_sma:.2f})")
            reasons.append(f"RSI is at {last_rsi:.2f} (not oversold)")
            
        if signal:
            return {
                "asset": symbol,
                "direction": signal,
                "reasons": reasons,
                "price": current_price
            }
        return None

    async def run(self):
        print("Starting Market Analysis AI...")
        while True:
            for asset in ASSETS:
                try:
                    df = self.get_data(asset)
                    result = self.analyze(asset, df)
                    
                    if result:
                        message = (
                            f"🔔 Market Signal\n"
                            f"Asset: {result['asset']}\n"
                            f"Direction: {result['direction']}\n"
                            f"Current Price: {result['price']:.2f}\n"
                            f"Reasons:\n- " + "\n- ".join(result['reasons']) + "\n"
                            f"⚠️ Risk Warning: This is not financial advice. Trading involves high risk."
                        )
                        await self.send_notification(message)
                except Exception as e:
                    print(f"Error analyzing {asset}: {e}")
            
            print(f"Cycle complete. Waiting {CHECK_PERIOD} seconds...")
            await asyncio.sleep(CHECK_PERIOD)

if __name__ == "__main__":
    analyzer = MarketAnalyzer(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    asyncio.run(analyzer.run())
