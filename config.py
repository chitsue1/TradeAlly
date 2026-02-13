"""
AI Trading Bot - Configuration - PRODUCTION FINAL
✅ 57 კრიპტოვალუტა
✅ AI Risk Intelligence
"""
import os

# TELEGRAM
TELEGRAM_TOKEN = "8247808058:AAGBsRWw8UOoZHMoulK6dGv-QI5L6A9f9rA"
ADMIN_ID = 6564836899

# API KEYS
TWELVE_DATA_API_KEY = "c512e8ccb9ae4637a613152481546749"
ALPACA_API_KEY = None
ALPACA_SECRET_KEY = None

# ✅ AI - ჩაწერე შენი API Key
import os
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
AI_RISK_ENABLED = True

# CRYPTO (57)
TIER_1_BLUE_CHIPS = ["BTC/USD", "ETH/USD", "BNB/USD", "SOL/USD", "XRP/USD", "ADA/USD", "AVAX/USD", "LINK/USD", "MATIC/USD", "DOT/USD", "TRX/USD", "LTC/USD", "XLM/USD", "ETC/USD"]
TIER_2_HIGH_GROWTH = ["NEAR/USD", "ARB/USD", "OP/USD", "SUI/USD", "INJ/USD", "APT/USD", "UNI/USD", "ATOM/USD", "FTM/USD", "KAS/USD", "RUNE/USD", "EGLD/USD", "MINA/USD"]
TIER_3_MEME_COINS = ["DOGE/USD", "PEPE/USD", "WIF/USD", "BONK/USD", "FLOKI/USD", "BRETT/USD", "POPCAT/USD", "BOME/USD", "MYRO/USD"]
TIER_4_NARRATIVE = ["RNDR/USD", "FET/USD", "AGIX/USD", "GALA/USD", "IMX/USD", "ONDO/USD", "CFG/USD", "AKT/USD", "TAO/USD", "PIXEL/USD"]
TIER_5_EMERGING = ["SEI/USD", "TIA/USD", "STRK/USD", "BCH/USD", "TON/USD", "PYTH/USD", "JTO/USD", "DYM/USD", "ZK/USD", "AEVO/USD"]
CRYPTO = TIER_1_BLUE_CHIPS + TIER_2_HIGH_GROWTH + TIER_3_MEME_COINS + TIER_4_NARRATIVE + TIER_5_EMERGING
STOCKS = []
COMMODITIES = []

# PARAMETERS
INTERVAL = "1h"
SCAN_INTERVAL = 900
ASSET_DELAY = 2
NOTIFICATION_COOLDOWN = 1800
STOP_LOSS_PERCENT = 5.0
TAKE_PROFIT_PERCENT = 10.0
MAX_HOLD_HOURS = 48

# AI SETTINGS
AI_ENTRY_THRESHOLD = 45
AI_MIN_CONFIDENCE = 45
AI_CAUTION_THRESHOLD = 55
AI_HIGH_RISK_THRESHOLD = 75
AI_CONFIDENCE_HIGH = 80
AI_CONFIDENCE_LOW = 40

# FILES
SUBSCRIPTIONS_FILE = "subscriptions.json"
PAYMENT_REQUESTS_FILE = "payment_requests.json"
KNOWLEDGE_BASE_FILE = "trading_knowledge.json"
CACHE_FILE = "market_cache.json"
PDF_FOLDER = "My-AI-Agent_needs"

# MESSAGES
WELCOME_MSG_TEMPLATE = """👋 გამარჯობა @{username}!
🚀 AI Crypto Trading Bot
📊 {crypto_count} კრიპტო | 🧠 AI Risk
💰 150₾/თვე
/subscribe - გამოწერა"""

PAYMENT_INSTRUCTIONS = """💳 გადახდა
GE70BG0000000538913702
150₾ → ქვითარი აქ"""

BUY_SIGNAL_TEMPLATE = """🟢 იყიდე: {asset} [{tier}]
💵 ${price:.4f}
📊 RSI: {rsi:.1f}
🧠 {ai_score}/100
🔌 {data_source}

{reasons}

🎯 რისკ-მენეჯმენტი:
🔴 Stop: -{sl_percent}%
🟢 Target: +{tp_percent}%"""

SELL_SIGNAL_TEMPLATE = """{emoji} გაყიდე: {asset}
📊 ${entry_price:.4f} → ${exit_price:.4f}
💰 {profit:+.2f}%
⏱️ {hours:.1f}სთ
{reason}"""

GUIDE_FOOTER = "\n━━━━━━━━━━\n📖 /guide"

TIER_DESCRIPTIONS = """📊 კატეგორიები:
🔵 Blue Chips: BTC, ETH, SOL
🟢 High Growth: NEAR, ARB, SUI
🟡 Meme: DOGE, PEPE, WIF
🟣 Narrative: RNDR, FET, GALA
🔴 Emerging: SEI, TIA, TON"""

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')