import os
import asyncio
import pandas as pd
import yfinance as yf
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from telegram import Bot

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ASSETS = ["BTC-USD", "ETH-USD", "AAPL", "TSLA", "^GSPC"]
INTERVAL = "1h"
CHECK_PERIOD = 3600  # 1 hour

class MarketAnalyzer:
    def __init__(self, token, chat_id):
        self.bot = Bot(token=token) if token else None
        self.chat_id = chat_id
        self.balance_tracker = {}  # Symbol -> Current balance based on 1.0 start
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

    def get_data(self, symbol):
        ticker = yf.Ticker(symbol)
        # Need enough data for 200 EMA
        df = ticker.history(period="1mo", interval=INTERVAL)
        return df

    def analyze(self, symbol, df):
        if df.empty or len(df) < 200:
            return None
        
        close = df['Close']
        current_price = close.iloc[-1]
        
        # Indicators
        ema_200 = EMAIndicator(close=close, window=200).ema_indicator().iloc[-1]
        rsi = RSIIndicator(close=close, window=14).rsi().iloc[-1]
        bb = BollingerBands(close=close, window=20, window_dev=2)
        bb_high = bb.bollinger_hband().iloc[-1]
        bb_low = bb.bollinger_lband().iloc[-1]
        atr = AverageTrueRange(high=df['High'], low=df['Low'], close=close, window=14).average_true_range().iloc[-1]
        
        # Volatility check (Noise filter)
        # If ATR is very low relative to price, market might be too quiet/noisy
        volatility_ratio = (atr / current_price) * 100
        if volatility_ratio < 0.1: # Threshold for "noise"
            return None

        signal = None
        reasons = []

        # Context Filter: 200 EMA
        market_trend = "UP" if current_price > ema_200 else "DOWN"

        # Strategy: RSI + Bollinger Bands + EMA Filter
        # Buy Signal (Long)
        if market_trend == "UP" and symbol not in self.active_positions:
            if rsi < 35 and current_price <= bb_low:
                signal = "BUY"
                reasons = ["RSI მიუთითებს გადაყიდვაზე", "ფასი ბოლინჯერის ქვედა ზოლთანაა"]

        # Sell Signal (Exit Long)
        elif symbol in self.active_positions:
            entry_price = self.active_positions[symbol]
            # Exit if RSI is overbought or price hits upper band
            if rsi > 65 or current_price >= bb_high:
                signal = "SELL"
                profit_pct = ((current_price - entry_price) / entry_price) * 100
                return {
                    "asset": symbol,
                    "action": "SELL",
                    "price": current_price,
                    "profit": profit_pct
                }

        if signal == "BUY":
            self.active_positions[symbol] = current_price
            return {
                "asset": symbol,
                "action": "BUY",
                "price": current_price,
                "reasons": reasons
            }
            
        return None

    async def run(self):
        print("Starting Market Analysis AI with EMA-200 Filter...")
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
                        else: # SELL
                            # Update balance tracker
                            current_val = self.balance_tracker.get(result['asset'], 1.0)
                            new_val = current_val * (1 + result['profit'] / 100)
                            self.balance_tracker[result['asset']] = new_val
                            
                            message = (
                                f"🔴 გაყიდე: {result['asset']}\n"
                                f"მოგება: {result['profit']:.2f}%\n"
                                f"1$-ის ბალანსი იქნებოდა: {new_val:.4f}$."
                            )
                            # Remove from active positions
                            if result['asset'] in self.active_positions:
                                del self.active_positions[result['asset']]
                                
                        await self.send_notification(message)
                except Exception as e:
                    print(f"Error analyzing {asset}: {e}")
            
            print(f"Cycle complete. Waiting {CHECK_PERIOD} seconds...")
            await asyncio.sleep(CHECK_PERIOD)

if __name__ == "__main__":
    analyzer = MarketAnalyzer(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    asyncio.run(analyzer.run())
