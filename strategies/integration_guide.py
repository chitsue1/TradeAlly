"""
═══════════════════════════════════════════════════════════════════════════════
STRATEGY INTEGRATION GUIDE - REFACTORED v2.0
═══════════════════════════════════════════════════════════════════════════════

როგორ მივაერთოთ გაუმჯობესებული სტრატეგიები Trading Engine-ს

AUTHOR: Trading System Architecture Team
LAST UPDATE: 2024-02-05
"""

# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: IMPORT ALL STRATEGIES
# ═══════════════════════════════════════════════════════════════════════════

from strategies.base_strategy import (
    BaseStrategy,
    TradingSignal,
    StrategyType,
    ActionType,
    ConfidenceLevel,
    MarketStructure
)

from strategies.long_term_strategy import LongTermStrategy
from strategies.swing_strategy import SwingStrategy
from strategies.scalping_strategy import ScalpingStrategy
from strategies.opportunistic_strategy import OpportunisticStrategy

# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: INITIALIZE STRATEGY REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

class StrategyRegistry:
    """
    ცენტრალური სტრატეგიების რეესტრი

    Manages all active strategies and their execution
    """

    def __init__(self):
        # Initialize strategies
        self.long_term = LongTermStrategy()
        self.swing = SwingStrategy()
        self.scalping = ScalpingStrategy()
        self.opportunistic = OpportunisticStrategy()

        # Strategy map
        self.strategies = {
            'long_term': self.long_term,
            'swing': self.swing,
            'scalping': self.scalping,
            'opportunistic': self.opportunistic
        }

        # Active signals tracker
        self.active_signals = {}

        logger.info("✅ Strategy Registry initialized with 4 strategies")

    def get_all_strategies(self) -> list:
        """Get list of all strategies"""
        return list(self.strategies.values())

    def get_strategy(self, name: str) -> BaseStrategy:
        """Get specific strategy by name"""
        return self.strategies.get(name)

    def get_stats(self) -> dict:
        """Get stats for all strategies"""
        return {
            name: strategy.get_stats()
            for name, strategy in self.strategies.items()
        }

# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: PREPARE MARKET STRUCTURE DATA
# ═══════════════════════════════════════════════════════════════════════════

def prepare_market_structure(
    symbol: str,
    price: float,
    technical_data: dict,
    regime_analysis
) -> MarketStructure:
    """
    Prepare MarketStructure object for strategies

    ეს არის CRITICAL - სტრატეგიები ელოდებიან MarketStructure ობიექტს
    """

    # Extract support/resistance (example logic)
    # In production, this should use your actual support/resistance detection
    nearest_support = technical_data.get('support_level', price * 0.95)
    nearest_resistance = technical_data.get('resistance_level', price * 1.05)

    # Support/resistance strength (0-100)
    support_strength = technical_data.get('support_strength', 50)
    resistance_strength = technical_data.get('resistance_strength', 50)

    # Volume analysis
    volume = technical_data.get('volume', 0)
    avg_volume = technical_data.get('avg_volume_20d', volume)
    volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

    if volume_ratio > 1.3:
        volume_trend = "increasing"
    elif volume_ratio < 0.8:
        volume_trend = "decreasing"
    else:
        volume_trend = "stable"

    volume_percentile = min(volume_ratio * 70, 100)

    # Momentum score (-100 to +100)
    # Example: based on MACD or price momentum
    macd_histogram = technical_data.get('macd_histogram', 0)
    momentum_score = min(max(macd_histogram * 100, -100), 100)

    # Trend strength (0-100)
    ema50 = technical_data.get('ema50', price)
    ema200 = technical_data.get('ema200', price)

    if ema50 > ema200:
        trend_strength = min(((ema50 - ema200) / ema200) * 1000, 100)
    else:
        trend_strength = 0

    # Volatility regime
    vol_pct = regime_analysis.volatility_percentile

    if vol_pct > 90:
        volatility_regime = "extreme"
    elif vol_pct > 70:
        volatility_regime = "high"
    elif vol_pct > 40:
        volatility_regime = "normal"
    else:
        volatility_regime = "low"

    # Multi-timeframe trends
    # These should come from your actual timeframe analysis
    # For now, example logic:
    rsi = technical_data.get('rsi', 50)

    if rsi > 55:
        tf_1h_trend = "bullish"
    elif rsi < 45:
        tf_1h_trend = "bearish"
    else:
        tf_1h_trend = "neutral"

    # 4H trend (example: based on EMA200 position)
    if price > ema200 * 1.02:
        tf_4h_trend = "bullish"
    elif price < ema200 * 0.98:
        tf_4h_trend = "bearish"
    else:
        tf_4h_trend = "neutral"

    # 1D trend (example: from regime analysis)
    if hasattr(regime_analysis, 'is_structural') and regime_analysis.is_structural:
        tf_1d_trend = "bullish"
    elif hasattr(regime_analysis, 'regime'):
        regime_str = str(regime_analysis.regime.value)
        if "up" in regime_str:
            tf_1d_trend = "bullish"
        elif "down" in regime_str:
            tf_1d_trend = "bearish"
        else:
            tf_1d_trend = "neutral"
    else:
        tf_1d_trend = "neutral"

    # Alignment score
    trend_map = {"bullish": 100, "neutral": 50, "bearish": 0}
    alignment_score = (
        trend_map.get(tf_1h_trend, 50) * 0.2 +
        trend_map.get(tf_4h_trend, 50) * 0.3 +
        trend_map.get(tf_1d_trend, 50) * 0.5
    )

    # Create MarketStructure object
    market_structure = MarketStructure(
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
        support_strength=support_strength,
        resistance_strength=resistance_strength,
        volume_trend=volume_trend,
        volume_percentile=volume_percentile,
        momentum_score=momentum_score,
        trend_strength=trend_strength,
        volatility_regime=volatility_regime,
        volatility_percentile=vol_pct,
        tf_1h_trend=tf_1h_trend,
        tf_4h_trend=tf_4h_trend,
        tf_1d_trend=tf_1d_trend,
        alignment_score=alignment_score
    )

    return market_structure

# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: SCAN CYCLE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

class TradingEngine:
    """
    მთავარი Trading Engine

    Integrates all strategies and executes scan cycles
    """

    def __init__(self, telegram_bot=None):
        # Initialize strategy registry
        self.strategy_registry = StrategyRegistry()

        # Telegram bot (for sending signals)
        self.telegram_bot = telegram_bot

        # Analytics (if available)
        self.analytics_db = None  # Initialize if using analytics

        # Position tracker
        self.positions = {}  # symbol -> Position object

        logger.info("✅ Trading Engine initialized")

    def scan_symbol(
        self,
        symbol: str,
        price: float,
        regime_analysis,
        technical_data: dict,
        tier: str,
        news_text: Optional[str] = None
    ):
        """
        Scan single symbol across all strategies

        Args:
            symbol: Crypto symbol (e.g., "BTCUSDT")
            price: Current price
            regime_analysis: Market regime object
            technical_data: Dict with RSI, EMA, BB, MACD, volume, etc.
            tier: Asset tier ("BLUE_CHIP", "HIGH_GROWTH", etc.)
            news_text: Optional recent news text
        """

        # Prepare market structure
        market_structure = prepare_market_structure(
            symbol=symbol,
            price=price,
            technical_data=technical_data,
            regime_analysis=regime_analysis
        )

        # Get existing position (if any)
        existing_position = self.positions.get(symbol)

        # Try each strategy
        for strategy_name, strategy in self.strategy_registry.strategies.items():

            try:
                # Analyze
                signal = strategy.analyze(
                    symbol=symbol,
                    price=price,
                    regime_analysis=regime_analysis,
                    technical_data=technical_data,
                    tier=tier,
                    existing_position=existing_position,
                    market_structure=market_structure,
                    news_text=news_text  # Scalping & Opportunistic use this
                )

                # If signal generated
                if signal:
                    # Validate
                    should_send, reason = strategy.should_send_signal(
                        symbol=symbol,
                        signal=signal
                    )

                    if should_send:
                        # Send to Telegram
                        self._send_signal_to_telegram(signal)

                        # Record in analytics (if available)
                        if self.analytics_db:
                            signal_id = self.analytics_db.record_signal(signal)

                            # Track signal
                            self.strategy_registry.active_signals[symbol] = {
                                'signal_id': signal_id,
                                'signal': signal,
                                'strategy': strategy_name
                            }

                        logger.info(
                            f"✅ [{strategy_name}] {symbol} SIGNAL SENT TO TELEGRAM"
                        )
                    else:
                        logger.debug(
                            f"[{strategy_name}] {symbol} signal blocked: {reason}"
                        )

            except Exception as e:
                logger.error(
                    f"❌ [{strategy_name}] {symbol} error: {e}",
                    exc_info=True
                )

    def _send_signal_to_telegram(self, signal: TradingSignal):
        """
        გაგზავნე სიგნალი Telegram-ში

        ✅ IMPORTANT: This uses signal.to_message() - unchanged from original
        """
        if not self.telegram_bot:
            logger.warning("⚠️ Telegram bot not configured")
            return

        try:
            # Generate message using signal's to_message() method
            message = signal.to_message()

            # Send via Telegram bot
            # (Exact implementation depends on your bot setup)
            # Example:
            # self.telegram_bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)

            logger.info(f"📤 Telegram message sent for {signal.symbol}")

        except Exception as e:
            logger.error(f"❌ Telegram send failed: {e}", exc_info=True)

    def update_positions(self, current_prices: dict):
        """
        Update active positions and check target/stop hits

        Args:
            current_prices: Dict of {symbol: current_price}
        """

        for symbol, signal_data in list(self.strategy_registry.active_signals.items()):

            if symbol not in current_prices:
                continue

            current_price = current_prices[symbol]
            signal = signal_data['signal']
            strategy_name = signal_data['strategy']

            # Calculate profit %
            profit_pct = (
                (current_price - signal.entry_price) / signal.entry_price * 100
            )

            # Check target hit
            if current_price >= signal.target_price:
                logger.info(
                    f"🎯 [{strategy_name}] {symbol} TARGET HIT! "
                    f"Profit: {profit_pct:+.2f}%"
                )

                # Send Telegram notification
                if self.telegram_bot:
                    self._send_exit_notification(
                        signal=signal,
                        exit_price=current_price,
                        reason="TARGET_HIT",
                        profit_pct=profit_pct
                    )

                # Record performance (if analytics available)
                if self.analytics_db:
                    self.analytics_db.record_performance(
                        signal_id=signal_data['signal_id'],
                        outcome='SUCCESS',
                        final_profit_pct=profit_pct,
                        exit_reason='TARGET_HIT'
                    )

                # Clear position in strategy
                strategy = self.strategy_registry.get_strategy(strategy_name)
                if strategy:
                    strategy.mark_position_closed(symbol)
                    strategy.record_outcome(success=True)

                # Remove from active signals
                del self.strategy_registry.active_signals[symbol]

            # Check stop loss hit
            elif current_price <= signal.stop_loss_price:
                logger.warning(
                    f"🛑 [{strategy_name}] {symbol} STOP LOSS HIT! "
                    f"Loss: {profit_pct:+.2f}%"
                )

                # Send Telegram notification
                if self.telegram_bot:
                    self._send_exit_notification(
                        signal=signal,
                        exit_price=current_price,
                        reason="STOP_LOSS",
                        profit_pct=profit_pct
                    )

                # Record performance
                if self.analytics_db:
                    self.analytics_db.record_performance(
                        signal_id=signal_data['signal_id'],
                        outcome='FAILURE',
                        final_profit_pct=profit_pct,
                        exit_reason='STOP_LOSS'
                    )

                # Clear position
                strategy = self.strategy_registry.get_strategy(strategy_name)
                if strategy:
                    strategy.mark_position_closed(symbol)
                    strategy.record_outcome(success=False)

                # Remove from active
                del self.strategy_registry.active_signals[symbol]

            # Otherwise, record price update (if analytics)
            elif self.analytics_db:
                self.analytics_db.record_price_update(
                    signal_id=signal_data['signal_id'],
                    symbol=symbol,
                    current_price=current_price,
                    entry_price=signal.entry_price,
                    target_price=signal.target_price,
                    stop_loss=signal.stop_loss_price
                )

    def _send_exit_notification(
        self,
        signal: TradingSignal,
        exit_price: float,
        reason: str,
        profit_pct: float
    ):
        """Send exit notification to Telegram"""

        emoji = "🎯" if reason == "TARGET_HIT" else "🛑"

        message = f"""
{emoji} **{reason.replace('_', ' ')}**

**Asset:** {signal.symbol}
**Strategy:** {signal.strategy_type.value.upper()}

**Entry:** ${signal.entry_price:.4f}
**Exit:** ${exit_price:.4f}
**Profit:** {profit_pct:+.2f}%

**Hold Duration:** {signal.expected_hold_duration}
**Confidence Was:** {signal.confidence_score:.0f}%
        """

        # Send via bot (implementation depends on your bot)
        # self.telegram_bot.send_message(ADMIN_CHAT_ID, message)

        logger.info(f"📤 Exit notification sent for {signal.symbol}")

# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: TELEGRAM COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

# Example Telegram command handlers (adjust to your bot framework)

"""
@bot.message_handler(commands=['stats'])
def show_strategy_stats(message):
    '''Display stats for all strategies'''

    if message.from_user.id != ADMIN_ID:
        return

    stats = engine.strategy_registry.get_stats()

    text = "📊 **STRATEGY STATISTICS**\\n\\n"

    for strategy_name, strategy_stats in stats.items():
        text += f"**{strategy_name.upper()}:**\\n"
        text += f"• Signals: {strategy_stats['signals_generated']}\\n"
        text += f"• Win Rate: {strategy_stats.get('win_rate', 'N/A')}\\n"
        text += f"• Last Active: {strategy_stats['last_activity']}\\n\\n"

    bot.send_message(message.chat.id, text, parse_mode='Markdown')


@bot.message_handler(commands=['active'])
def show_active_signals(message):
    '''Display all active signals'''

    if message.from_user.id != ADMIN_ID:
        return

    active = engine.strategy_registry.active_signals

    if not active:
        bot.send_message(message.chat.id, "📭 No active signals")
        return

    text = "📊 **ACTIVE SIGNALS:**\\n\\n"

    for symbol, data in active.items():
        signal = data['signal']
        strategy = data['strategy']

        profit_pct = (
            (current_prices.get(symbol, signal.entry_price) - signal.entry_price) 
            / signal.entry_price * 100
        )

        text += f"**{symbol}** ({strategy})\\n"
        text += f"• Entry: ${signal.entry_price:.4f}\\n"
        text += f"• Target: ${signal.target_price:.4f}\\n"
        text += f"• Current P/L: {profit_pct:+.2f}%\\n\\n"

    bot.send_message(message.chat.id, text, parse_mode='Markdown')
"""

# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: EXAMPLE MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════

"""
def main_scan_loop():
    '''
    Main scan loop - runs continuously
    '''

    engine = TradingEngine(telegram_bot=bot)

    # Load watchlist
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", ...]

    while True:
        try:
            logger.info("🔍 Starting scan cycle...")

            for symbol in symbols:
                # Fetch current data
                price = fetch_current_price(symbol)
                regime_analysis = analyze_market_regime(symbol)
                technical_data = calculate_technical_indicators(symbol)
                tier = get_asset_tier(symbol)

                # Optional: fetch recent news
                news_text = fetch_recent_news(symbol)  # or None

                # Scan symbol
                engine.scan_symbol(
                    symbol=symbol,
                    price=price,
                    regime_analysis=regime_analysis,
                    technical_data=technical_data,
                    tier=tier,
                    news_text=news_text
                )

            # Update active positions
            current_prices = {
                symbol: fetch_current_price(symbol) 
                for symbol in engine.strategy_registry.active_signals.keys()
            }
            engine.update_positions(current_prices)

            logger.info("✅ Scan cycle complete")

            # Wait before next cycle (e.g., 5 minutes)
            time.sleep(300)

        except Exception as e:
            logger.error(f"❌ Scan cycle error: {e}", exc_info=True)
            time.sleep(60)
"""

# ═══════════════════════════════════════════════════════════════════════════
# KEY POINTS
# ═══════════════════════════════════════════════════════════════════════════

"""
✅ TELEGRAM INTEGRATION: Unchanged - uses signal.to_message()

✅ STRATEGY DIFFERENTIATION:
   - Long-Term: EMA200 trend + deep RSI pullbacks (1-3 weeks)
   - Swing: EMA50/200 golden cross + MACD momentum (4-10 days)
   - Scalping: News sentiment + volatility spikes (10-60 min)
   - Opportunistic: BB squeeze + RSI divergence (1-7 days)

✅ CONFIDENCE THRESHOLDS:
   - Long-Term: 55% (lowered for more opportunities)
   - Swing: 55%
   - Scalping: 50% (raised for tighter stops)
   - Opportunistic: 60% (higher risk needs higher conviction)

✅ MARKET STRUCTURE:
   - All strategies now receive MarketStructure object
   - Includes multi-timeframe trends, support/resistance, momentum
   - Improves confidence calculation and risk assessment

✅ NEWS INTEGRATION:
   - Scalping: Primary filter (blocks bearish news)
   - Opportunistic: Optional catalyst (boosts confidence)
   - Long-Term & Swing: Not used (pure technical)

✅ ANALYTICS:
   - Optional but recommended
   - Tracks signal performance
   - Monitors strategy win rates
   - Helps with strategy optimization
"""