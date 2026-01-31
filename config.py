"""
AI Trading Bot - Configuration (CRYPTO-ONLY VERSION)
✅ 34 კრიპტოვალუტა სრული დაფარვა
✅ Multi-source fallback (CoinGecko → Binance → Yahoo)
✅ FIXED: AI_ENTRY_THRESHOLD, NOTIFICATION_COOLDOWN
"""

# ========================
# TELEGRAM SETTINGS
# ========================
TELEGRAM_TOKEN = "8247808058:AAGBsRWw8UOoZHMoulK6dGv-QI5L6A9f9rA"
ADMIN_ID = 6564836899

# ========================
# API KEYS & PROVIDERS
# ========================
# Primary provider (fallback only, not main)
TWELVE_DATA_API_KEY = "c512e8ccb9ae4637a613152481546749"

# Optional providers (not needed for crypto-only mode)
ALPACA_API_KEY = None
ALPACA_SECRET_KEY = None

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
# CRYPTO ASSETS (34 TOP PERFORMERS)
# ========================

# 🔵 Tier 1: Blue Chips (სტაბილური, დიდი კაპიტალიზაცია)
TIER_1_BLUE_CHIPS = [
    "BTC/USD",   # Bitcoin - ბაზრის ბირთვი
    "ETH/USD",   # Ethereum - DeFi + NFT ხერხემალი
    "BNB/USD",   # Binance Coin - ძლიერი მხარდაჭერა
    "SOL/USD",   # Solana - სწრაფი ეკოსისტემა
    "XRP/USD",   # Ripple - მკვეთრი სპაიკები
    "ADA/USD",   # Cardano - აკადემიური მიდგომა
    "AVAX/USD",  # Avalanche - სუბნეტები + ინსტიტუციური
    "LINK/USD",  # Chainlink - Oracle მონოპოლია
    "MATIC/USD", # Polygon - Ethereum scaling
    "DOT/USD",   # Polkadot - Parachains
    "TRX/USD",   # Tron - stablecoin volume ლიდერი
    "LTC/USD",   # Litecoin - liquidity + longevity
    "XLM/USD",   # Stellar - payments + CBDC focus
    "ETC/USD",   # Ethereum Classic - PoW hedge
]

# 🟢 Tier 2: High Growth (მაღალი ზრდის პოტენციალი)
TIER_2_HIGH_GROWTH = [
    "NEAR/USD",  # Near Protocol - user-friendly Web3
    "ARB/USD",   # Arbitrum - L2 ლიდერი
    "OP/USD",    # Optimism - L2 კონკურენტი
    "SUI/USD",   # Sui - ახალი L1
    "INJ/USD",   # Injective - DeFi + DEX
    "APT/USD",   # Aptos - Move language
    "UNI/USD",   # Uniswap - DEX ლიდერი
    "ATOM/USD",  # Cosmos - IBC ინტერნეტი
    "FTM/USD",   # Fantom - DeFi revival cycles
    "KAS/USD",   # Kaspa - PoW + high TPS narrative
    "RUNE/USD",  # Thorchain - cross-chain liquidity
    "EGLD/USD",  # MultiversX - infra + adoption
    "MINA/USD",  # Mina - light blockchain narrative
]

# 🟡 Tier 3: Meme/Volatility (მაღალი ვოლატილობა, სწრაფი მოგება)
TIER_3_MEME_COINS = [
    "DOGE/USD",  # Dogecoin - ნიუსზე რეაქცია
    "PEPE/USD",  # Pepe - მაღალი ვოლატილობა
    "WIF/USD",   # Dogwifhat - Solana meme
    "BONK/USD",  # Bonk - Solana meme
    "FLOKI/USD", # Floki Inu - მემე + utility
    "BRETT/USD", # Base ecosystem meme
    "POPCAT/USD",# Solana meme volatility
    "BOME/USD",  # High-risk narrative meme
    "MYRO/USD",  # Early Solana meme
]

