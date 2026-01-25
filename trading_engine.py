"""
AI Trading Bot - Trading Engine (Production v3.0)
✅ Position Management (ყიდვა + გაყიდვა)
✅ Dynamic Take-Profit by Tier
✅ Stop-Loss Protection
✅ Max 2 Buy signals per asset
"""

import asyncio
import time
import json
import os
import logging
from datetime import datetime

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from config import *

# ✅ Import multi-source provider
try:
    from market_data import MultiSourceDataProvider
    MULTI_SOURCE_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ market_data.py successfully imported")
except ImportError as e:
    MULTI_SOURCE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error(f"❌ Failed to import market_data.py: {e}")
    logger.error("⚠️ Falling back to TwelveData-only mode")

# ========================
# FALLBACK: Simple Rate Limiter
# ========================
class SimpleFallbackLimiter:
    def __init__(self, max_per_minute=8):
        self.max_per_minute = max_per_minute
        self.requests = []

    async def wait_if_needed(self):
        now = time.time()
        self.requests = [t for t in self.requests if now - t < 60]

        if len(self.requests) >= self.max_per_minute:
            wait_time = 60 - (now - self.requests[0]) + 2
            logger.info(f"⏱️ Rate limit: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            self.requests = []

        self.requests.append(now)

# ========================
# POSITION MANAGEMENT
# ========================
class Position:
    """
    პოზიციის მენეჯმენტი ყიდვის/გაყიდვის თვალთვალისთვის
    """
    def __init__(self, symbol, entry_price, tier, ai_score, entry_time=None):
        self.symbol = symbol
        self.entry_price = entry_price
        self.tier = tier
        self.ai_score = ai_score
        self.entry_time = entry_time or datetime.now().isoformat()
        self.buy_signals_sent = 1  # პირველი ყიდვის სიგნალი
        self.highest_price = entry_price
        self.status = "open"

    def update_highest_price(self, current_price):
        """განახლება highest price-ის"""
        if current_price > self.highest_price:
            self.highest_price = current_price

    def get_profit_percent(self, current_price):
        """მოგების % გამოთვლა"""
        return ((current_price - self.entry_price) / self.entry_price) * 100

    def get_hours_held(self):
        """რამდენი ხანია ღია პოზიცია"""
        entry_dt = datetime.fromisoformat(self.entry_time)
        return (datetime.now() - entry_dt).total_seconds() / 3600

    def to_dict(self):
        """JSON-ში შესანახად"""
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'tier': self.tier,
            'ai_score': self.ai_score,
            'entry_time': self.entry_time,
            'buy_signals_sent': self.buy_signals_sent,
            'highest_price': self.highest_price,
            'status': self.status
        }

    @classmethod
    def from_dict(cls, data):
        """JSON-დან ჩატვირთვა"""
        pos = cls(
            symbol=data['symbol'],
            entry_price=data['entry_price'],
            tier=data['tier'],
            ai_score=data['ai_score'],
            entry_time=data['entry_time']
        )
        pos.buy_signals_sent = data.get('buy_signals_sent', 1)
        pos.highest_price = data.get('highest_price', data['entry_price'])
        pos.status = data.get('status', 'open')
        return pos

