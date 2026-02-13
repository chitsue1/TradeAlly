"""
═══════════════════════════════════════════════════════════════════════════════
SCALPING STRATEGY - REFACTORED v2.0
═══════════════════════════════════════════════════════════════════════════════

STRATEGY NICHE: News-driven volatility + Ultra-short momentum bursts

CORE PHILOSOPHY:
- Capitalize on 1-hour volatility spikes
- News sentiment as PRIMARY filter (optional but preferred)
- Technical oversold as ENTRY trigger
- 10-60 minute holding period
- Quick profits (5-12%), tight stops (-4 to -6%)

KEY INDICATORS:
✅ PRIMARY: News sentiment (bullish keywords), RSI < 35, 1H volatility
✅ SECONDARY: Volume surge (>1.5x average), BB squeeze breakout
✅ TERTIARY: Multi-timeframe momentum (1H + 4H alignment)

CONFIDENCE THRESHOLD: 50% minimum (was 45%)
REASON: Scalping needs higher conviction due to tight stops

DIFFERENTIATION:
- vs Long-Term: Ultra-short holds, ignores macro trends
- vs Swing: News-reactive, not trend-following
- vs Opportunistic: Tighter stops, faster exits

NEWS INTEGRATION:
- Bullish keywords: "partnership", "integration", "mainnet", "burn"
- Bearish keywords: "hack", "exploit", "regulation" → AVOID
- News age: < 3 hours preferred

AUTHOR: Trading System Architecture Team
LAST UPDATE: 2024-02-05
"""

import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta

