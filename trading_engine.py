"""
TRADING ENGINE v8.0 — ALL FIXES APPLIED
═══════════════════════════════════════════════════════════════════════════════
P0 FIXES:
  #1 — startup preload: data_provider.preload_all_history() before first scan
       scan_market blocked until preload_complete=True
  #2 — volume_missing → skip signal (no mock, no random)
  #3 — AI learning via SQLite (handled in ai_risk_evaluator.py)

P1 FIXES:
  #4 — multi-TF data from MarketData.multi_tf (real 1h+4h, no inference)
       passed to market_structure_builder and strategies
  #5 — trailing stop in exit_signals_handler.py (transparent to engine)
  #6 — global symbol cooldown: only ONE active signal per symbol
       across ALL strategies simultaneously

P2 FIX #8 — confidence score: base_score starts at 0 (no hidden +50 floor)
            MIN_CONFIDENCE thresholds raised by 5 points to compensate

v7.1 შენარჩუნებული: all strategies, AI eval, daily limits, position monitoring,
                     analytics, signal history, signal memory
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import time
import json
import os
import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple

import numpy as np

from config import (
    CRYPTO, STOCKS, COMMODITIES,
    SCAN_INTERVAL, ASSET_DELAY,
    MIN_CONFIDENCE_FOR_AI,
    MAX_SIGNALS_PER_DAY, MAX_SIGNALS_PER_TIER_DAY,
    MIN_RR_RATIO, ACTIVE_POSITIONS_FILE, ANALYTICS_DB,
    get_tier, get_tier_risk,
    TIER_1_BLUE_CHIPS, TIER_2_HIGH_GROWTH,
    TIER_3_MEME_COINS, TIER_4_NARRATIVE, TIER_5_EMERGING,
    TWELVE_DATA_API_KEY, ALPACA_API_KEY, ALPACA_SECRET_KEY,
    ANTHROPIC_API_KEY, AI_RISK_ENABLED,
)
from analytics_system import AnalyticsDatabase, AnalyticsDashboard
from market_regime import MarketRegimeDetector
from market_structure_builder import MarketStructureBuilder
from strategies.long_term_strategy import LongTermStrategy
from strategies.scalping_strategy import ScalpingStrategy
from strategies.opportunistic_strategy import OpportunisticStrategy
from strategies.swing_strategy import SwingStrategy
from exit_signals_handler import ExitSignalsHandler
from sell_signal_message_generator import SellSignalMessageGenerator

logger = logging.getLogger(__name__)

try:
    from signal_history_db import SignalHistoryDB, SentSignal, SignalResult, SignalStatus
    SIGNAL_HISTORY_AVAILABLE = True
except Exception as e:
    SIGNAL_HISTORY_AVAILABLE = False
    logger.warning(f"⚠️ SignalHistoryDB not available: {e}")

from position_monitor import PositionMonitor

try:
    from signal_memory import SignalMemory
    MEMORY_AVAILABLE = True
except Exception as e:
    MEMORY_AVAILABLE = False
    logger.warning(f"⚠️ SignalMemory not available: {e}")

try:
    from market_data import MultiSourceDataProvider
    MULTI_SOURCE_AVAILABLE = True
    logger.info("✅ MultiSourceDataProvider imported")
except Exception as e:
    MULTI_SOURCE_AVAILABLE = False
    logger.error(f"❌ market_data import failed: {e}")

try:
    from ai_risk_evaluator import AIRiskEvaluator, AIDecision, TradeOutcome
    AI_EVALUATOR_AVAILABLE = True
    logger.info("✅ AIRiskEvaluator imported")
except Exception as e:
    AI_EVALUATOR_AVAILABLE = False
    logger.warning(f"⚠️ AI evaluator not available: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# POSITION
# ═══════════════════════════════════════════════════════════════════════════

class Position:
    def __init__(self, symbol, entry_price, strategy_type, signal_id=None):
        self.symbol           = symbol
        self.entry_price      = entry_price
        self.strategy_type    = strategy_type
        self.signal_id        = signal_id
        self.entry_time       = datetime.now().isoformat()
        self.buy_signals_sent = 1


# ═══════════════════════════════════════════════════════════════════════════
# DAILY SIGNAL TRACKER (unchanged)
# ═══════════════════════════════════════════════════════════════════════════

class DailySignalTracker:

    def __init__(self):
        self._date  = date.today()
        self._total = 0
        self._tiers: Dict[str, int] = {}

    def _reset_if_new_day(self):
        today = date.today()
        if today != self._date:
            self._date  = today
            self._total = 0
            self._tiers = {}
            logger.info("📅 Daily signal counter reset")

    def can_send(self, tier: str) -> Tuple[bool, str]:
        self._reset_if_new_day()
        if self._total >= MAX_SIGNALS_PER_DAY:
            return False, f"Daily limit ({MAX_SIGNALS_PER_DAY}/day)"
        tier_limit = MAX_SIGNALS_PER_TIER_DAY.get(tier, 1)
        if self._tiers.get(tier, 0) >= tier_limit:
            return False, f"{tier} limit ({tier_limit}/day)"
        return True, ""

    def record(self, tier: str):
        self._reset_if_new_day()
        self._total += 1
        self._tiers[tier] = self._tiers.get(tier, 0) + 1

    def status(self) -> str:
        self._reset_if_new_day()
        parts = " | ".join(
            f"{t}: {self._tiers.get(t,0)}/{MAX_SIGNALS_PER_TIER_DAY.get(t,1)}"
            for t in ["BLUE_CHIP","HIGH_GROWTH","MEME","NARRATIVE","EMERGING"]
        )
        return f"Today: {self._total}/{MAX_SIGNALS_PER_DAY} | {parts}"


# ═══════════════════════════════════════════════════════════════════════════
# TRADING ENGINE v8.0
# ═══════════════════════════════════════════════════════════════════════════

class TradingEngine:

    def __init__(self):
        logger.info("🔧 TradingEngine v8.0 initializing...")

        self.telegram_handler = None
        self.analytics_db     = AnalyticsDatabase(ANALYTICS_DB)
        self.dashboard        = AnalyticsDashboard(self.analytics_db)
        self.exit_handler     = ExitSignalsHandler()
        self.daily_tracker    = DailySignalTracker()

        # ✅ P1/#6 — global symbol cooldown (symbol → last signal time)
        self._global_symbol_last_signal: Dict[str, datetime] = {}
        self._global_symbol_cooldown_hours: int = 6  # min hours between any signal on same symbol

        self.signal_memory = None
        if MEMORY_AVAILABLE:
            try:
                self.signal_memory = SignalMemory()
                logger.info("✅ SignalMemory ready")
            except Exception as e:
                logger.error(f"❌ SignalMemory init: {e}")

        self.data_provider    = None
        self.use_multi_source = False

        if MULTI_SOURCE_AVAILABLE:
            try:
                self.data_provider = MultiSourceDataProvider(
                    twelve_data_key=TWELVE_DATA_API_KEY,
                    alpaca_key=ALPACA_API_KEY,
                    alpaca_secret=ALPACA_SECRET_KEY
                )
                self.use_multi_source = True
                logger.info("✅ Data provider ready")
            except Exception as e:
                logger.error(f"❌ Data provider: {e}")

        self.ai_enabled   = False
        self.ai_evaluator = None

        if AI_EVALUATOR_AVAILABLE and AI_RISK_ENABLED and ANTHROPIC_API_KEY:
            try:
                self.ai_evaluator = AIRiskEvaluator(api_key=ANTHROPIC_API_KEY)
                self.ai_enabled   = True
                logger.info("✅ AI Risk Evaluator ready")
            except Exception as e:
                logger.error(f"❌ AI init: {e}")

        self.regime_detector   = MarketRegimeDetector()
        self.structure_builder = MarketStructureBuilder()
        self.strategies = [
            LongTermStrategy(),
            SwingStrategy(),
            ScalpingStrategy(),
            OpportunisticStrategy()
        ]
        logger.info(f"✅ {len(self.strategies)} strategies loaded")

        self.active_positions  = self._load_positions()
        self.position_monitor  = None

        self.signal_history_db = None
        if SIGNAL_HISTORY_AVAILABLE:
            try:
                self.signal_history_db = SignalHistoryDB()
                logger.info("✅ SignalHistoryDB ready")
            except Exception as e:
                logger.error(f"❌ SignalHistoryDB init: {e}")

        self.stats = {
            "total_signals": 0, "buy_signals": 0, "sell_signals": 0,
            "ai_approved": 0,   "ai_rejected": 0,
            "rr_filtered": 0,   "daily_limited": 0,
            "volume_blocked": 0,  # ✅ P0/#2
            "warmup_skipped": 0,  # ✅ P0/#1
            "global_cooldown": 0, # ✅ P1/#6
            "by_strategy": {s: 0 for s in ["long_term","swing","scalping","opportunistic"]},
            "by_tier":     {t: 0 for t in ["BLUE_CHIP","HIGH_GROWTH","MEME","NARRATIVE","EMERGING"]},
        }

        logger.info(
            f"✅ Engine v8.0 ready | "
            f"Data: {'✅' if self.use_multi_source else '❌'} | "
            f"AI: {'✅' if self.ai_enabled else '❌'}"
        )

    # ─── Setup ────────────────────────────────────────────────────────────

    def set_telegram_handler(self, handler):
        self.telegram_handler = handler
        if not self.position_monitor:
            self.position_monitor = PositionMonitor(
                exit_handler=self.exit_handler,
                data_provider=self.data_provider,
                telegram_handler=self.telegram_handler,
                analytics_db=self.analytics_db,
                scan_interval=30,
            )
        logger.info("✅ Telegram linked + Position Monitor created")

    # ─── Data ─────────────────────────────────────────────────────────────

    async def fetch_data(self, symbol: str) -> Optional[Dict]:
        if not self.use_multi_source or not self.data_provider:
            return None
        try:
            md = await self.data_provider.fetch_with_fallback(symbol)
            if not md:
                return None

            result = {
                "_symbol":             symbol,
                "price":               md.price,
                "prev_close":          md.prev_close,
                "rsi":                 md.rsi,
                "prev_rsi":            md.prev_rsi,
                "ema50":               md.ema50,
                "ema200":              md.ema200,
                "macd":                md.macd,
                "macd_signal":         md.macd_signal,
                "macd_histogram":      md.macd_histogram,
                "macd_histogram_prev": getattr(md, "macd_histogram_prev", md.macd_histogram),
                "bb_low":              md.bb_low,
                "bb_high":             md.bb_high,
                "bb_mid":              md.bb_mid,
                "bb_width":            md.bb_width,
                "avg_bb_width_20d":    md.avg_bb_width_20d,
                "source":              md.source,
                "volume":              md.volume,
                "avg_volume_20d":      md.avg_volume_20d,
                "volume_missing":      md.volume_missing,  # ✅ P0/#2
                # ✅ P1/#4 — real multi-TF data
                "_multi_tf":           md.multi_tf,
            }
            return result
        except Exception as e:
            logger.error(f"❌ fetch_data {symbol}: {e}")
            return None

    # ─── P0/#1 — Real price history from data_provider ───────────────────

    def _get_price_history(self, symbol: str, length: int = 200) -> np.ndarray:
        """
        ✅ P0/#1 — uses real history from preload, never random noise.
        Returns empty array if not preloaded yet.
        """
        if self.data_provider and hasattr(self.data_provider, "get_real_history"):
            return self.data_provider.get_real_history(symbol, length)
        return np.array([])

    # ─── P1/#6 — Global Symbol Cooldown ──────────────────────────────────

    def _check_global_cooldown(self, symbol: str) -> Tuple[bool, str]:
        """
        ✅ P1/#6 — One signal per symbol across all strategies.
        Returns (can_send, reason).
        """
        last = self._global_symbol_last_signal.get(symbol)
        if last is None:
            return True, ""
        hours_since = (datetime.now() - last).total_seconds() / 3600
        if hours_since < self._global_symbol_cooldown_hours:
            remaining = self._global_symbol_cooldown_hours - hours_since
            return False, f"Global cooldown: {remaining:.1f}h remaining"
        return True, ""

    def _record_global_signal(self, symbol: str):
        self._global_symbol_last_signal[symbol] = datetime.now()

    # ─── Quality Gate ─────────────────────────────────────────────────────

    def _passes_quality_gate(self, signal, tier: str, data: Dict) -> Tuple[bool, str]:
        tier_risk = get_tier_risk(tier)

        # ✅ P0/#2 — block if volume missing for volume-dependent strategies
        strat_val = signal.strategy_type.value if hasattr(signal.strategy_type, "value") else str(signal.strategy_type)
        if data.get("volume_missing", False) and strat_val in ("scalping", "opportunistic"):
            self.stats["volume_blocked"] += 1
            return False, f"Volume data missing — {strat_val} requires confirmed volume"

        if signal.confidence_score < tier_risk["min_confidence"]:
            return False, f"Confidence {signal.confidence_score:.0f}% < {tier_risk['min_confidence']}%"

        support    = getattr(signal, "stop_loss_price",  signal.entry_price * (1 - tier_risk["stop_loss_pct"]/100))
        resistance = getattr(signal, "target_price",     signal.entry_price * (1 + tier_risk["take_profit_pct"]/100))
        risk   = signal.entry_price - support
        reward = resistance - signal.entry_price

        if risk > 0:
            rr = reward / risk
            if rr < MIN_RR_RATIO:
                self.stats["rr_filtered"] += 1
                return False, f"R:R {rr:.2f} < {MIN_RR_RATIO}"

        # Pump detection (only if volume data available)
        if not data.get("volume_missing", True):
            rsi       = data.get("rsi", 50)
            volume    = data.get("volume", 1)
            avg_vol   = max(data.get("avg_volume_20d", 1), 1)
            vol_ratio = volume / avg_vol
            if rsi > 72 and vol_ratio > 2.5:
                return False, f"Pump detected: RSI={rsi:.0f} Vol={vol_ratio:.1f}x"

        can_send, reason = self.daily_tracker.can_send(tier)
        if not can_send:
            self.stats["daily_limited"] += 1
            return False, reason

        return True, "OK"

    # ─── Signal Sending (unchanged interface) ────────────────────────────

    async def send_buy_signal(self, signal, ai_eval=None, tier: str = "HIGH_GROWTH"):
        if not self.telegram_handler:
            return
        try:
            tier_risk = get_tier_risk(tier)
            stop_pct  = ai_eval.suggested_stop_pct   if ai_eval else tier_risk["stop_loss_pct"]
            tgt_pct   = ai_eval.realistic_target_pct if ai_eval else tier_risk["take_profit_pct"]
            rr        = ai_eval.risk_reward_ratio     if ai_eval else round(tgt_pct / max(stop_pct, 0.1), 2)

            msg = signal.to_message()

            if ai_eval:
                dec = ai_eval.decision.value
                if dec == "APPROVE":
                    ai_verdict = "✅ Claude AI: სიგნალი გაიარა შემოწმება — ძლიერი entry"
                elif dec == "APPROVE_WITH_CAUTION":
                    ai_verdict = "⚠️ Claude AI: სიგნალი გაიარა შემოწმება — manageable risks"
                else:
                    ai_verdict = f"🧠 Claude AI: {dec}"

                extras = []
                if ai_eval.timing_advice in ("PERFECT_TIMING", "ENTER_NOW"):
                    extras.append("⏱ Timing: ახლა კარგი შესვლის წერტილია")
                if ai_eval.pump_risk:
                    extras.append("⚠️ Pump risk — მცირე პოზიცია!")
                if ai_eval.near_resistance:
                    extras.append("⚠️ Resistance ახლოსაა")
                if ai_eval.red_flags:
                    extras.append("🔴 " + " | ".join(ai_eval.red_flags[:2]))
                if ai_eval.green_flags:
                    extras.append("🟢 " + " | ".join(ai_eval.green_flags[:2]))

                ai_block = f"\n━━━━━━━━━━━━━━\n🤖 {ai_verdict}\nAI Confidence: {ai_eval.adjusted_confidence:.0f}%"
                if extras:
                    ai_block += "\n" + "\n".join(extras)
                msg += ai_block

            msg += (
                f"\n━━━━━━━━━━━━━━━━━━\n"
                f"🔴 Stop Loss:  -{stop_pct:.1f}%\n"
                f"🟢 Target:     +{tgt_pct:.1f}%\n"
                f"📊 R:R Ratio:   1:{rr:.2f}\n"
                f"🎯 Trailing Stop: ჩაირთვება +{tgt_pct*0.5:.1f}%-ზე\n"
            )

            signal_id = None
            try:
                signal_id = self.analytics_db.record_signal(signal)
            except Exception as e:
                logger.warning(f"⚠️ Analytics: {e}")

            stop_price   = signal.entry_price * (1 - stop_pct / 100)
            target_price = signal.entry_price * (1 + tgt_pct  / 100)

            self.exit_handler.register_position(
                symbol=signal.symbol,
                entry_price=signal.entry_price,
                target_price=target_price,
                stop_loss_price=stop_price,
                entry_time=signal.entry_timestamp,
                signal_confidence=signal.confidence_score,
                expected_profit_min=tgt_pct * 0.5,
                expected_profit_max=tgt_pct,
                strategy_type=signal.strategy_type.value,
                signal_id=signal_id,
                ai_approved=(ai_eval is not None and ai_eval.decision.value in ("APPROVE","APPROVE_WITH_CAUTION")),
            )

            await self.telegram_handler.broadcast_signal(message=msg, asset=signal.symbol)

            if self.signal_history_db:
                try:
                    self.signal_history_db.record_sent_signal(SentSignal(
                        symbol=signal.symbol,
                        strategy=signal.strategy_type.value,
                        entry_price=signal.entry_price,
                        target_price=target_price,
                        stop_loss_price=stop_price,
                        sent_time=datetime.now().isoformat(),
                        confidence_score=signal.confidence_score,
                        ai_approved=(ai_eval is not None),
                        expected_profit_min=tgt_pct * 0.5,
                        expected_profit_max=tgt_pct,
                        tier=tier,
                    ))
                except Exception as e:
                    logger.warning(f"⚠️ signal_history_db: {e}")

            self.daily_tracker.record(tier)
            self._record_global_signal(signal.symbol)  # ✅ P1/#6

            if self.signal_memory:
                try:
                    self.signal_memory.record_signal(
                        symbol=signal.symbol, entry_price=signal.entry_price,
                        strategy=signal.strategy_type.value,
                        confidence=signal.confidence_score, tier=tier,
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Memory record: {e}")

            self.active_positions.setdefault(
                signal.symbol,
                Position(signal.symbol, signal.entry_price, signal.strategy_type.value, signal_id)
            )
            self._save_positions()

            self.stats["total_signals"] += 1
            self.stats["buy_signals"]   += 1
            self.stats["by_strategy"][signal.strategy_type.value] = \
                self.stats["by_strategy"].get(signal.strategy_type.value, 0) + 1
            self.stats["by_tier"][tier] = self.stats["by_tier"].get(tier, 0) + 1

            logger.info(f"✅ BUY sent: {signal.symbol} | {self.daily_tracker.status()}")

        except Exception as e:
            logger.error(f"❌ send_buy_signal {signal.symbol}: {e}")

    async def send_sell_signal(self, symbol: str, exit_analysis):
        if not self.telegram_handler:
            return
        try:
            msg = SellSignalMessageGenerator.generate_sell_message(
                symbol=symbol, exit_analysis=exit_analysis
            )
            await self.telegram_handler.broadcast_signal(message=msg, asset=symbol)

            if self.ai_evaluator and symbol in self.active_positions:
                pos = self.active_positions[symbol]
                try:
                    self.ai_evaluator.record_outcome(TradeOutcome(
                        symbol=symbol,
                        strategy=pos.strategy_type,
                        tier=get_tier(symbol),
                        entry_price=pos.entry_price,
                        exit_price=exit_analysis.exit_price,
                        profit_pct=exit_analysis.profit_pct,
                        hold_hours=exit_analysis.hold_duration_hours,
                        ai_decision="approved",
                        win=exit_analysis.profit_pct > 0,
                    ))
                except Exception:
                    pass

            # ✅ FIX: Update signal_history_db — close signal as win/loss
            # Without this, /results always shows HOLD for closed positions
            if self.signal_history_db and symbol in self.active_positions:
                pos = self.active_positions[symbol]
                try:
                    signal_id = getattr(pos, "signal_id", None)
                    if signal_id is not None:
                        status = (
                            SignalStatus.CLOSED_WIN
                            if exit_analysis.profit_pct > 0
                            else SignalStatus.CLOSED_LOSS
                        )
                        now_iso = datetime.now().isoformat()
                        self.signal_history_db.record_signal_result(SignalResult(
                            signal_id=signal_id,
                            symbol=symbol,
                            actual_entry_price=pos.entry_price,
                            entry_time=getattr(pos, "entry_time", now_iso) or now_iso,
                            exit_price=exit_analysis.exit_price,
                            exit_time=exit_analysis.exit_time or now_iso,
                            exit_reason=exit_analysis.exit_reason.value,
                            profit_pct=exit_analysis.profit_pct,
                            profit_usd=exit_analysis.simulated_profit_usd,
                            days_held=exit_analysis.hold_duration_hours / 24.0,
                            status=status,
                        ))
                        # Also store max_profit so /results can display it
                        self.signal_history_db.add_note(
                            signal_id,
                            f"max_profit_pct={exit_analysis.max_profit_pct_during_hold:.4f}"
                        )
                        logger.info(
                            f"✅ signal_history_db closed: {symbol} "
                            f"{exit_analysis.profit_pct:+.2f}% ({status.value})"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ signal_history_db sell update: {e}")

            self.stats["total_signals"] += 1
            self.stats["sell_signals"]  += 1
            logger.info(f"✅ SELL sent: {symbol}")
        except Exception as e:
            logger.error(f"❌ send_sell_signal {symbol}: {e}")

    # ─── Market Scan ──────────────────────────────────────────────────────

    async def scan_market(self, all_assets: List[str]):
        # ✅ P0/#1 — block scan until preload complete
        if self.data_provider and not self.data_provider.preload_complete:
            logger.warning("⏳ SCAN SKIPPED — preload not complete yet")
            self.stats["warmup_skipped"] += 1
            return

        logger.info("=" * 65)
        logger.info(
            f"🔍 SCAN | {len(all_assets)} assets | "
            f"Data: {'✅' if self.use_multi_source else '❌'} | "
            f"AI: {'✅' if self.ai_enabled else '❌'}"
        )
        logger.info(self.daily_tracker.status())
        logger.info("=" * 65)

        if not self.use_multi_source:
            logger.error("❌ SCAN ABORTED — no data provider")
            return

        start    = time.time()
        success  = fail = generated = filtered = ai_rejected = sent = 0
        vol_blocked = global_cd = 0

        for symbol in all_assets:
            try:
                # ✅ P1/#6 — global cooldown check
                can_proceed, cd_reason = self._check_global_cooldown(symbol)
                if not can_proceed:
                    global_cd += 1
                    self.stats["global_cooldown"] += 1
                    logger.debug(f"⏭️ {symbol}: {cd_reason}")
                    await asyncio.sleep(ASSET_DELAY)
                    continue

                data = await self.fetch_data(symbol)
                if not data:
                    fail += 1
                    continue
                success += 1

                price = data["price"]
                tier  = get_tier(symbol)

                # ✅ P0/#1 — real price history
                price_history = self._get_price_history(symbol, 200)
                if len(price_history) < 50:
                    logger.debug(f"⚠️ {symbol}: insufficient history ({len(price_history)} pts) — skip")
                    await asyncio.sleep(ASSET_DELAY)
                    continue

                regime = self.regime_detector.analyze_regime(
                    symbol, price, price_history,
                    data["rsi"], data["ema200"],
                    data["bb_low"], data["bb_high"]
                )

                # ✅ P1/#4 — pass real multi-TF data to structure builder
                multi_tf = data.get("_multi_tf")
                market_structure = self.structure_builder.build(
                    symbol, price, data, regime, list(price_history),
                    multi_tf=multi_tf  # new kwarg (builder handles None gracefully)
                )

                technical = {k: data[k] for k in [
                    "rsi","prev_rsi","ema50","ema200",
                    "macd","macd_signal","macd_histogram","macd_histogram_prev",
                    "bb_low","bb_high","bb_mid","bb_width","avg_bb_width_20d",
                    "volume","avg_volume_20d","prev_close","volume_missing",
                ] if k in data}

                best_signal   = None
                best_conf     = 0
                best_strategy = None

                for strategy in self.strategies:
                    try:
                        sig = strategy.analyze(
                            symbol, price, regime,
                            technical, tier,
                            self.active_positions.get(symbol),
                            market_structure
                        )
                        if sig and sig.confidence_score > best_conf:
                            best_signal   = sig
                            best_conf     = sig.confidence_score
                            best_strategy = strategy
                    except Exception as e:
                        logger.warning(f"⚠️ Strategy err {symbol}: {e}")
                        continue

                if not best_signal:
                    await asyncio.sleep(ASSET_DELAY)
                    continue

                generated += 1

                # ✅ P0/#2 volume check + R:R + daily limit
                passes, reason = self._passes_quality_gate(best_signal, tier, data)
                if not passes:
                    if "volume" in reason.lower():
                        vol_blocked += 1
                    filtered += 1
                    logger.debug(f"⏭️ {symbol}: {reason}")
                    await asyncio.sleep(ASSET_DELAY)
                    continue

                if best_strategy:
                    should_send, s_reason = best_strategy.should_send_signal(symbol, best_signal)
                    if not should_send:
                        logger.debug(f"⏭️ {symbol}: Cooldown")
                        await asyncio.sleep(ASSET_DELAY)
                        continue

                ai_eval = None

                if self.ai_enabled and self.ai_evaluator and best_conf >= MIN_CONFIDENCE_FOR_AI:
                    logger.info(f"🧠 {symbol}: AI eval (conf {best_conf:.0f}%)...")
                    try:
                        mem_summary = ""
                        if self.signal_memory:
                            try:
                                mem_summary = self.signal_memory.get_summary(symbol)
                            except Exception:
                                pass

                        ai_eval = await self.ai_evaluator.evaluate_signal(
                            symbol=symbol,
                            strategy_type=best_signal.strategy_type.value,
                            entry_price=best_signal.entry_price,
                            strategy_confidence=best_conf,
                            indicators=technical,
                            market_structure={
                                "nearest_support":    market_structure.nearest_support,
                                "nearest_resistance": market_structure.nearest_resistance,
                                "volume_trend":       market_structure.volume_trend,
                            },
                            regime=regime.regime.value,
                            tier=tier,
                            symbol_history=mem_summary,
                        )
                        should_send_ai, ai_reason = self.ai_evaluator.should_send_signal(ai_eval)

                        if should_send_ai:
                            sent += 1
                            self.stats["ai_approved"] += 1
                            await self.send_buy_signal(best_signal, ai_eval, tier)
                            if best_strategy:
                                best_strategy.record_activity()
                        else:
                            ai_rejected += 1
                            self.stats["ai_rejected"] += 1
                            logger.info(f"❌ {symbol}: AI rejected — {ai_reason}")

                    except Exception as e:
                        logger.error(f"❌ AI error {symbol}: {e}")
                        if best_conf >= 75:
                            sent += 1
                            await self.send_buy_signal(best_signal, None, tier)
                            if best_strategy:
                                best_strategy.record_activity()

                elif best_conf >= 72:
                    sent += 1
                    await self.send_buy_signal(best_signal, None, tier)
                    if best_strategy:
                        best_strategy.record_activity()

                await asyncio.sleep(ASSET_DELAY)

            except Exception as e:
                logger.error(f"❌ Scan error {symbol}: {e}")
                fail += 1

        duration = (time.time() - start) / 60
        logger.info("=" * 65)
        logger.info(f"✅ SCAN DONE ({duration:.1f}min)")
        logger.info(f"📊 Success: {success}/{len(all_assets)} | Fail: {fail}")
        logger.info(
            f"🔍 Generated: {generated} → "
            f"Filtered: {filtered} (vol_blocked:{vol_blocked}) → "
            f"Global CD: {global_cd} → "
            f"AI Rejected: {ai_rejected} → Sent: {sent}"
        )
        logger.info(self.daily_tracker.status())
        logger.info("=" * 65)

    # ─── Main Loop ────────────────────────────────────────────────────────

    async def run_forever(self):
        all_assets = CRYPTO + STOCKS + COMMODITIES

        logger.info(
            f"\n╔═══════════════════════════════════════╗\n"
            f"║  TRADE ALLY ENGINE v8.0 — PRODUCTION  ║\n"
            f"║  Data:  {'ACTIVE' if self.use_multi_source else 'INACTIVE':<10} AI: {'ACTIVE' if self.ai_enabled else 'INACTIVE':<10} ║\n"
            f"║  Assets: {len(all_assets):<5} | Strategies: {len(self.strategies):<4}      ║\n"
            f"╚═══════════════════════════════════════╝"
        )

        # ✅ P0/#1 — STARTUP PRELOAD before any scan
        if self.data_provider and self.use_multi_source:
            logger.info("🚀 Starting startup preload...")
            try:
                count = await self.data_provider.preload_all_history(all_assets, batch_size=8)
                logger.info(f"✅ Preload done: {count}/{len(all_assets)} symbols ready")
            except Exception as e:
                logger.error(f"❌ Preload failed: {e} — scans will be blocked until data is ready")
        else:
            logger.warning("⚠️ No data provider — scans will be blocked")

        if self.position_monitor:
            await self.position_monitor.start_monitoring()

        scan_n = 0
        while True:
            try:
                scan_n += 1
                logger.info(f"\n🔄 SCAN #{scan_n}")
                await self.scan_market(all_assets)
                logger.info(f"⏸️ Next scan in {SCAN_INTERVAL/60:.0f}min...")
                await asyncio.sleep(SCAN_INTERVAL)
            except asyncio.CancelledError:
                logger.info("Engine cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                await asyncio.sleep(300)

    # ─── Helpers ─────────────────────────────────────────────────────────

    def _load_positions(self) -> Dict:
        if os.path.exists(ACTIVE_POSITIONS_FILE):
            try:
                with open(ACTIVE_POSITIONS_FILE, "r") as f:
                    raw = json.load(f)
                positions = {}
                for sym, d in raw.items():
                    p = Position(d["symbol"], d["entry_price"],
                                 d.get("strategy_type","unknown"), d.get("signal_id"))
                    p.buy_signals_sent = d.get("buy_signals_sent", 1)
                    positions[sym] = p
                return positions
            except Exception:
                pass
        return {}

    def _save_positions(self):
        try:
            data = {}
            for sym, pos in self.active_positions.items():
                data[sym] = {
                    "symbol":          pos.symbol,
                    "entry_price":     pos.entry_price,
                    "strategy_type":   pos.strategy_type,
                    "signal_id":       pos.signal_id,
                    "entry_time":      pos.entry_time,
                    "buy_signals_sent": pos.buy_signals_sent,
                }
            with open(ACTIVE_POSITIONS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ save_positions: {e}")

    def get_engine_status(self) -> str:
        exit_stats = self.exit_handler.get_exit_statistics()
        ai_stats   = self.ai_evaluator.get_stats() if self.ai_evaluator else {}
        preload_st = self.data_provider.get_preload_status() if self.data_provider else {}
        return (
            f"\n📊 ENGINE v8.0 STATUS\n"
            f"Data: {'✅' if self.use_multi_source else '❌'} | "
            f"AI: {'✅' if self.ai_enabled else '❌'} | "
            f"Monitor: {'✅' if self.position_monitor else '❌'}\n\n"
            f"Preload: {preload_st.get('loaded','?')}/{preload_st.get('complete','?')} | "
            f"Vol: {preload_st.get('with_volume','?')} | 4H: {preload_st.get('with_4h','?')}\n\n"
            f"Signals: {self.stats['total_signals']} total | "
            f"Buy: {self.stats['buy_signals']} | Sell: {self.stats['sell_signals']}\n"
            f"AI: {self.stats['ai_approved']} approved / {self.stats['ai_rejected']} rejected\n"
            f"Filtered: R:R={self.stats['rr_filtered']} | Daily={self.stats['daily_limited']} | "
            f"Vol={self.stats['volume_blocked']} | GlobalCD={self.stats['global_cooldown']}\n\n"
            f"{self.daily_tracker.status()}\n\n"
            f"Active positions: {len(self.active_positions)}\n"
            f"Closed: {exit_stats.get('total_exits',0)} | "
            f"Win rate: {exit_stats.get('win_rate',0):.1f}%\n"
            f"AI approval rate: {ai_stats.get('approval_rate','N/A')} | "
            f"Outcomes in DB: {ai_stats.get('outcomes_in_db',0)}"
        )