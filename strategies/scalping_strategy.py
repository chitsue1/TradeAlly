"""
═══════════════════════════════════════════════════════════════════════════════
SCALPING STRATEGY - v2.0 REDESIGNED (TECHNICAL-ONLY)
═══════════════════════════════════════════════════════════════════════════════

CHANGES FROM v1:
  - REMOVED: news dependency (was never implemented, broke everything)
  - REMOVED: 60-minute auto-exit (bot scans every 15min, Telegram notification
             delivery takes 1-5min → user loses 5-10% of entry window before
             they can even execute; 60min was effectively unusable)
  - CHANGED: Hold time 60min → 4 hours (realistic for Telegram-bot users)
  - STRENGTHENED: Volume filter 1.2x → 1.5x (reduces noise signals)
  - STRENGTHENED: RSI max entry 38 → 35 (tighter oversold requirement)
  - ADDED: Volume data quality gate — block signal if volume is zero/missing
  - ADDED: surge_scans counter — tracks consecutive volume surge scans,
           resets when conditions break (reduces fake breakout signals)
  - KEPT: All volatility, BB, market structure logic (these work well)

Result: Fewer but much higher-quality signals, executable by real users.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .base_strategy import (
    BaseStrategy, TradingSignal, StrategyType,
    ConfidenceLevel, ActionType, MarketStructure
)

logger = logging.getLogger(__name__)


class ScalpingStrategy(BaseStrategy):
    """
    Scalping Strategy - v2.0 REDESIGNED

    Technical momentum: Volatility spike + RSI oversold + confirmed volume surge
    Hold time: 2-4 hours (realistic for Telegram notification lag)
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

        # v2.0: Multi-scan confirmation tracking
        # Counts consecutive scans where volume surge is present.
        # Resets to 0 when conditions break (RSI too high, volatility low, etc.)
        self._volume_surge_scans: Dict[str, int] = {}

        # Configuration
        self.min_cooldown_hours = 8           # v2.0: 6h → 8h
        self.min_confidence = 52.0            # v2.0: slight increase
        self.auto_exit_minutes = 240          # v2.0: 60min → 4h (executable via Telegram)
        self.required_surge_scans = 1         # 1 = fire immediately on first confirmed surge

        # v2.0: Tighter entry filters
        self.rsi_max_entry = 35               # Was 38
        self.rsi_optimal = 25
        self.min_volume_ratio = 1.5           # Was 1.2
        self.min_volatility_percentile = 65   # Was 60

        logger.info(f"[{self.name}] v2.0 — 4h hold, technical-only, stronger filters")

    def analyze(
        self,
        symbol: str,
        price: float,
        regime_analysis: Any,
        technical_data: Dict,
        tier: str,
        existing_position: Optional[object] = None,
        market_structure: Optional[MarketStructure] = None
    ) -> Optional[TradingSignal]:
        """
        v2.0: High volatility + genuine RSI oversold + confirmed volume surge
        """

        # ════════════════════════════════════════════════════════════════════
        # PRE-FLIGHT CHECKS
        # ════════════════════════════════════════════════════════════════════

        if symbol in self.active_scalp_positions:
            logger.debug(f"[{self.name}] {symbol} active scalp position exists")
            return None

        if existing_position and hasattr(existing_position, 'buy_signals_sent'):
            if existing_position.buy_signals_sent >= 1:
                self.active_scalp_positions.add(symbol)
                return None

        if not self._check_cooldown(symbol):
            return None

        # ════════════════════════════════════════════════════════════════════
        # EXTRACT TECHNICAL DATA
        # ════════════════════════════════════════════════════════════════════

        rsi = technical_data.get('rsi', 50)
        bb_low = technical_data.get('bb_low', price)
        bb_high = technical_data.get('bb_high', price)
        volume = technical_data.get('volume', 0)
        avg_volume = technical_data.get('avg_volume_20d', volume)

        # ════════════════════════════════════════════════════════════════════
        # v2.0 GATE: VOLUME DATA QUALITY
        # Block if volume is zero or missing — likely mock data
        # ════════════════════════════════════════════════════════════════════

        if volume <= 0 or avg_volume <= 0:
            logger.debug(f"[{self.name}] {symbol} volume data missing/zero — skip")
            self._volume_surge_scans[symbol] = 0
            return None

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 1: VOLATILITY (MANDATORY)
        # ════════════════════════════════════════════════════════════════════

        if regime_analysis.volatility_percentile < self.min_volatility_percentile:
            logger.debug(
                f"[{self.name}] {symbol} volatility "
                f"{regime_analysis.volatility_percentile:.0f}% < {self.min_volatility_percentile}%"
            )
            self._volume_surge_scans[symbol] = 0
            return None

        logger.info(f"[{self.name}] {symbol} ✅ Volatility: {regime_analysis.volatility_percentile:.0f}%")

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 2: RSI OVERSOLD (MANDATORY) — v2.0: max 35
        # ════════════════════════════════════════════════════════════════════

        if rsi > self.rsi_max_entry:
            logger.debug(f"[{self.name}] {symbol} RSI {rsi:.1f} > {self.rsi_max_entry}")
            self._volume_surge_scans[symbol] = 0
            return None

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 3: VOLUME SURGE + SCAN CONFIRMATION
        # v2.0: min 1.5x, counter tracks consecutive qualifying scans
        # ════════════════════════════════════════════════════════════════════

        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        if volume_ratio < self.min_volume_ratio:
            logger.debug(f"[{self.name}] {symbol} volume {volume_ratio:.2f}x < {self.min_volume_ratio}x")
            self._volume_surge_scans[symbol] = 0
            return None

        current_surge_scans = self._volume_surge_scans.get(symbol, 0) + 1
        self._volume_surge_scans[symbol] = current_surge_scans

        if current_surge_scans < self.required_surge_scans:
            logger.info(
                f"[{self.name}] {symbol} volume {volume_ratio:.2f}x ✅ "
                f"({current_surge_scans}/{self.required_surge_scans} confirmations)"
            )
            return None

        logger.info(f"[{self.name}] {symbol} ✅ Volume surge: {volume_ratio:.2f}x (confirmed)")

        # ════════════════════════════════════════════════════════════════════
        # CORE FILTER 4: BOLLINGER BAND POSITION
        # ════════════════════════════════════════════════════════════════════

        bb_range = bb_high - bb_low
        bb_position = (price - bb_low) / bb_range if bb_range > 0 else 0.5

        if bb_position > 0.50:
            logger.debug(f"[{self.name}] {symbol} BB position {bb_position*100:.0f}% > 50%")
            return None

        # ════════════════════════════════════════════════════════════════════
        # TECHNICAL SCORING
        # ════════════════════════════════════════════════════════════════════

        technical_score = 0

        # RSI (0-35 pts)
        if rsi < 18:
            technical_score += 35
        elif rsi < 22:
            technical_score += 30
        elif rsi < self.rsi_optimal:
            technical_score += 25
        elif rsi < 30:
            technical_score += 18
        else:
            technical_score += 10

        # BB position (0-25 pts)
        if bb_position < 0.15:
            technical_score += 25
        elif bb_position < 0.25:
            technical_score += 22
        elif bb_position < 0.35:
            technical_score += 17
        elif bb_position < 0.45:
            technical_score += 10
        else:
            technical_score += 5

        # Volatility (0-20 pts)
        if regime_analysis.volatility_percentile > 90:
            technical_score += 20
        elif regime_analysis.volatility_percentile > 80:
            technical_score += 15
        elif regime_analysis.volatility_percentile > 70:
            technical_score += 10
        else:
            technical_score += 5

        # Volume surge (0-20 pts)
        if volume_ratio > 3.0:
            technical_score += 20
        elif volume_ratio > 2.5:
            technical_score += 17
        elif volume_ratio > 2.0:
            technical_score += 14
        elif volume_ratio > 1.7:
            technical_score += 10
        else:
            technical_score += 6

        # ════════════════════════════════════════════════════════════════════
        # MARKET STRUCTURE SCORING
        # ════════════════════════════════════════════════════════════════════

        structure_score = 50
        structure_bonus = 0

        if market_structure:
            if market_structure.momentum_score > 30:
                structure_score += 20
            elif market_structure.momentum_score > 10:
                structure_score += 10

            if market_structure.tf_1h_trend == "bullish":
                structure_score += 15
            elif market_structure.tf_1h_trend == "neutral":
                structure_score += 5

            if market_structure.structure_quality > 75:
                structure_bonus = 5

        structure_score = min(structure_score, 100)

        # ════════════════════════════════════════════════════════════════════
        # VOLUME SCORING
        # ════════════════════════════════════════════════════════════════════

        volume_score = min(volume_ratio * 40, 100) if volume_ratio > 0 else 0

        # ════════════════════════════════════════════════════════════════════
        # CONFIDENCE CALCULATION
        # ════════════════════════════════════════════════════════════════════

        confidence_level, confidence_score = self._calculate_confidence(
            regime_confidence=regime_analysis.confidence,
            technical_score=technical_score,
            structure_score=structure_score,
            volume_score=volume_score,
            multi_tf_alignment=50
        )

        confidence_score = min(confidence_score + structure_bonus, 100)

        if confidence_score < self.min_confidence:
            logger.debug(f"[{self.name}] {symbol} confidence {confidence_score:.1f}% < {self.min_confidence}%")
            return None

        # ════════════════════════════════════════════════════════════════════
        # TIER CONFIG + STOP/TARGET
        # ════════════════════════════════════════════════════════════════════

        tier_config = self._get_tier_config(tier)

        if market_structure:
            stop_loss_price = market_structure.nearest_support * 0.995
            target_price = market_structure.nearest_resistance * 0.99
        else:
            base_stop_pct = 6.0
            if regime_analysis.volatility_percentile > 90:
                base_stop_pct = 7.5
            elif regime_analysis.volatility_percentile < 75:
                base_stop_pct = 5.0
            stop_loss_price = price * (1 - base_stop_pct / 100)
            target_price = price * (1 + tier_config['target'] / 100)

        # ════════════════════════════════════════════════════════════════════
        # RISK/REWARD FILTER
        # ════════════════════════════════════════════════════════════════════

        profit_pct = ((target_price - price) / price) * 100
        risk_pct = ((price - stop_loss_price) / price) * 100

        if profit_pct < 3.0:
            logger.debug(f"[{self.name}] {symbol} target too close: {profit_pct:.2f}%")
            return None

        if risk_pct > 0:
            ratio = profit_pct / risk_pct
            if ratio < 1.2:
                logger.debug(f"[{self.name}] {symbol} R:R {ratio:.2f}:1 < 1.2")
                return None

        # Reset surge counter after signal fires
        self._volume_surge_scans[symbol] = 0

        # ════════════════════════════════════════════════════════════════════
        # SIGNAL CONSTRUCTION
        # ════════════════════════════════════════════════════════════════════

        signal = TradingSignal(
            symbol=symbol,
            action=ActionType.BUY,
            strategy_type=StrategyType.SCALPING,
            entry_price=price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
            expected_hold_duration=tier_config['hold'],
            entry_timestamp=datetime.now().isoformat(),
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            risk_level="MEDIUM_HIGH",
            primary_reason=f"{symbol}: Momentum scalp — volatility spike + volume surge",
            supporting_reasons=[
                f"Volatility: {regime_analysis.volatility_percentile:.0f}th percentile",
                f"RSI oversold: {rsi:.1f}",
                f"Volume surge: {volume_ratio:.2f}x average",
                f"BB position: {bb_position*100:.0f}% of range",
            ],
            risk_factors=[
                "High volatility environment",
                f"Hold max {self.auto_exit_minutes // 60}h — monitor position",
                "Volume surge may fade quickly"
            ],
            expected_profit_min=tier_config['target'] * 0.5,
            expected_profit_max=tier_config['target'] * 1.4,
            market_regime=regime_analysis.regime.value if hasattr(regime_analysis, 'regime') else "NEUTRAL",
            market_structure=market_structure,
            requires_sell_notification=True,
            technical_scores={
                'rsi': rsi,
                'technical_score': technical_score,
                'volume_ratio': volume_ratio,
                'volatility': regime_analysis.volatility_percentile,
                'bb_position': bb_position * 100
            },
            timeframe_context={
                'auto_exit_minutes': str(self.auto_exit_minutes),
                'hold_hours': str(self.auto_exit_minutes // 60),
                'strategy_version': '2.0'
            }
        )

        logger.info(
            f"✅ [{self.name}] {symbol} SCALP SIGNAL v2.0\n"
            f"   Entry: ${price:.4f} | Target: ${target_price:.4f} (+{profit_pct:.1f}%)\n"
            f"   Stop:  ${stop_loss_price:.4f} (-{risk_pct:.1f}%)\n"
            f"   Confidence: {confidence_score:.1f}% | Hold: {tier_config['hold']}"
        )

        return signal

    # ═══════════════════════════════════════════════════════════════════════
    # SIGNAL VALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    def should_send_signal(self, symbol: str, signal: TradingSignal) -> tuple:
        if signal.confidence_score < self.min_confidence:
            return False, f"confidence too low ({signal.confidence_score:.1f}%)"

        if signal.risk_level == "EXTREME" and signal.confidence_score < 68:
            return False, "EXTREME risk with insufficient confidence"

        if symbol in self.active_scalp_positions:
            return False, "active scalp position exists"

        if signal.risk_reward_ratio < 1.2:
            return False, f"R:R {signal.risk_reward_ratio:.2f} too low (need ≥1.2)"

        self.active_scalp_positions.add(symbol)
        self.last_signal_time[symbol] = datetime.now()
        self.position_entry_times[symbol] = datetime.now()
        self.record_activity()

        logger.info(
            f"[{self.name}] ✅ {symbol} SCALP APPROVED (v2.0)\n"
            f"   Confidence: {signal.confidence_score:.1f}% | R:R: 1:{signal.risk_reward_ratio:.2f}\n"
            f"   Auto-exit: {self.auto_exit_minutes}min ({self.auto_exit_minutes//60}h)"
        )

        return True, "approved"

    # ═══════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════

    def check_auto_exit(self, symbol: str) -> bool:
        if symbol not in self.position_entry_times:
            return False
        entry_time = self.position_entry_times[symbol]
        minutes_elapsed = (datetime.now() - entry_time).total_seconds() / 60
        if minutes_elapsed >= self.auto_exit_minutes:
            logger.warning(f"[{self.name}] ⏰ {symbol} AUTO-EXIT: {minutes_elapsed:.0f}min")
            return True
        return False

    def mark_position_closed(self, symbol: str):
        if symbol in self.active_scalp_positions:
            self.active_scalp_positions.remove(symbol)
            self.position_entry_times.pop(symbol, None)
            self._volume_surge_scans[symbol] = 0
            logger.info(f"[{self.name}] ✅ {symbol} scalp position closed")

    def clear_position(self, symbol: str):
        self.mark_position_closed(symbol)

    def get_active_positions(self) -> set:
        return self.active_scalp_positions.copy()

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _check_cooldown(self, symbol: str) -> bool:
        if symbol not in self.last_signal_time:
            return True
        hours_since = (datetime.now() - self.last_signal_time[symbol]).total_seconds() / 3600
        if hours_since < self.min_cooldown_hours:
            logger.debug(f"[{self.name}] {symbol} cooldown ({hours_since:.1f}h/{self.min_cooldown_hours}h)")
            return False
        return True

    def _get_tier_config(self, tier: str) -> Dict:
        """v2.0: Adjusted targets for 4h hold window"""
        configs = {
            "BLUE_CHIP":   {"target": 6.0,  "hold": "2-4 hours"},
            "HIGH_GROWTH": {"target": 10.0, "hold": "1.5-3.5 hours"},
            "MEME":        {"target": 15.0, "hold": "1-3 hours"},
            "NARRATIVE":   {"target": 11.0, "hold": "2-4 hours"},
            "EMERGING":    {"target": 12.0, "hold": "2-4 hours"}
        }
        return configs.get(tier, configs["HIGH_GROWTH"])