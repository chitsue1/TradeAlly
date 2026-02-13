"""
AI Trading Bot - Configuration (CRYPTO-ONLY VERSION + AI RISK LAYER)
✅ 57 კრიპტოვალუტა სრული დაფარვა
✅ Multi-source fallback (Yahoo → CoinGecko → Binance)
✅ AI Risk Intelligence Layer
✅ FIXED: AI_ENTRY_THRESHOLD, NOTIFICATION_COOLDOWN
"""
import os

# ========================
# TELEGRAM SETTINGS
# ========================
TELEGRAM_TOKEN = "8247808058:AAGBsRWw8UOoZHMoulK6dGv-QI5L6A9f9rA"
ADMIN_ID = 6564836899

# ========================
# API KEYS & PROVIDERS
# ========================
# Primary provider
TWELVE_DATA_API_KEY = "c512e8ccb9ae4637a613152481546749"

# Optional providers
ALPACA_API_KEY = None
ALPACA_SECRET_KEY = None

# ✅ NEW: AI Risk Evaluator
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")

AI_RISK_ENABLED = True  # Set False to disable AI evaluation

# Note: CoinGecko, Binance, Yahoo Finance don't require API keys

# ========================
# FILE PATHS
# ========================
SUBSCRIPTIONS_FILE = "subscriptions.json"
PAYMENT_REQUESTS_FILE = "payment_requests.json"
KNOWLEDGE_BASE_FILE = "trading_knowledge.json"
CACHE_FILE = "market_cache.json"
PDF_FOLDER = "My-AI-Agent_needs"

# ========================
# CRYPTO ASSETS (57 TOP PERFORMERS)
# ========================

# 🔵 Tier 1: Blue Chips (სტაბილური, დიდი კაპიტალიზაცია)
TIER_1_BLUE_CHIPS = [
    "BTC/USD", "ETH/USD", "BNB/USD", "SOL/USD",
    "XRP/USD", "ADA/USD", "AVAX/USD", "LINK/USD",
    "MATIC/USD", "DOT/USD", "TRX/USD", "LTC/USD",
    "XLM/USD", "ETC/USD"
]

# 🟢 Tier 2: High Growth (მაღალი ზრდის პოტენციალი)
TIER_2_HIGH_GROWTH = [
    "NEAR/USD", "ARB/USD", "OP/USD", "SUI/USD",
    "INJ/USD", "APT/USD", "UNI/USD", "ATOM/USD",
    "FTM/USD", "KAS/USD", "RUNE/USD", "EGLD/USD",
    "MINA/USD"
]

# 🟡 Tier 3: Meme/Volatility (მაღალი ვოლატილობა, სწრაფი მოგება)
TIER_3_MEME_COINS = [
    "DOGE/USD", "PEPE/USD", "WIF/USD", "BONK/USD",
    "FLOKI/USD", "BRETT/USD", "POPCAT/USD", "BOME/USD",
    "MYRO/USD"
]

# 🟣 Tier 4: Narrative Plays (AI, Gaming, RWA)
TIER_4_NARRATIVE = [
    "RNDR/USD", "FET/USD", "AGIX/USD", "GALA/USD",
    "IMX/USD", "ONDO/USD", "CFG/USD", "AKT/USD",
    "TAO/USD", "PIXEL/USD"
]

# 🔴 Tier 5: New/Emerging (ახალი პროექტები, მაღალი რისკი)
TIER_5_EMERGING = [
    "SEI/USD", "TIA/USD", "STRK/USD",
    "BCH/USD", "TON/USD", "PYTH/USD",
    "JTO/USD", "DYM/USD", "ZK/USD", "AEVO/USD"
]

# ✅ COMBINED LIST (all tiers)
CRYPTO = (
    TIER_1_BLUE_CHIPS +
    TIER_2_HIGH_GROWTH +
    TIER_3_MEME_COINS +
    TIER_4_NARRATIVE +
    TIER_5_EMERGING
)

# ❌ REMOVED: Stocks and Commodities (crypto-only strategy)
STOCKS = []
COMMODITIES = []

# ========================
# TRADING PARAMETERS (OPTIMIZED FOR CRYPTO)
# ========================
INTERVAL = "1h"

# ✅ Crypto-optimized scan cycle
SCAN_INTERVAL = 900  # 15 minutes
ASSET_DELAY = 2  # 2 seconds between each crypto

# 🔧 Notification settings
NOTIFICATION_COOLDOWN = 1800  # 30 minutes
STOP_LOSS_PERCENT = 5.0
TAKE_PROFIT_PERCENT = 10.0
MAX_HOLD_HOURS = 48

# ========================
# AI SETTINGS (CRYPTO-TUNED + AI RISK LAYER)
# ========================
# Strategy confidence threshold
AI_ENTRY_THRESHOLD = 45  # Base strategy threshold