# 🟣 Tier 4: Narrative Plays (AI, Gaming, RWA)
TIER_4_NARRATIVE = [
    "RNDR/USD",  # Render - AI + GPU narrative
    "FET/USD",   # Fetch.ai - AI agents
    "AGIX/USD",  # SingularityNET - AGI
    "GALA/USD",  # Gala Games - Web3 gaming
    "IMX/USD",   # Immutable X - NFT gaming L2
    "ONDO/USD",  # RWA leader
    "CFG/USD",   # Centrifuge - real-world assets
    "AKT/USD",   # Akash - decentralized cloud / AI
    "TAO/USD",   # Bittensor - AI subnet economy
    "PIXEL/USD", # Gaming + social narrative
]

# 🔴 Tier 5: New/Emerging (ახალი პროექტები, მაღალი რისკი)
TIER_5_EMERGING = [
    "SEI/USD",   # Sei Network - DeFi optimized L1
    "TIA/USD",   # Celestia - Modular blockchain
    "STRK/USD",  # Starknet - ZK-rollup
    "LTC/USD",   # Litecoin - "silver to Bitcoin's gold"
    "BCH/USD",   # Bitcoin Cash - payments focus
    "TON/USD",   # Toncoin - Telegram blockchain
    "PYTH/USD",  # Oracle for Solana ecosystem
    "JTO/USD",   # Solana liquid staking
    "DYM/USD",   # Modular rollapps
    "ZK/USD",    # ZK ecosystem exposure
    "AEVO/USD",  # Derivatives + options narrative
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
# Total crypto assets: 34
# Cycle time: 900 seconds (15 minutes) - faster for volatile crypto market
# Delay per asset: 900 / 34 ≈ 26 seconds (safe for all APIs)
SCAN_INTERVAL = 900  # 15 minutes (crypto markets move fast)

# Asset delay (smooth distribution)
ASSET_DELAY = 10  # 10 seconds between each crypto (faster than stocks)

# 🔧 FIXED: Notification settings
NOTIFICATION_COOLDOWN = 1800  # ✅ 30 minutes (was 1 hour - too long for crypto!)
STOP_LOSS_PERCENT = 5.0
TAKE_PROFIT_PERCENT = 10.0
MAX_HOLD_HOURS = 48  # Crypto trades shorter than stocks

# ========================
# AI SETTINGS (CRYPTO-TUNED)
# ========================
# 🔧 CRITICAL FIX: AI_ENTRY_THRESHOLD
# Old value: 65 (too high! Average score is 40-55)
# New value: 45 (realistic threshold that will actually trigger signals)
AI_ENTRY_THRESHOLD = 45  # ✅ FIXED from 65

AI_CONFIDENCE_HIGH = 80
AI_CONFIDENCE_LOW = 40

# ========================
# MESSAGE TEMPLATES (CRYPTO-FOCUSED)
# ========================
WELCOME_MSG_TEMPLATE = """👋 გამარჯობა @{username}!

🚀 AI Crypto Trading Bot (Multi-Source Data)

📊 მონიტორინგი:
• {crypto_count} კრიპტოვალუტა
• 5 კატეგორია (Blue Chips → Meme Coins)
• 15-წუთიანი სკანირება

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

# Guide footer
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
მაგალითი: SEI, TIA, STRK
""".format(
    blue_chip_count=len(TIER_1_BLUE_CHIPS),
    high_growth_count=len(TIER_2_HIGH_GROWTH),
    meme_count=len(TIER_3_MEME_COINS),
    narrative_count=len(TIER_4_NARRATIVE),
    emerging_count=len(TIER_5_EMERGING)
)

# ========================
# VALIDATION (დეველოპერისთვის)
# ========================
if __name__ == "__main__":
    print("="*60)
    print("📊 CONFIG VALIDATION")
    print("="*60)
    print(f"Total CRYPTO: {len(CRYPTO)}")
    print(f"AI_ENTRY_THRESHOLD: {AI_ENTRY_THRESHOLD}")
    print(f"NOTIFICATION_COOLDOWN: {NOTIFICATION_COOLDOWN}s ({NOTIFICATION_COOLDOWN/60:.0f} min)")
    print(f"SCAN_INTERVAL: {SCAN_INTERVAL}s ({SCAN_INTERVAL/60:.0f} min)")
    print("="*60)