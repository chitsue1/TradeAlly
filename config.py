"""
AI Trading Bot - Configuration
"""

# ========================
# TELEGRAM SETTINGS
# ========================
TELEGRAM_TOKEN = "8247808058:AAGBsRWw8UOoZHMoulK6dGv-QI5L6A9f9rA"
ADMIN_ID = 6564836899

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
CRYPTO = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
    "ADA-USD", "DOGE-USD", "DOT-USD", "LINK-USD",
    "AVAX-USD", "SHIB-USD", "LTC-USD", "BCH-USD",
    "UNI-USD", "NEAR-USD", "ICP-USD", "HBAR-USD",
    "ARB-USD", "OP-USD"
]

STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "BRK-B", "V", "JPM", "UNH", "MA", "PG", "HD",
    "AVGO", "ORCL", "COST", "NFLX", "ADBE", "AMD",
    "CRM", "WMT", "LLY", "BAC", "XOM", "PFE", "DIS"
]

COMMODITIES = [
    "GC=F", "SI=F", "CL=F", "NG=F", "ZC=F", "ZW=F",
    "ES=F", "NQ=F", "DX=F", "HG=F"
]

ASSETS = CRYPTO + STOCKS + COMMODITIES

# ========================
# TRADING PARAMETERS
# ========================
INTERVAL = "1h"
SCAN_INTERVAL = 300  # 5 minutes
ASSET_DELAY = 2  # seconds between assets
NOTIFICATION_COOLDOWN = 7200  # 2 hours
STOP_LOSS_PERCENT = 5.0
TAKE_PROFIT_PERCENT = 10.0
MAX_HOLD_HOURS = 72
RSS_CACHE_TIME = 1800  # 30 minutes

# ========================
# API RATE LIMITS
# ========================
MAX_YAHOO_REQUESTS_PER_MINUTE = 30
MAX_COINGECKO_REQUESTS_PER_MINUTE = 50
MAX_SENTIMENT_REQUESTS_PER_HOUR = 40

# ========================
# AI SETTINGS
# ========================
AI_ENTRY_THRESHOLD = 60  # Score threshold for buy signal
AI_CONFIDENCE_HIGH = 80  # High confidence threshold
AI_CONFIDENCE_LOW = 40   # Low confidence threshold

# ========================
# COINGECKO COIN MAPPING
# ========================
COINGECKO_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "bnb": "binancecoin",
    "sol": "solana",
    "xrp": "ripple",
    "ada": "cardano",
    "doge": "dogecoin",
    "dot": "polkadot",
    "link": "chainlink",
    "avax": "avalanche-2",
    "shib": "shiba-inu",
    "ltc": "litecoin",
    "bch": "bitcoin-cash",
    "uni": "uniswap",
    "near": "near",
    "icp": "internet-computer",
    "hbar": "hedera-hashgraph",
    "arb": "arbitrum",
    "op": "optimism"
}

# ========================
# RSS FEEDS
# ========================
RSS_FEEDS = [
    "https://cryptopanic.com/news/rss/",
    "https://cointelegraph.com/rss"
]

# ========================
# MESSAGE TEMPLATES
# ========================
WELCOME_MSG_TEMPLATE = """👋 გამარჯობა @{username}!

🧠 AI: {ai_info} AI Trading Bot

📊 მონიტორინგი:
• {crypto_count} კრიპტოვალუტა
• {stocks_count} აქცია
• {commodities_count} საქონელი

💰 ფასი: 150₾ / თვე

📌 ბრძანებები:
/subscribe - გამოწერა
/mystatus - სტატუსი
/stop - გაუქმება

❓ კითხვები? https://t.me/Kagurashinakami"""

PAYMENT_INSTRUCTIONS = """💳 გამოწერის ინსტრუქცია:

1️⃣ გადაიხადეთ 150₾
🏦 ბანკი: საქართველოს ბანკი
📋 IBAN: GE95BG0000000528102311
👤 მიმღები: ლ.გ

2️⃣ გადახდის შემდეგ:
• გამოაგზავნეთ screenshot ამ ჩატში
• ან პირადში: https://t.me/Kagurashinakami

3️⃣ ჩვენ გავააქტიურებთ subscription-ს
⏱️ პროცესი: 24 საათში

❓ კითხვები? https://t.me/Kagurashinakami"""

BUY_SIGNAL_TEMPLATE = """🟢 AI იყიდე: {asset} [{asset_type}]

💵 ფასი: ${price:.2f}
📊 RSI: {rsi:.1f}
📈 EMA200: ${ema200:.2f}
🧠 AI Score: {ai_score}/100
📊 Fear&Greed: {fg_index} ({fg_class})

📌 AI მიზეზები:
{reasons}

🎯 რისკ მენეჯმენტი:
🔴 Stop-Loss: -{sl_percent}%
🟢 Take-Profit: +{tp_percent}%
💰 ესთიმეიტი TP: +{estimated_tp:.1f}% (პოტენციური)"""

SELL_SIGNAL_TEMPLATE = """{emoji} გაყიდე: {asset} [{asset_type}]

📊 შესვლა: ${entry_price:.2f}
📊 გასვლა: ${exit_price:.2f}
💰 მოგება/ზარალი: {profit:+.2f}%
💵 1$-ის ბალანსი: ${balance:.4f}
⏱️ ხანგრძლივობა: {hours:.1f}სთ

📌 მიზეზი: {reason}"""