from .base_strategy import (
    BaseStrategy, TradingSignal, StrategyType,
    ConfidenceLevel, ActionType, MarketStructure
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# NEWS SENTIMENT ANALYZER (Lightweight)
# ═══════════════════════════════════════════════════════════════════════════

class NewsSentimentScorer:
    """
    Simple keyword-based news sentiment for scalping

    Focus: Quick bullish/bearish classification
    """

    BULLISH_KEYWORDS = {
        # Tier 1 (strong bullish)
        "partnership": 25,
        "integration": 25,
        "mainnet launch": 30,
        "token burn": 30,
        "listing": 20,
        "adoption": 20,

        # Tier 2 (moderate bullish)
        "upgrade": 15,
        "airdrop": 15,
        "staking": 12,
        "governance": 10,
        "audit passed": 15,
    }

    BEARISH_KEYWORDS = {
        "hack": -40,
        "exploit": -40,
        "delisting": -35,
        "regulation": -20,
        "sec": -15,
        "lawsuit": -25,
        "halt": -30,
    }

    @classmethod
    def score_text(cls, text: str) -> Tuple[int, str, List[str]]:
        """
        Score news text for sentiment

        Returns:
            (score: int, sentiment: str, keywords: List[str])

        Score range: -100 to +100
        Sentiment: "bullish", "bearish", "neutral"
        """
        text_lower = text.lower()
        score = 0
        matched_keywords = []

        # Check bullish
        for keyword, points in cls.BULLISH_KEYWORDS.items():
            if keyword in text_lower:
                score += points
                matched_keywords.append(keyword)

        # Check bearish
        for keyword, points in cls.BEARISH_KEYWORDS.items():
            if keyword in text_lower:
                score += points  # points are negative
                matched_keywords.append(f"⚠️ {keyword}")

        # Classify sentiment
        if score > 15:
            sentiment = "bullish"
        elif score < -10:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        return score, sentiment, matched_keywords

# ═══════════════════════════════════════════════════════════════════════════
# SCALPING STRATEGY
# ═══════════════════════════════════════════════════════════════════════════

class ScalpingStrategy(BaseStrategy):
    """
    სკალპინგის სტრატეგია - News-Driven Momentum

    ✅ REFACTORED: News sentiment integration, tighter risk management
    ✅ FOCUS: 1H volatility + news momentum + RSI oversold
    """

    def __init__(self):
        super().__init__(
            name="ScalpingStrategy",
            strategy_type=StrategyType.SCALPING
        )

        # Position tracking
        self.active_scalp_positions = set()
        self.last_signal_time = {}
        self.position_entry_times = {}

        # Configuration
        self.min_cooldown_hours = 6  # 6 hours between scalps
        self.min_confidence = 50.0   # Raised from 45% (tighter)
        self.auto_exit_minutes = 60  # Auto-close after 60 min

        # RSI thresholds (tighter than long-term)
        self.rsi_max_entry = 38
        self.rsi_optimal = 28

        # News sentiment scorer
        self.news_scorer = NewsSentimentScorer()

        logger.info(f"[{self.name}] Initialized with 60min auto-exit")

    # ═══════════════════════════════════════════════════════════════════════
    # MAIN ANALYSIS METHOD
    # ═══════════════════════════════════════════════════════════════════════

    def analyze(
        self,
        symbol: str,
        price: float,
        regime_analysis: Any,
        technical_data: Dict,
        tier: str,
        existing_position: Optional[object] = None,
        market_structure: Optional[MarketStructure] = None,
        news_text: Optional[str] = None  # ✅ NEWS INPUT
    ) -> Optional[TradingSignal]:
        """
        Scalping opportunity analysis

        ENTRY CONDITIONS:
        1. [OPTIONAL] Bullish news within last 3 hours
        2. [MANDATORY] High volatility (>60 percentile)
        3. [MANDATORY] RSI < 38 (oversold)
        4. [MANDATORY] Volume surge (>1.2x average)
        5. Confidence >= 50%
        """

        # ════════════════════════════════════════════════════════════════════
        # 1. PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════════════════

        if symbol in self.active_scalp_positions:
            logger.debug(
                f"[{self.name}] {symbol} active scalp position - "
                f"waiting for auto-exit"
            )
            return None

        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                self.active_scalp_positions.add(symbol)
                return None

        if not self._check_cooldown(symbol):
            return None

        # ════════════════════════════════════════════════════════════════════
        # 2. NEWS SENTIMENT ANALYSIS (Optional but preferred)
        # ════════════════════════════════════════════════════════════════════

        news_score = 0
        news_sentiment = "neutral"
        news_keywords = []
        has_bullish_news = False

        if news_text:
            news_score, news_sentiment, news_keywords = (
                self.news_scorer.score_text(news_text)
            )

            # REJECT bearish news immediately
            if news_sentiment == "bearish":
                logger.debug(
                    f"[{self.name}] {symbol} BEARISH news detected - "
                    f"blocking scalp ({news_keywords})"
                )
                return None

            # Bonus for bullish news
            if news_sentiment == "bullish" and news_score > 20:
                has_bullish_news = True
                logger.info(
                    f"[{self.name}] {symbol} BULLISH news: "
                    f"score={news_score} | {news_keywords[:2]}"
                )

        # ════════════════════════════════════════════════════════════════════
        # 3. EXTRACT TECHNICAL DATA
        # ════════════════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        bb_low = technical_data.get('bb_low', price)
        bb_high = technical_data.get('bb_high', price)

        volume = technical_data.get('volume', 0)
        avg_volume = technical_data.get('avg_volume_20d', volume)

        # ════════════════════════════════════════════════════════════════════
        # 4. CORE FILTERS (MANDATORY)
        # ════════════════════════════════════════════════════════════════════

        # Filter 1: Volatility must be elevated
        if regime_analysis.volatility_percentile < 60:
            logger.debug(
                f"[{self.name}] {symbol} volatility too low: "
                f"{regime_analysis.volatility_percentile:.0f}% (min 60%)"
            )
            return None

        # Filter 2: RSI oversold
        if rsi > self.rsi_max_entry:
            logger.debug(
                f"[{self.name}] {symbol} RSI too high: {rsi:.1f} "
                f"(max {self.rsi_max_entry})"
            )
            return None

        # Filter 3: Volume surge required
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        if volume_ratio < 1.2:
            logger.debug(
                f"[{self.name}] {symbol} volume surge insufficient: "
                f"{volume_ratio:.2f}x (min 1.2x)"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 5. BOLLINGER BAND POSITION
        # ════════════════════════════════════════════════════════════════════

        bb_range = bb_high - bb_low
        bb_position = (price - bb_low) / bb_range if bb_range > 0 else 0.5

        # Scalping prefers lower half of BB
        if bb_position > 0.55:
            logger.debug(
                f"[{self.name}] {symbol} price too high in BB: "
                f"{bb_position*100:.0f}% (max 55%)"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 6. TECHNICAL SCORING
        # ════════════════════════════════════════════════════════════════════

        technical_score = 0

        # RSI component (0-35 points)
        if rsi < 20:
            technical_score += 35
        elif rsi < 25:
            technical_score += 30
        elif rsi < self.rsi_optimal:
            technical_score += 25
        elif rsi < 32:
            technical_score += 18
        elif rsi < self.rsi_max_entry:
            technical_score += 10

        # BB position (0-25 points)
        if bb_position < 0.20:
            technical_score += 25
        elif bb_position < 0.35:
            technical_score += 20
        elif bb_position < 0.50:
            technical_score += 12
        elif bb_position < 0.55:
            technical_score += 5

        # Volatility component (0-20 points)
        if regime_analysis.volatility_percentile > 90:
            technical_score += 20
        elif regime_analysis.volatility_percentile > 80:
            technical_score += 15
        elif regime_analysis.volatility_percentile > 70:
            technical_score += 10
        elif regime_analysis.volatility_percentile >= 60:
            technical_score += 5

        # Volume surge (0-20 points)
        if volume_ratio > 2.5:
            technical_score += 20
        elif volume_ratio > 2.0:
            technical_score += 15
        elif volume_ratio > 1.5:
            technical_score += 12
        elif volume_ratio >= 1.2:
            technical_score += 8

        # ════════════════════════════════════════════════════════════════════
        # 7. NEWS SCORING (Bonus component)
        # ════════════════════════════════════════════════════════════════════

        news_score_normalized = 0

        if has_bullish_news:
            # Convert news_score (0-100) to confidence contribution
            news_score_normalized = min(news_score, 100)

        # ════════════════════════════════════════════════════════════════════
        # 8. STRUCTURE SCORING
        # ════════════════════════════════════════════════════════════════════

        structure_score = 50  # default

        if market_structure:
            # Momentum alignment
            if market_structure.momentum_score > 30:
                structure_score += 20
            elif market_structure.momentum_score > 10:
                structure_score += 10

            # 1H timeframe must be bullish for scalping
            if market_structure.tf_1h_trend == "bullish":
                structure_score += 15
            elif market_structure.tf_1h_trend == "neutral":
                structure_score += 5

        structure_score = min(structure_score, 100)

        # ════════════════════════════════════════════════════════════════════
        # 9. CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════════════════

        # If news exists, boost confidence
        if has_bullish_news:
            confidence_level, confidence_score = self._calculate_confidence(
                regime_confidence=regime_analysis.confidence,
                technical_score=technical_score,
                structure_score=structure_score,
                volume_score=min(volume_ratio * 50, 100),
                multi_tf_alignment=news_score_normalized  # News as TF proxy
            )
        else:
            # Pure technical confidence
            confidence_level, confidence_score = self._calculate_confidence(
                regime_confidence=regime_analysis.confidence,
                technical_score=technical_score,
                structure_score=structure_score,
                volume_score=min(volume_ratio * 50, 100),
                multi_tf_alignment=50  # neutral
            )

        # ✅ THRESHOLD: 50% (raised from 45%)
        if confidence_score < self.min_confidence:
            logger.debug(
                f"[{self.name}] {symbol} confidence insufficient: "
                f"{confidence_score:.1f}% (min {self.min_confidence}%)"
            )
            return None

        # ════════════════════════════════════════════════════════════════════
        # 10. TIER-BASED TARGETS
        # ════════════════════════════════════════════════════════════════════

        tier_config = self._get_tier_config(tier, has_bullish_news)

        # ════════════════════════════════════════════════════════════════════
        # 11. STOP LOSS CALCULATION (Tight for scalping)
        # ════════════════════════════════════════════════════════════════════

        # Base stop: -5% (tighter than other strategies)
        base_stop_pct = 5.0

        # Adjust for volatility
        if regime_analysis.volatility_percentile > 90:
            base_stop_pct = 6.0  # Slightly wider in extreme volatility
        elif regime_analysis.volatility_percentile < 70:
            base_stop_pct = 4.0  # Tighter in lower volatility

        # With news: slightly tighter (news can reverse quickly)
        if has_bullish_news:
            base_stop_pct = max(base_stop_pct - 0.5, 4.0)

        stop_loss_price = price * (1 - base_stop_pct / 100)

        # ════════════════════════════════════════════════════════════════════
        # 12. REASONING CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        primary_reason = self._build_primary_reason(
            symbol=symbol,
            has_news=has_bullish_news,
            news_keywords=news_keywords,
            rsi=rsi,
            volume_ratio=volume_ratio,
            volatility=regime_analysis.volatility_percentile
        )

        supporting_reasons = self._build_supporting_reasons(
            has_news=has_bullish_news,
            news_score=news_score,
            rsi=rsi,
            bb_position=bb_position,
            volume_ratio=volume_ratio,
            volatility=regime_analysis.volatility_percentile
        )

        risk_factors = self._build_risk_factors(
            volatility=regime_analysis.volatility_percentile,
            has_news=has_bullish_news,
            volume_ratio=volume_ratio
        )

        # ════════════════════════════════════════════════════════════════════
        # 13. RISK ASSESSMENT
        # ════════════════════════════════════════════════════════════════════

        volume_trend = (
            "increasing" if volume_ratio > 1.5 else
            "decreasing" if volume_ratio < 0.8 else
            "stable"
        )

        risk_level = self._assess_risk_level(
            volatility_percentile=regime_analysis.volatility_percentile,
            volume_trend=volume_trend,
            structure_quality=structure_score,
            warning_count=len(regime_analysis.warning_flags)
        )

        # Scalping is inherently higher risk
        if risk_level == "LOW":
            risk_level = "MEDIUM"  # Minimum risk for scalping

        # ════════════════════════════════════════════════════════════════════
        # 14. SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.SCALPING,
            entry_price=price,
            target_price=price * (1 + tier_config['target'] / 100),
            stop_loss_price=stop_loss_price,
            expected_hold_duration=tier_config['hold'],
            entry_timestamp=datetime.now().isoformat(),
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            risk_level=risk_level,
            primary_reason=primary_reason,
            supporting_reasons=supporting_reasons,
            risk_factors=risk_factors,
            expected_profit_min=tier_config['target'] * 0.5,
            expected_profit_max=tier_config['target'] * 1.3,
            market_regime=regime_analysis.regime.value,
            market_structure=market_structure,
            requires_sell_notification=True,
            technical_scores={
                'rsi': rsi,
                'technical_score': technical_score,
                'news_score': news_score,
                'volume_ratio': volume_ratio,
                'volatility': regime_analysis.volatility_percentile
            },
            timeframe_context={
                'news_driven': str(has_bullish_news),
                'auto_exit_minutes': str(self.auto_exit_minutes)
            }
        )

        logger.info(
            f"✅ [{self.name}] {symbol} SCALP SIGNAL\n"
            f"   Entry: ${price:.4f} | Target: ${signal.target_price:.4f}\n"
            f"   Stop: ${stop_loss_price:.4f} (-{base_stop_pct:.1f}%)\n"
            f"   Confidence: {confidence_score:.1f}% | News: {has_bullish_news}\n"
            f"   RSI: {rsi:.1f} | Vol: {volume_ratio:.2f}x | Auto-exit: 60min"
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL VALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    def should_send_signal(
        self,
        symbol: str,
        signal: TradingSignal
    ) -> tuple[bool, str]:
        """Final validation before sending"""

        # Confidence check
        if signal.confidence_score < self.min_confidence:
            return False, f"confidence too low ({signal.confidence_score:.1f}%)"

        # Extreme risk block (even for scalping)
        if signal.risk_level == "EXTREME" and signal.confidence_score < 65:
            return False, "EXTREME risk with low confidence"

        # Position check
        if symbol in self.active_scalp_positions:
            return False, "active scalp position exists"

        # R:R check (minimum 1:1 for scalping)
        if signal.risk_reward_ratio < 1.0:
            return False, f"R:R too low ({signal.risk_reward_ratio:.2f})"

        # Register position
        self.active_scalp_positions.add(symbol)
        self.last_signal_time[symbol] = datetime.now()
        self.position_entry_times[symbol] = datetime.now()

        self.record_activity()

        logger.info(
            f"[{self.name}] ✅ {symbol} SCALP approved\n"
            f"   Confidence: {signal.confidence_score:.1f}%\n"
            f"   R:R: 1:{signal.risk_reward_ratio:.2f}\n"
            f"   Auto-exit: 60 minutes"
        )

        return True, "scalp conditions met"

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def check_auto_exit(self, symbol: str) -> bool:
        """
        Check if position should auto-exit due to time limit

        Returns:
            True if position should close
        """
        if symbol not in self.position_entry_times:
            return False

        entry_time = self.position_entry_times[symbol]
        minutes_elapsed = (
            (datetime.now() - entry_time).total_seconds() / 60
        )

        if minutes_elapsed >= self.auto_exit_minutes:
            logger.warning(
                f"[{self.name}] ⏰ {symbol} AUTO-EXIT triggered "
                f"({minutes_elapsed:.0f} min elapsed)"
            )
            return True

        return False

    def mark_position_closed(self, symbol: str):
        """Mark scalp position as closed"""
        if symbol in self.active_scalp_positions:
            self.active_scalp_positions.remove(symbol)
            self.position_entry_times.pop(symbol, None)

            logger.info(
                f"[{self.name}] ✅ {symbol} scalp closed - "
                f"new signals allowed after cooldown"
            )

    def clear_position(self, symbol: str):
        """Alias"""
        self.mark_position_closed(symbol)

    def get_active_positions(self) -> set:
        """Get active scalp positions"""
        return self.active_scalp_positions.copy()

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _check_cooldown(self, symbol: str) -> bool:
        """Check 6-hour cooldown"""
        if symbol not in self.last_signal_time:
            return True

        last_time = self.last_signal_time[symbol]
        hours_since = (datetime.now() - last_time).total_seconds() / 3600

        if hours_since < self.min_cooldown_hours:
            logger.debug(
                f"[{self.name}] {symbol} cooldown active "
                f"({hours_since:.1f}h / {self.min_cooldown_hours}h)"
            )
            return False

        return True

    def _get_tier_config(
        self,
        tier: str,
        has_news: bool
    ) -> Dict:
        """Tier-specific configuration with news adjustment"""

        base_configs = {
            "BLUE_CHIP": {"target": 5.0, "hold": "20-40 წუთი"},
            "HIGH_GROWTH": {"target": 8.0, "hold": "15-35 წუთი"},
            "MEME": {"target": 12.0, "hold": "10-25 წუთი"},
            "NARRATIVE": {"target": 9.0, "hold": "15-30 წუთი"},
            "EMERGING": {"target": 10.0, "hold": "15-35 წუთი"}
        }

        config = base_configs.get(tier, base_configs["HIGH_GROWTH"])

        # Boost target if news-driven (momentum can carry further)
        if has_news:
            config['target'] *= 1.2

        return config

    def _build_primary_reason(
        self,
        symbol: str,
        has_news: bool,
        news_keywords: List[str],
        rsi: float,
        volume_ratio: float,
        volatility: float
    ) -> str:
        """Build primary reasoning"""

        reason = f"{symbol} "

        if has_news:
            reason += f"🔥 ახალი სიახლე ({', '.join(news_keywords[:2])}) + "

        reason += f"მაღალ ვოლატილობაში ({volatility:.0f}%) და "

        if rsi < 25:
            reason += "ძლიერად გადაყიდულია"
        elif rsi < 32:
            reason += "oversold ზონაშია"
        else:
            reason += "pullback-ში"

        reason += f". მოცულობა გაზრდილია ({volume_ratio:.1f}x). "

        reason += "სწრაფი bounce-ის პოტენციალი 10-60 წუთში."

        return reason

    def _build_supporting_reasons(
        self,
        has_news: bool,
        news_score: int,
        rsi: float,
        bb_position: float,
        volume_ratio: float,
        volatility: float
    ) -> List[str]:
        """Build supporting reasons"""

        reasons = []

        if has_news:
            reasons.append(f"📰 Bullish news detected (score: {news_score})")

        reasons.append(f"🔵 RSI oversold: {rsi:.1f}")

        if bb_position < 0.30:
            reasons.append(f"📉 BB lower zone (deep pullback)")

        reasons.append(f"📊 Volume surge: {volume_ratio:.2f}x average")
        reasons.append(f"⚡ High volatility: {volatility:.0f}%")

        return reasons[:4]

    def _build_risk_factors(
        self,
        volatility: float,
        has_news: bool,
        volume_ratio: float
    ) -> List[str]:
        """Build risk factors"""

        factors = []

        factors.append("⚠️ სკალპინგი - სწრაფი exit აუცილებელია (60წთ)")

        if volatility > 85:
            factors.append(f"⚠️ ძალიან მაღალი ვოლატილობა ({volatility:.0f}%)")

        if has_news:
            factors.append("⚠️ News-driven - momentum შეიძლება სწრაფად შეიცვალოს")

        if volume_ratio < 1.5:
            factors.append("⚠️ მოცულობა არასაკმარისად მაღალია")

        factors.append("💨 High risk / High reward")

        return factors[:4]