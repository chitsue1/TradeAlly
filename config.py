"""
AI Trading Bot - Configuration (Multi-Source Optimized)
"""

# ========================
# TELEGRAM SETTINGS
# ========================
TELEGRAM_TOKEN = "8247808058:AAGBsRWw8UOoZHMoulK6dGv-QI5L6A9f9rA"
ADMIN_ID = 6564836899

# ========================
# API KEYS & PROVIDERS
# ========================
# Primary provider (fallback)
TWELVE_DATA_API_KEY = "c512e8ccb9ae4637a613152481546749"

# Optional providers (leave None if not using)
ALPACA_API_KEY = None  # Get free key at: https://alpaca.markets
ALPACA_SECRET_KEY = None

# Note: Binance and Yahoo Finance don't require API keys for public market data

# ========================
# FILE PATHS
# ========================
SUBSCRIPTIONS_FILE = "subscriptions.json"
PAYMENT_REQUESTS_FILE = "payment_requests.json"
KNOWLEDGE_BASE_FILE = "trading_knowledge.json"
CACHE_FILE = "market_cache.json"
PDF_FOLDER = "My-AI-Agent_needs"

# ========================
# TRADING ASSETS
# ========================
# Crypto assets (multi-source compatible format)
CRYPTO = [
    "BTC/USD", "ETH/USD", "BNB/USD", "SOL/USD", "XRP/USD",
    "ADA/USD", "DOGE/USD", "DOT/USD", "LINK/USD",
    "AVAX/USD", "LTC/USD", "BCH/USD", "UNI/USD", 
    "NEAR/USD", "ICP/USD", "HBAR/USD"
]

# Stock assets
STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "V", "JPM", "MA", "PG", "HD", "NFLX", "ADBE", "AMD",
    "TSM", "ASML", "SNOW", "SQ", "PYPL", "XOM", "COST", "CAT"
]

# Commodities
COMMODITIES = [
    "GOLD", "SILVER", "WTI"
]

# ========================
# TRADING PARAMETERS (OPTIMIZED FOR 30-MIN CYCLES)
# ========================
INTERVAL = "1h"

# ✅ NEW: 30-minute full scan cycle (instead of 7 minutes)
# Total assets: ~43 (16 crypto + 24 stocks + 3 commodities)
# Cycle time: 1800 seconds (30 minutes)
# Delay per asset: 1800 / 43 ≈ 42 seconds
SCAN_INTERVAL = 1800  # Full cycle: 30 minutes

# ✅ NEW: Smart delay between assets
# With multi-source fallback, we don't need aggressive delays
# 15 seconds is enough for smooth distribution
ASSET_DELAY = 15  # Delay between each asset fetch

# Notification settings
NOTIFICATION_COOLDOWN = 7200  # Don't spam same signal within 2 hours
STOP_LOSS_PERCENT = 5.0
TAKE_PROFIT_PERCENT = 10.0
MAX_HOLD_HOURS = 72

# ========================
# RATE LIMITS (Per Source - Handled by MultiSourceDataProvider)
# ========================
# These are now managed internally by market_data.py
# Binance: 1200 requests/minute (weight system)
# Alpaca: 200 requests/minute
# Yahoo: ~2000 requests/hour
# TwelveData: 8 requests/minute (free tier)

# Legacy (kept for backwards compatibility, not used)
MAX_TD_REQUESTS_PER_MINUTE = 8
MAX_TD_REQUESTS_PER_DAY = 800

# ========================
# AI SETTINGS
# ========================
AI_ENTRY_THRESHOLD = 70  
AI_CONFIDENCE_HIGH = 85  
AI_CONFIDENCE_LOW = 40   

# ========================
# MESSAGE TEMPLATES
# ========================
WELCOME_MSG_TEMPLATE = """👋 გამარჯობა @{username}!

🚀 AI Trading Bot (Multi-Source Data Provider)

📊 მონიტორინგი:
• {crypto_count} კრიპტოვალუტა
• {stocks_count} აქცია
• {commodities_count} საქონელი

💰 ფასი: 150₾ / თვე

📌 ბრძანებები:
/subscribe - გამოწერა
/mystatus - სტატუსი
/stop - გაუქმება

❓ დახმარებისთვის: https://t.me/Kagurashinakami"""

PAYMENT_INSTRUCTIONS = """💳 **გადახდის ინსტრუქცია**

გადაიხადეთ 150₾ ბანკის ბარათზე და გამოგზავნეთ ქვითარი აქ.

📌 ადმინი დაადასტურებს 24 საათში."""

BUY_SIGNAL_TEMPLATE = """🟢 AI იყიდე: {asset} [{asset_type}]

💵 ფასი: ${price:.2f}
📊 RSI: {rsi:.1f}
📈 EMA200: ${ema200:.2f}
🧠 AI Score: {ai_score}/100
🔌 წყარო: {data_source}

📌 AI ანალიზი:
{reasons}

🎯 რისკ მენეჯმენტი:
🔴 Stop-Loss: -{sl_percent}%
🟢 Take-Profit: +{tp_percent}%
💰 პოტენციური მოგება: +{estimated_tp:.1f}%"""

SELL_SIGNAL_TEMPLATE = """{emoji} გაყიდე: {asset} [{asset_type}]

📊 შესვლა: ${entry_price:.2f}
📊 გასვლა: ${exit_price:.2f}
💰 მოგება/ზარალი: {profit:+.2f}%
💵 ბალანსი (1$): ${balance:.4f}
⏱️ ხანგრძლივობა: {hours:.1f}სთ

📌 მიზეზი: {reason}"""

# ყველა სიგნალის ბოლოში დაემატება
GUIDE_FOOTER = "\n\n━━━━━━━━━━━━━━\n📖 **არ გესმით რა არის RSI, EMA, Stop-Loss?**\nგამოიყენეთ: /guide"