# ✅ NEW: AI Risk Evaluator Settings
AI_MIN_CONFIDENCE = 45  # Minimum after AI evaluation
AI_CAUTION_THRESHOLD = 55  # Below this = APPROVE_WITH_CAUTION
AI_HIGH_RISK_THRESHOLD = 75  # Risk score above = extra scrutiny

AI_CONFIDENCE_HIGH = 80
AI_CONFIDENCE_LOW = 40

# ========================
# MESSAGE TEMPLATES (CRYPTO-FOCUSED)
# ========================
WELCOME_MSG_TEMPLATE = """👋 გამარჯობა @{username}!

🚀 AI Crypto Trading Bot (Multi-Source Data + AI Risk Layer)

📊 მონიტორინგი:
• {crypto_count} კრიპტოვალუტა
• 5 კატეგორია (Blue Chips → Emerging)
• 15-წუთიანი სკანირება
• 🧠 AI Risk Intelligence

💰 ფასი: 150₾ / თვე

📌 ბრძანებები:
/subscribe - გამოწერა
/mystatus - სტატუსი
/tiers - კატეგორიები
/stop - გაუქმება

❓ დახმარებისთვის: https://t.me/Kagurashinakami"""

PAYMENT_INSTRUCTIONS = """💳 **გადახდის ინსტრუქცია**
საქართველოს ანგარიში (Bog): GE70BG0000000538913702  ლ.გ

გადაიხადეთ 150₾ ბანკის ბარათზე და გამოგზავნეთ ქვითარი აქ.

📌 ადმინი დაადასტურებს 24 საათში."""

BUY_SIGNAL_TEMPLATE = """🟢 AI იყიდე: {asset} [{tier}]

💵 ფასი: ${price:.4f}
📊 RSI: {rsi:.1f}
📈 EMA200: ${ema200:.4f}
🧠 AI Score: {ai_score}/100
🔌 წყარო: {data_source}

📌 AI ანალიზი:
{reasons}

🎯 რისკ მენეჯმენტი:
🔴 Stop-Loss: -{sl_percent}%
🟢 Take-Profit: +{tp_percent}%
💰 პოტენციური მოგება: +{estimated_tp:.1f}%"""

SELL_SIGNAL_TEMPLATE = """{emoji} გაყიდე: {asset} [{tier}]

📊 შესვლა: ${entry_price:.4f}
📊 გასვლა: ${exit_price:.4f}
💰 მოგება/ზარალი: {profit:+.2f}%
💵 ბალანსი (1$): ${balance:.4f}
⏱️ ხანგრძლივობა: {hours:.1f}სთ

📌 მიზეზი: {reason}"""

GUIDE_FOOTER = "\n\n━━━━━━━━━━━━━━\n📖 **არ გესმით რა არის RSI, EMA, Stop-Loss?**\nგამოიყენეთ: /guide"

# ========================
# TIER DESCRIPTIONS (for /tiers command)
# ========================
TIER_DESCRIPTIONS = """
📊 **კრიპტო კატეგორიები:**

🔵 **Tier 1: Blue Chips** ({blue_chip_count})
სტაბილური, დიდი კაპიტალიზაცია
მაგალითი: BTC, ETH, BNB, SOL

🟢 **Tier 2: High Growth** ({high_growth_count})
მაღალი ზრდის პოტენციალი
მაგალითი: NEAR, ARB, OP, SUI

🟡 **Tier 3: Meme Coins** ({meme_count})
მაღალი ვოლატილობა, სწრაფი მოგება
მაგალითი: DOGE, PEPE, WIF, BONK

🟣 **Tier 4: Narratives** ({narrative_count})
AI, Gaming, RWA თემატიკა
მაგალითი: RNDR, FET, GALA, IMX

🔴 **Tier 5: Emerging** ({emerging_count})
ახალი პროექტები, მაღალი რისკი
მაგალითი: SEI, TIA, STRK, TON
""".format(
    blue_chip_count=len(TIER_1_BLUE_CHIPS),
    high_growth_count=len(TIER_2_HIGH_GROWTH),
    meme_count=len(TIER_3_MEME_COINS),
    narrative_count=len(TIER_4_NARRATIVE),
    emerging_count=len(TIER_5_EMERGING)
)

# ========================
# VALIDATION
# ========================
if __name__ == "__main__":
    print("="*60)
    print("📊 CONFIG VALIDATION")
    print("="*60)
    print(f"Total CRYPTO: {len(CRYPTO)}")
    print(f"AI_ENTRY_THRESHOLD: {AI_ENTRY_THRESHOLD}")
    print(f"AI Risk Enabled: {AI_RISK_ENABLED}")
    print(f"NOTIFICATION_COOLDOWN: {NOTIFICATION_COOLDOWN}s ({NOTIFICATION_COOLDOWN/60:.0f} min)")
    print(f"SCAN_INTERVAL: {SCAN_INTERVAL}s ({SCAN_INTERVAL/60:.0f} min)")
    print("="*60)

# ========================
# LOGGING
# ========================
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)