# ========================
# TRADING ENGINE
# ========================
class TradingEngine:
    def __init__(self):
        logger.info("🔧 Initializing TradingEngine...")

        # ✅ Multi-source provider
        if MULTI_SOURCE_AVAILABLE:
            try:
                self.data_provider = MultiSourceDataProvider(
                    twelve_data_key=TWELVE_DATA_API_KEY,
                    alpaca_key=ALPACA_API_KEY,
                    alpaca_secret=ALPACA_SECRET_KEY
                )
                self.use_multi_source = True
                logger.info("✅ Multi-source data provider initialized")
            except Exception as e:
                logger.error(f"❌ Multi-source init failed: {e}")
                self.use_multi_source = False
                self.fallback_limiter = SimpleFallbackLimiter(8)
        else:
            self.use_multi_source = False
            self.fallback_limiter = SimpleFallbackLimiter(8)
            logger.warning("⚠️ Using fallback mode (TwelveData only)")

        self.knowledge = self.load_trading_knowledge()

        # ✅ POSITION MANAGEMENT
        self.positions_file = "active_positions.json"
        self.active_positions = self.load_positions()
        self.last_scan_time = 0

        # ✅ Stats tracking
        self.stats = {
            'total_signals': 0,
            'buy_signals': 0,
            'sell_signals': 0,
            'profitable_trades': 0,
            'losing_trades': 0,
            'total_profit_percent': 0.0,
            'signals_by_tier': {
                'BLUE_CHIP': 0,
                'HIGH_GROWTH': 0,
                'MEME': 0,
                'NARRATIVE': 0,
                'EMERGING': 0
            }
        }

        logger.info("✅ TradingEngine initialized with Position Management")

    def load_trading_knowledge(self):
        """PDF ცოდნის ჩატვირთვა"""
        if os.path.exists(KNOWLEDGE_BASE_FILE):
            try:
                with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"patterns": [], "strategies": []}

    # ════════════════════════════════════════
    # POSITION MANAGEMENT
    # ════════════════════════════════════════

    def load_positions(self):
        """აქტიური პოზიციების ჩატვირთვა"""
        if os.path.exists(self.positions_file):
            try:
                with open(self.positions_file, 'r') as f:
                    data = json.load(f)
                    return {k: Position.from_dict(v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"❌ Positions load error: {e}")
        return {}

    def save_positions(self):
        """პოზიციების შენახვა"""
        try:
            data = {k: v.to_dict() for k, v in self.active_positions.items()}
            with open(self.positions_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Positions save error: {e}")

    def get_tier_config(self, symbol):
        """
        Tier-ის კონფიგურაცია symbol-ის მიხედვით
        Returns: (tier_name, tier_key, max_profit_target, trailing_stop_percent)
        """
        if symbol in TIER_1_BLUE_CHIPS:
            # Blue Chips: კონსერვატიული (10-15% target)
            return "🔵 BLUE CHIP", "BLUE_CHIP", 15.0, 5.0
        elif symbol in TIER_2_HIGH_GROWTH:
            # High Growth: საშუალო (20-30% target)
            return "🟢 HIGH GROWTH", "HIGH_GROWTH", 30.0, 7.0
        elif symbol in TIER_3_MEME_COINS:
            # Meme: აგრესიული (50-100% target)
            return "🟡 MEME", "MEME", 100.0, 15.0
        elif symbol in TIER_4_NARRATIVE:
            # Narrative: საშუალო-აგრესიული (40% target)
            return "🟣 NARRATIVE", "NARRATIVE", 40.0, 10.0
        elif symbol in TIER_5_EMERGING:
            # Emerging: მაღალი რისკი (60% target)
            return "🔴 EMERGING", "EMERGING", 60.0, 12.0
        else:
            return "CRYPTO", "OTHER", 20.0, 8.0

    def should_send_buy_signal(self, symbol):
        """
        ✅ გადაწყვეტილება: უნდა გაიგზავნოს ყიდვის სიგნალი?

        Rules:
        1. თუ პოზიცია არ არის - YES
        2. თუ პოზიცია არის და buy_signals_sent < 2 - YES (მეორე შესვლა)
        3. თუ უკვე 2 სიგნალი გაგზავნილია - NO (spam prevention)
        """
        if symbol not in self.active_positions:
            return True, "პირველი შესვლა"

        position = self.active_positions[symbol]

        if position.buy_signals_sent < 2:
            return True, f"მეორე შესვლა (DCA)"

        return False, f"მაქსიმუმ 2 ყიდვის სიგნალი უკვე გაგზავნილია"

    async def check_sell_conditions(self, symbol, current_price, data):
        """
        ✅ გაყიდვის პირობების შემოწმება

        Returns: (should_sell, reason, profit_percent)
        """
        if symbol not in self.active_positions:
            return False, None, 0.0

        position = self.active_positions[symbol]
        tier_name, tier_key, max_profit_target, trailing_stop = self.get_tier_config(symbol)

        # განახლება highest price
        position.update_highest_price(current_price)

        # მოგების გამოთვლა
        profit_percent = position.get_profit_percent(current_price)
        hours_held = position.get_hours_held()

        # ════════════════════════════════════════
        # 1. STOP-LOSS (-10%)
        # ════════════════════════════════════════
        if profit_percent <= -10.0:
            return True, f"🔴 Stop-Loss ({profit_percent:.1f}%) - რისკის შემცირება", profit_percent

        # ════════════════════════════════════════
        # 2. DYNAMIC TAKE-PROFIT
        # ════════════════════════════════════════

        # თუ მოგება მიაღწია max target-ს და დაიწყო დაცემა
        if profit_percent >= max_profit_target:
            # Trailing stop: თუ highest-დან 5-15% ჩამოვარდა
            drop_from_peak = ((position.highest_price - current_price) / position.highest_price) * 100

            if drop_from_peak >= trailing_stop:
                return True, f"🟢 Take-Profit ({profit_percent:.1f}%) - trailing stop triggered", profit_percent

        # ════════════════════════════════════════
        # 3. TIER-BASED PROFIT TARGETS
        # ════════════════════════════════════════

        # Blue Chips: 10-15% მოგება
        if tier_key == "BLUE_CHIP" and profit_percent >= 10.0:
            if data['rsi'] > 70:  # გადახურებულია
                return True, f"🔵 Blue Chip მიზანი ({profit_percent:.1f}%) + RSI>70", profit_percent

        # High Growth: 20-30% მოგება
        elif tier_key == "HIGH_GROWTH" and profit_percent >= 20.0:
            if data['rsi'] > 65 or data['price'] >= data['bb_high']:
                return True, f"🟢 High Growth მიზანი ({profit_percent:.1f}%)", profit_percent

        # Meme Coins: 50-100% მოგება (ან RSI>75)
        elif tier_key == "MEME" and profit_percent >= 50.0:
            if data['rsi'] > 75 or profit_percent >= 100.0:
                return True, f"🟡 Meme Coin მიზანი ({profit_percent:.1f}%)", profit_percent

        # Narrative: 40% მოგება
        elif tier_key == "NARRATIVE" and profit_percent >= 40.0:
            if data['rsi'] > 68:
                return True, f"🟣 Narrative მიზანი ({profit_percent:.1f}%)", profit_percent

        # Emerging: 60% მოგება
        elif tier_key == "EMERGING" and profit_percent >= 60.0:
            if data['rsi'] > 70:
                return True, f"🔴 Emerging მიზანი ({profit_percent:.1f}%)", profit_percent

        # ════════════════════════════════════════
        # 4. TIME-BASED EXIT (48h max hold)
        # ════════════════════════════════════════
        if hours_held >= MAX_HOLD_HOURS and profit_percent > 0:
            return True, f"⏱️ დროის ლიმიტი ({hours_held:.1f}h) + პოზიტიური ({profit_percent:.1f}%)", profit_percent

        return False, None, profit_percent

    # ════════════════════════════════════════
    # DATA FETCHING
    # ════════════════════════════════════════

    async def fetch_data_multi_source(self, symbol):
        """Multi-source fetch"""
        try:
            logger.debug(f"🔍 Fetching {symbol} via multi-source...")
            market_data = await self.data_provider.fetch_with_fallback(symbol)

            if market_data is None:
                logger.warning(f"⚠️ All sources failed for {symbol}")
                return None

            return {
                "price": market_data.price,
                "rsi": market_data.rsi,
                "ema200": market_data.ema200,
                "bb_low": market_data.bb_low,
                "bb_high": market_data.bb_high,
                "source": market_data.source
            }

        except Exception as e:
            logger.error(f"❌ Error fetching {symbol}: {e}")
            return None

    async def fetch_data_fallback(self, symbol):
        """TwelveData fallback"""
        try:
            import aiohttp
            import pandas as pd
            from ta.trend import EMAIndicator
            from ta.momentum import RSIIndicator
            from ta.volatility import BollingerBands

            await self.fallback_limiter.wait_if_needed()

            async with aiohttp.ClientSession() as session:
                url = "https://api.twelvedata.com/time_series"
                params = {
                    "symbol": symbol,
                    "interval": INTERVAL,
                    "apikey": TWELVE_DATA_API_KEY,
                    "outputsize": 200
                }

                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    if data.get('status') == 'error':
                        return None

                    df = pd.DataFrame(data.get('values', []))
                    if df.empty:
                        return None

                    df['close'] = pd.to_numeric(df['close'])
                    close = df['close'].iloc[::-1]

                    rsi = RSIIndicator(close).rsi().iloc[-1]
                    ema200 = EMAIndicator(close, window=200).ema_indicator().iloc[-1]
                    bb = BollingerBands(close)

                    return {
                        "price": close.iloc[-1],
                        "rsi": rsi,
                        "ema200": ema200,
                        "bb_low": bb.bollinger_lband().iloc[-1],
                        "bb_high": bb.bollinger_hband().iloc[-1],
                        "source": "twelvedata_fallback"
                    }

        except Exception as e:
            logger.error(f"❌ Fallback error {symbol}: {e}")
            return None

    async def fetch_data(self, symbol):
        """Main fetch router"""
        if self.use_multi_source:
            return await self.fetch_data_multi_source(symbol)
        else:
            return await self.fetch_data_fallback(symbol)

    # ════════════════════════════════════════
    # AI ANALYSIS
    # ════════════════════════════════════════

    async def ai_analyze_signal(self, symbol, data, sentiment):
        """AI score calculation"""
        score = 0
        reasons = []

        # RSI
        if data['rsi'] < 30:
            score += 40
            reasons.append(f"📉 გადაყიდულია (RSI: {data['rsi']:.1f})")
        elif data['rsi'] < 40:
            score += 25
            reasons.append(f"📉 დაბალი RSI ({data['rsi']:.1f})")

        # EMA200
        if data['price'] > data['ema200']:
            score += 20
            reasons.append("📈 აღმავალი ტრენდი")
        elif data['price'] > data['ema200'] * 0.98:
            score += 10
            reasons.append("📈 ტრენდთან ახლოს")

        # Bollinger Bands
        if data['price'] <= data['bb_low']:
            score += 25
            reasons.append("🎯 ქვედა ბოლინჯერზე")
        elif data['price'] <= data['bb_low'] * 1.02:
            score += 15
            reasons.append("🎯 ბოლინჯერთან ახლოს")

        # Fear & Greed
        if sentiment.get('fg_index', 50) < 30:
            score += 15
            reasons.append(f"😱 პანიკა ({sentiment['fg_index']})")
        elif sentiment.get('fg_index', 50) < 40:
            score += 8
            reasons.append(f"😰 შიში ({sentiment['fg_index']})")

        # PDF knowledge
        if any(p in str(reasons).lower() for p in self.knowledge.get('patterns', [])):
            score += 10
            reasons.append("🧠 PDF ნიმუში")

        return score, reasons

    # ════════════════════════════════════════
    # SIGNAL SENDING
    # ════════════════════════════════════════

    async def send_buy_signal(self, symbol, data, ai_score, reasons):
        """ყიდვის სიგნალის გაგზავნა"""
        if not hasattr(self, 'telegram_handler') or self.telegram_handler is None:
            logger.warning("⚠️ Telegram handler not linked")
            return

        tier_name, tier_key, max_target, trailing = self.get_tier_config(symbol)

        # ✅ შექმენი ან განაახლე პოზიცია
        if symbol not in self.active_positions:
            position = Position(symbol, data['price'], tier_name, ai_score)
            self.active_positions[symbol] = position
            logger.info(f"📝 ახალი პოზიცია: {symbol} @ ${data['price']:.4f}")
        else:
            self.active_positions[symbol].buy_signals_sent += 1
            logger.info(f"📝 DCA: {symbol} (სიგნალი #{self.active_positions[symbol].buy_signals_sent})")

        self.save_positions()

        # Format message
        message = BUY_SIGNAL_TEMPLATE.format(
            asset=symbol,
            tier=tier_name,
            price=data['price'],
            rsi=data['rsi'],
            ema200=data['ema200'],
            ai_score=ai_score,
            data_source=data.get('source', 'unknown').upper(),
            reasons="\n".join(reasons),
            sl_percent=10.0,  # Fixed 10% stop-loss
            tp_percent=max_target,
            estimated_tp=max_target
        )

        # Send
        try:
            await self.telegram_handler.broadcast_signal(message, symbol)
            self.stats['total_signals'] += 1
            self.stats['buy_signals'] += 1
            self.stats['signals_by_tier'][tier_key] += 1
            logger.info(f"📤 BUY signal: {symbol} [{tier_name}]")
        except Exception as e:
            logger.error(f"❌ Send error: {e}")

    async def send_sell_signal(self, symbol, data, reason, profit_percent):
        """გაყიდვის სიგნალის გაგზავნა"""
        if not hasattr(self, 'telegram_handler') or self.telegram_handler is None:
            return

        position = self.active_positions[symbol]
        hours_held = position.get_hours_held()

        # Emoji based on profit
        if profit_percent > 0:
            emoji = "🟢"
            self.stats['profitable_trades'] += 1
        else:
            emoji = "🔴"
            self.stats['losing_trades'] += 1

        self.stats['total_profit_percent'] += profit_percent

        # Format sell message
        message = SELL_SIGNAL_TEMPLATE.format(
            emoji=emoji,
            asset=symbol,
            tier=position.tier,
            entry_price=position.entry_price,
            exit_price=data['price'],
            profit=profit_percent,
            balance=1 + (profit_percent / 100),  # $1 → $X
            hours=hours_held,
            reason=reason
        )

        # Send
        try:
            await self.telegram_handler.broadcast_signal(message, symbol)
            self.stats['total_signals'] += 1
            self.stats['sell_signals'] += 1
            logger.info(f"📤 SELL signal: {symbol} ({profit_percent:+.1f}%)")
        except Exception as e:
            logger.error(f"❌ Send error: {e}")

        # ✅ დახურე პოზიცია
        position.status = "closed"
        del self.active_positions[symbol]
        self.save_positions()

    # ════════════════════════════════════════
    # MARKET SCAN
    # ════════════════════════════════════════

    async def scan_market(self, all_assets):
        """Market scanning with buy/sell logic"""
        logger.info("="*60)
        logger.info(f"🔍 MARKET SCAN STARTED")
        logger.info(f"📊 Assets: {len(all_assets)} | Positions: {len(self.active_positions)}")
        logger.info(f"🎯 AI Threshold: {AI_ENTRY_THRESHOLD}")
        logger.info("="*60)

        scan_start = time.time()
        success_count = 0
        fail_count = 0
        buy_signals = 0
        sell_signals = 0
        near_miss = 0

        for i, symbol in enumerate(all_assets, 1):
            try:
                logger.info(f"📊 [{i}/{len(all_assets)}] Scanning: {symbol}")

                # Fetch data
                data = await self.fetch_data(symbol)

                if data is None:
                    fail_count += 1
                    continue

                success_count += 1

                # ════════════════════════════════════════
                # 1. შემოწმება: გაყიდვის პირობები
                # ════════════════════════════════════════
                should_sell, sell_reason, profit = await self.check_sell_conditions(
                    symbol, data['price'], data
                )

                if should_sell:
                    sell_signals += 1
                    logger.info(f"🔴 SELL: {symbol} | {sell_reason}")
                    await self.send_sell_signal(symbol, data, sell_reason, profit)
                    continue  # Skip buy logic

                # ════════════════════════════════════════
                # 2. შემოწმება: ყიდვის პირობები
                # ════════════════════════════════════════
                can_buy, buy_reason = self.should_send_buy_signal(symbol)

                if not can_buy:
                    logger.debug(f"⏸️ Skip buy: {symbol} ({buy_reason})")
                    continue

                # AI Analysis
                sentiment = {"fg_index": 32}
                ai_score, reasons = await self.ai_analyze_signal(symbol, data, sentiment)

                # Signal decision
                if ai_score >= AI_ENTRY_THRESHOLD:
                    buy_signals += 1
                    logger.info(f"🟢 BUY: {symbol} (Score: {ai_score})")
                    await self.send_buy_signal(symbol, data, ai_score, reasons)
                else:
                    if ai_score >= AI_ENTRY_THRESHOLD - 10:
                        near_miss += 1
                        logger.info(f"⚠️ NEAR: {symbol} ({ai_score}/{AI_ENTRY_THRESHOLD})")

                # Delay
                await asyncio.sleep(ASSET_DELAY)

            except Exception as e:
                fail_count += 1
                logger.error(f"❌ Error: {symbol}: {e}")

        # Summary
        duration = time.time() - scan_start
        logger.info("="*60)
        logger.info(f"✅ SCAN COMPLETE ({duration/60:.1f}min)")
        logger.info(f"📊 Success: {success_count}/{len(all_assets)}")
        logger.info(f"🟢 Buy Signals: {buy_signals}")
        logger.info(f"🔴 Sell Signals: {sell_signals}")
        logger.info(f"⚠️ Near Misses: {near_miss}")
        logger.info(f"📂 Open Positions: {len(self.active_positions)}")

        # Provider stats
        if self.use_multi_source:
            try:
                stats = self.data_provider.get_stats()
                logger.info(f"📈 Provider Stats:")
                for source, sdata in stats['sources'].items():
                    logger.info(f"   {source}: {sdata['success']} OK | {sdata['fail']} FAIL")
            except:
                pass

        logger.info("="*60)
        self.last_scan_time = time.time()

    # ════════════════════════════════════════
    # MAIN LOOP
    # ════════════════════════════════════════

    async def run_forever(self):
        """Main trading loop"""
        all_assets = CRYPTO + STOCKS + COMMODITIES

        logger.info(f"""
╔════════════════════════════════════════╗
║  TRADING ENGINE v3.0 (POSITION MGT)    ║
╠════════════════════════════════════════╣
║ Mode: {'Multi-Source ✅' if self.use_multi_source else 'Fallback ⚠️'}
║ Assets: {len(all_assets)}
║ Scan: {SCAN_INTERVAL/60:.0f}min
║ AI Threshold: {AI_ENTRY_THRESHOLD}
║ Max Buy Signals: 2 per asset
║ Stop-Loss: -10% (fixed)
║ Take-Profit: Dynamic by Tier
╚════════════════════════════════════════╝
        """)

        consecutive_failures = 0

        while True:
            try:
                await self.scan_market(all_assets)
                consecutive_failures = 0

                logger.info(f"⏸️ Next scan in {SCAN_INTERVAL/60:.0f}min...")
                await asyncio.sleep(SCAN_INTERVAL)

            except Exception as e:
                consecutive_failures += 1
                logger.error(f"🚨 Error ({consecutive_failures}/3): {e}")

                if consecutive_failures >= 3:
                    logger.error("💥 Emergency mode (30min cooldown)")
                    await asyncio.sleep(1800)
                    consecutive_failures = 0
                else:
                    await asyncio.sleep(300)