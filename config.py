"""
AI Trading Bot - Configuration (Twelve Data Optimized)
"""

# ========================
# TELEGRAM SETTINGS
# ========================
TELEGRAM_TOKEN = "8247808058:AAGBsRWw8UOoZHMoulK6dGv-QI5L6A9f9rA"
ADMIN_ID = 6564836899

# ========================
# API KEYS & PROVIDERS
# ========================
TWELVE_DATA_API_KEY = "c512e8ccb9ae4637a613152481546749"

# ========================
# FILE PATHS
# ========================
SUBSCRIPTIONS_FILE = "subscriptions.json"
PAYMENT_REQUESTS_FILE = "payment_requests.json"
KNOWLEDGE_BASE_FILE = "trading_knowledge.json"
CACHE_FILE = "market_cache.json"
PDF_FOLDER = "My-AI-Agent_needs"

# ========================
# TRADING ASSETS (Twelve Data Format)
# ========================
# კრიპტო: Twelve Data იყენებს ფორმატს "BTC/USD"
CRYPTO = [
    "BTC/USD", "ETH/USD", "BNB/USD", "SOL/USD", "XRP/USD",
    "ADA/USD", "DOGE/USD", "DOT/USD", "LINK/USD",
    "AVAX/USD", "LTC/USD", "BCH/USD", "UNI/USD", 
    "NEAR/USD", "ICP/USD", "HBAR/USD"
]

# აქციები: ჩვეულებრივი სიმბოლოები
STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "V", "JPM", "MA", "PG", "HD", "NFLX", "ADBE", "AMD","TSM", "ASML", "SNOW", "SQ", "PYPL", "XOM", "COST", "CAT"
]

# საქონელი: Twelve Data-ს ფორმატი
COMMODITIES = [
    "GOLD", "SILVER", "WTI"
]

# ========================
# TRADING PARAMETERS (Twelve Data Limits)
# ========================
INTERVAL = "1h"

# რადგან ლიმიტი არის 8 მოთხოვნა/წუთში, სკანირების ინტერვალი უნდა იყოს გონივრული.
# 15 წუთი (900 წამი) იდეალურია, რომ ბოტმა მშვიდად დაასრულოს ციკლი.
SCAN_INTERVAL = 900  

# ASSET_DELAY - ყველაზე მნიშვნელოვანი პარამეტრი!
# 60 წამი / 8 მოთხოვნა = 7.5 წამი. 
# ჩვენ ავიღებთ 10 წამს, რომ API-მ არასდროს დაგვიბლოკოს წვდომა.
ASSET_DELAY = 10  

NOTIFICATION_COOLDOWN = 7200  
STOP_LOSS_PERCENT = 5.0
TAKE_PROFIT_PERCENT = 10.0
MAX_HOLD_HOURS = 72

# ========================
# API RATE LIMITS (Twelve Data Free Plan)
# ========================
# მკაცრი ლიმიტები უფასო პაკეტისთვის
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

🚀 AI Trading Bot (Powered by Twelve Data)

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