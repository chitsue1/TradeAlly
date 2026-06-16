    """
    ═══════════════════════════════════════════════════════════════════════════════
    TRADE ALLY BOT - CONFIG v4.0 PRODUCTION
    ═══════════════════════════════════════════════════════════════════════════════

    ✅ გაუმჯობესებები:
    - ყველა token/key env variable-ში (hardcode აღარ)
    - Tier-based risk thresholds
    - Signal quality gates
    - ATR-based stop/target multipliers
    - Daily signal limits per tier
    ═══════════════════════════════════════════════════════════════════════════════
    """

    import os
    import logging

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # Railway-ზე dotenv არ სჭირდება — env vars dashboard-ში იწერება

    logger = logging.getLogger(__name__)

    # ═══════════════════════════════════════════════════════════════════════════
    # CREDENTIALS — ყველა env-დან (NEVER hardcode!)
    # ═══════════════════════════════════════════════════════════════════════════

    TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN", "")
    ADMIN_ID            = int(os.environ.get("ADMIN_ID", "0"))
    ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
    AI_RISK_ENABLED     = os.environ.get("AI_RISK_ENABLED", "true").lower() == "true"

    # Legacy compat
    TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
    ALPACA_API_KEY      = os.environ.get("ALPACA_API_KEY", None)
    ALPACA_SECRET_KEY   = os.environ.get("ALPACA_SECRET_KEY", None)

    # ═══════════════════════════════════════════════════════════════════════════
    # ASSET UNIVERSE — 140 კრიპტო, 5 Tier (v9.0 სრული სია)
    # ═══════════════════════════════════════════════════════════════════════════

    # Tier 1 — Core Majors / Blue Chips (ყველაზე დიდი cap, ყველაზე დაბალი რისკი)
    TIER_1_BLUE_CHIPS = [
        "BTC/USD", "ETH/USD", "BNB/USD", "SOL/USD", "XRP/USD",
        "ADA/USD", "DOGE/USD", "TRX/USD", "TON/USD", "AVAX/USD",
    ]

    # Tier 2 — High Growth: L1s + L2s + DeFi + Infra (საშუალო-მაღალი პოტენციალი)
    TIER_2_HIGH_GROWTH = [
        # Smart Contract L1s
        "DOT/USD", "NEAR/USD", "ATOM/USD", "APT/USD", "SUI/USD",
        "SEI/USD", "TIA/USD", "INJ/USD", "EGLD/USD", "KAS/USD",
        "FTM/USD", "MINA/USD", "ALGO/USD", "ICP/USD", "HBAR/USD",
        "XTZ/USD", "FLOW/USD", "ROSE/USD", "CKB/USD", "ONE/USD",
        # L2 / Rollup Ecosystem
        "ARB/USD", "OP/USD", "MATIC/USD", "IMX/USD", "STRK/USD",
        "ZK/USD", "METIS/USD", "MANTA/USD", "BLAST/USD", "DYM/USD",
        "AEVO/USD", "ZETA/USD", "SKL/USD", "LRC/USD", "CELR/USD",
        # Oracle / Interop / Infra
        "LINK/USD", "PYTH/USD", "BAND/USD", "API3/USD", "AXL/USD",
        "W/USD", "SYN/USD", "RUNE/USD", "ZRO/USD", "GRT/USD",
        # DeFi Leaders
        "UNI/USD", "AAVE/USD", "MKR/USD", "LDO/USD", "SNX/USD",
        "CRV/USD", "COMP/USD", "PENDLE/USD", "MORPHO/USD", "JUP/USD",
        "JTO/USD", "RAY/USD", "DYDX/USD", "GMX/USD", "1INCH/USD",
        # RWA / Institutional
        "ONDO/USD", "CFG/USD", "POLYX/USD", "XDC/USD", "TRAC/USD",
        "MPL/USD", "OM/USD", "RIO/USD", "CHEX/USD", "LCX/USD",
        # AI / Compute / Agents
        "TAO/USD", "RNDR/USD", "FET/USD", "AGIX/USD", "AKT/USD",
        "OCEAN/USD", "AIOZ/USD", "NMR/USD", "VIRTUAL/USD", "PAAL/USD",
        # DePIN / Storage
        "FIL/USD", "AR/USD", "HNT/USD", "THETA/USD", "IOTX/USD",
        "FLUX/USD", "RLC/USD", "DIMO/USD", "MOBILE/USD", "AERO/USD",
        # Gaming / Metaverse
        "GALA/USD", "BEAM/USD", "PIXEL/USD", "AXS/USD", "SAND/USD",
        "MANA/USD", "RON/USD", "SUPER/USD", "ILV/USD", "YGG/USD",
        # Payments / Legacy
        "LTC/USD", "BCH/USD", "XLM/USD", "ETC/USD", "DASH/USD",
        "ZEC/USD", "BAT/USD", "ENJ/USD", "ZIL/USD", "QTUM/USD",
        # Exchange Tokens
        "OKB/USD", "CRO/USD", "BGB/USD", "KCS/USD", "GT/USD",
    ]

    # Tier 3 — Meme Coins (მაღალი ვოლატილობა, სწრაფი მოძრაობები)
    TIER_3_MEME_COINS = [
        "PEPE/USD", "WIF/USD", "BONK/USD", "FLOKI/USD",
        "BRETT/USD", "POPCAT/USD", "BOME/USD", "MYRO/USD",
    ]

    # Tier 4 — Narrative / Sector Mid-Caps (DeFi infra, cross-chain)
    TIER_4_NARRATIVE = [
        "SUSHI/USD", "CVX/USD", "KAVA/USD", "OSMO/USD",
        "STX/USD", "ORDI/USD", "SATS/USD",
    ]

    # Tier 5 — Emerging (ახალი პროექტები, ყველაზე მაღალი რისკი/reward)
    TIER_5_EMERGING = []

    CRYPTO      = TIER_1_BLUE_CHIPS + TIER_2_HIGH_GROWTH + TIER_3_MEME_COINS + TIER_4_NARRATIVE + TIER_5_EMERGING
    STOCKS      = []
    COMMODITIES = []

    # ═══════════════════════════════════════════════════════════════════════════
    # SCAN SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════

    SCAN_INTERVAL         = 300     # ✅ FIX #scalping — 5 წუთი (scalping-ს სჭირდება სწრაფი სკანირება)
    ASSET_DELAY           = 1.5     # წამი assets შორის
    NOTIFICATION_COOLDOWN = 1800    # 30 წუთი cooldown per symbol (scalping-ისთვის 6h override-ია სტრატეგიაში)
    MAX_HOLD_HOURS        = 240     # 10 დღე default max hold

    # ═══════════════════════════════════════════════════════════════════════════
    # AI SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════

    AI_MODEL                  = "claude-sonnet-4-5"   # Sonnet — fast + cheap
    AI_MAX_TOKENS             = 1200
    AI_ENTRY_THRESHOLD        = 50    # min score AI-სთვის გასაგზავნად
    AI_MIN_CONFIDENCE         = 50
    AI_CAUTION_THRESHOLD      = 60
    AI_HIGH_RISK_THRESHOLD    = 75
    AI_CONFIDENCE_HIGH        = 80
    AI_CONFIDENCE_LOW         = 45
    MIN_CONFIDENCE_FOR_AI     = 55   # strategy confidence >= ამ score-ამდე AI-ს ვიძახებთ

    # ═══════════════════════════════════════════════════════════════════════════
    # SIGNAL QUALITY GATES
    # ═══════════════════════════════════════════════════════════════════════════

    # ✅ v9.0 — AI filter is the real gate; artificial daily caps removed
    MAX_SIGNALS_PER_DAY           = 9999
    MAX_SIGNALS_PER_TIER_DAY = {
        "BLUE_CHIP":   9999,
        "HIGH_GROWTH": 9999,
        "MEME":        9999,
        "NARRATIVE":   9999,
        "EMERGING":    9999,
    }

    MIN_RR_RATIO                  = 1.5  # minimum Risk:Reward
    REQUIRE_VOLUME_CONFIRMATION   = True

    # ═══════════════════════════════════════════════════════════════════════════
    # TIER-BASED RISK PARAMETERS
    # ═══════════════════════════════════════════════════════════════════════════

    TIER_RISK = {
        "BLUE_CHIP": {
            "stop_loss_pct":  5.0,
            "take_profit_pct": 10.0,
            "min_confidence": 60,
            "min_rr":         1.5,
            "max_hold_hours": 504,   # 21 day
            "atr_stop_mult":  1.5,
            "atr_target_mult": 2.5,
        },
        "HIGH_GROWTH": {
            "stop_loss_pct":  6.0,
            "take_profit_pct": 14.0,
            "min_confidence": 58,
            "min_rr":         1.8,
            "max_hold_hours": 240,
            "atr_stop_mult":  1.8,
            "atr_target_mult": 3.0,
        },
        "MEME": {
            "stop_loss_pct":  7.0,
            "take_profit_pct": 20.0,
            "min_confidence": 62,
            "min_rr":         2.5,
            "max_hold_hours": 72,
            "atr_stop_mult":  2.0,
            "atr_target_mult": 4.0,
        },
        "NARRATIVE": {
            "stop_loss_pct":  6.5,
            "take_profit_pct": 16.0,
            "min_confidence": 60,
            "min_rr":         2.0,
            "max_hold_hours": 168,
            "atr_stop_mult":  1.8,
            "atr_target_mult": 3.2,
        },
        "EMERGING": {
            "stop_loss_pct":  8.0,
            "take_profit_pct": 20.0,
            "min_confidence": 63,
            "min_rr":         2.2,
            "max_hold_hours": 120,
            "atr_stop_mult":  2.2,
            "atr_target_mult": 4.0,
        },
    }

    # Default fallback
    DEFAULT_STOP_LOSS_PCT    = 5.0
    DEFAULT_TAKE_PROFIT_PCT  = 10.0

    # ═══════════════════════════════════════════════════════════════════════════
    # STRATEGY COOLDOWNS (საათებში)
    # ═══════════════════════════════════════════════════════════════════════════

    STRATEGY_COOLDOWNS = {
        "long_term":     48,
        "swing":         96,
        "scalping":       6,
        "opportunistic": 72,
    }

    # ═══════════════════════════════════════════════════════════════════════════
    # TECHNICAL INDICATOR SETTINGS
    # ═══════════════════════════════════════════════════════════════════════════

    RSI_PERIOD      = 14
    RSI_OVERBOUGHT  = 70
    RSI_OVERSOLD    = 30
    EMA_SHORT       = 50
    EMA_LONG        = 200
    BB_PERIOD       = 20
    BB_STD          = 2.0
    MACD_FAST       = 12
    MACD_SLOW       = 26
    MACD_SIGNAL_P   = 9
    ATR_PERIOD      = 14
    VOLUME_MA       = 20

    # ═══════════════════════════════════════════════════════════════════════════
    # FILES & PATHS
    # ═══════════════════════════════════════════════════════════════════════════

    SUBSCRIPTIONS_FILE    = "subscriptions.json"
    PAYMENT_REQUESTS_FILE = "payment_requests.json"
    ACTIVE_POSITIONS_FILE = "active_positions.json"
    KNOWLEDGE_BASE_FILE   = "trading_knowledge.json"
    ANALYTICS_DB          = "trading_analytics.db"
    SIGNAL_HISTORY_DB     = "signal_history.db"
    LOG_FILE              = "tradeally.log"
    LOG_MAX_BYTES         = 10 * 1024 * 1024
    LOG_BACKUP_COUNT      = 5

    # ═══════════════════════════════════════════════════════════════════════════
    # TELEGRAM MESSAGE TEMPLATES
    # ═══════════════════════════════════════════════════════════════════════════

    WELCOME_MSG_TEMPLATE = """👋 გამარჯობა @{username}!

    🤖 Trade Ally — AI Crypto Trading Bot

    📊 57 კრიპტო | 24/7 მონიტორინგი
    🧠 AI Risk Evaluator (Claude Sonnet)
    🎯 4 სტრატეგია | Real-time Exit Signals

    💰 Subscription: 150₾ / თვე

    /subscribe — გამოწერა
    /guide — სახელმძღვანელო
    /tiers — კატეგორიები"""

    PAYMENT_INSTRUCTIONS = """💳 გადახდის ინსტრუქცია

    თანხა: 150₾ / თვე

    გადახდის გზები:
    ━━━━━━━━━━━━━━━━━━
    🏦 TBC Bank
    IBAN: GE70BG0000000538913702
    დანიშნულება: შენი Telegram ID

    📱 UNISTREAM
    ნომერი: +995 XXX XX XX XX
    შენობა: შენი Telegram ID

    💎 USDT (TRC20)
    მისამართი: [WALLET_ADDRESS]

    ━━━━━━━━━━━━━━━━━━
    გადახდის შემდეგ:
    1. ქვითრის ფოტო — გამოაგზავნე ბოტზე
    2. Admin: 1-6 საათი
    3. Premium — 30 დღე"""

    TIER_DESCRIPTIONS = """📊 Asset კატეგორიები

    🔵 BLUE CHIP (Tier 1)
    BTC, ETH, BNB, SOL, XRP...
    → დაბალი რისკი | -5% stop | +10% target

    🟢 HIGH GROWTH (Tier 2)
    NEAR, ARB, SUI, INJ, APT...
    → საშუალო რისკი | -6% stop | +14% target

    🟡 MEME (Tier 3)
    DOGE, PEPE, WIF, BONK...
    → მაღალი რისკი | -7% stop | +20% target

    🟣 NARRATIVE (Tier 4)
    RNDR, FET, TAO, ONDO...
    → საშუალო-მაღალი | -6.5% stop | +16% target

    🔴 EMERGING (Tier 5)
    SEI, TIA, TON, ZK...
    → ყველაზე მაღალი | -8% stop | +20% target"""

    GUIDE_FOOTER = "\n\n⚠️ DYOR — არ არის ფინანსური რჩევა\n💡 Always use Stop-Loss!"

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_tier(symbol: str) -> str:
        if symbol in TIER_1_BLUE_CHIPS:   return "BLUE_CHIP"
        if symbol in TIER_2_HIGH_GROWTH:  return "HIGH_GROWTH"
        if symbol in TIER_3_MEME_COINS:   return "MEME"
        if symbol in TIER_4_NARRATIVE:    return "NARRATIVE"
        if symbol in TIER_5_EMERGING:     return "EMERGING"
        return "BLUE_CHIP"


    def get_tier_risk(tier: str) -> dict:
        return TIER_RISK.get(tier, TIER_RISK["HIGH_GROWTH"])


    def validate_config() -> bool:
        issues = []
        if not TELEGRAM_TOKEN:
            issues.append("TELEGRAM_TOKEN not set")
        if not ANTHROPIC_API_KEY:
            issues.append("ANTHROPIC_API_KEY not set")
        if ADMIN_ID == 0:
            issues.append("ADMIN_ID not set")

        if issues:
            for issue in issues:
                logger.error(f"❌ Config: {issue}")
            return False

        logger.info("✅ Config validated OK")
        return True