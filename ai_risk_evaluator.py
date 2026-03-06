"""
AI RISK EVALUATOR v4.0 — FIXED
P0 FIX #3: trade_outcomes SQLite-ში (signal_memory.db) — restart-safe learning
v3.0 შენარჩუნებული: 4 decisions, Georgian responses, 5 checks, retry logic
"""

import logging
import json
import asyncio
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import anthropic

from config import (
    AI_MODEL, AI_MAX_TOKENS, ANTHROPIC_API_KEY,
    AI_MIN_CONFIDENCE, AI_CAUTION_THRESHOLD,
    MIN_RR_RATIO, get_tier_risk
)

logger = logging.getLogger(__name__)

OUTCOMES_DB = "ai_outcomes.db"


class AIDecision(Enum):
    APPROVE              = "APPROVE"
    APPROVE_WITH_CAUTION = "APPROVE_WITH_CAUTION"
    DELAY_ENTRY          = "DELAY_ENTRY"
    REJECT               = "REJECT"


@dataclass
class AIEvaluation:
    decision:             AIDecision
    adjusted_confidence:  float
    risk_score:           float
    reasoning:            List[str]
    timing_advice:        str
    red_flags:            List[str]
    green_flags:          List[str]
    entry_zone_min:       float = 0.0
    entry_zone_max:       float = 0.0
    realistic_target_pct: float = 0.0
    suggested_stop_pct:   float = 0.0
    risk_reward_ratio:    float = 0.0
    pump_risk:            bool  = False
    near_resistance:      bool  = False


@dataclass
class TradeOutcome:
    symbol:      str
    strategy:    str
    tier:        str
    entry_price: float
    exit_price:  float
    profit_pct:  float
    hold_hours:  float
    ai_decision: str
    win:         bool


# ═══════════════════════════════════════════════════════════════════════════
# P0/#3 — PERSISTENT OUTCOMES STORE
# ═══════════════════════════════════════════════════════════════════════════

class OutcomesStore:
    """SQLite-backed trade outcomes — restart-safe."""

    def __init__(self, db_path: str = OUTCOMES_DB):
        self.db_path = db_path
        self._init()

    def _init(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_outcomes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol      TEXT    NOT NULL,
                    strategy    TEXT    NOT NULL,
                    tier        TEXT    NOT NULL,
                    entry_price REAL    NOT NULL,
                    exit_price  REAL    NOT NULL,
                    profit_pct  REAL    NOT NULL,
                    hold_hours  REAL    NOT NULL,
                    ai_decision TEXT    NOT NULL,
                    win         INTEGER NOT NULL,
                    recorded_at TEXT    DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_oc_tier ON trade_outcomes(tier)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_oc_sym  ON trade_outcomes(symbol)")
            conn.commit()
        logger.info("✅ OutcomesStore (SQLite) initialized")

    def save(self, o: TradeOutcome):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO trade_outcomes
                  (symbol,strategy,tier,entry_price,exit_price,profit_pct,hold_hours,ai_decision,win)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (o.symbol, o.strategy, o.tier, o.entry_price, o.exit_price,
                  o.profit_pct, o.hold_hours, o.ai_decision, int(o.win)))
            # Keep max 200 rows (rolling window)
            conn.execute("""
                DELETE FROM trade_outcomes WHERE id NOT IN (
                    SELECT id FROM trade_outcomes ORDER BY id DESC LIMIT 200
                )
            """)
            conn.commit()

    def load_recent(self, n: int = 100, tier: str = None) -> List[TradeOutcome]:
        with sqlite3.connect(self.db_path) as conn:
            if tier:
                rows = conn.execute(
                    "SELECT * FROM trade_outcomes WHERE tier=? ORDER BY id DESC LIMIT ?",
                    (tier, n)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trade_outcomes ORDER BY id DESC LIMIT ?", (n,)
                ).fetchall()
        outcomes = []
        for r in rows:
            outcomes.append(TradeOutcome(
                symbol=r[1], strategy=r[2], tier=r[3],
                entry_price=r[4], exit_price=r[5],
                profit_pct=r[6], hold_hours=r[7],
                ai_decision=r[8], win=bool(r[9])
            ))
        return outcomes

    def win_rate(self, tier: str = None) -> float:
        outcomes = self.load_recent(200, tier)
        if not outcomes: return 0.0
        return sum(1 for o in outcomes if o.win) / len(outcomes) * 100

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM trade_outcomes").fetchone()[0]


# ═══════════════════════════════════════════════════════════════════════════
# AI RISK EVALUATOR v4.0
# ═══════════════════════════════════════════════════════════════════════════

class AIRiskEvaluator:
    """
    Professional AI Risk Evaluator v4.0
    P0/#3: trade_outcomes → SQLite (persistent across restarts)
    """

    def __init__(self, api_key: str = None):
        self.api_key    = api_key or ANTHROPIC_API_KEY
        self.client     = anthropic.AsyncAnthropic(api_key=self.api_key)
        self.model      = AI_MODEL
        self.max_tokens = AI_MAX_TOKENS

        # P0/#3 — persistent outcomes
        self.outcomes_store = OutcomesStore(OUTCOMES_DB)
        logger.info(f"📊 Loaded {self.outcomes_store.count()} historical outcomes from DB")

        self.stats = {
            "total_evaluated": 0,
            "approved":        0,
            "caution":         0,
            "delayed":         0,
            "rejected":        0,
            "api_errors":      0,
        }
        logger.info(f"🧠 AIRiskEvaluator v4.0 | Model: {self.model}")

    # ─── Main evaluate (unchanged interface) ──────────────────────────────

    async def evaluate_signal(
        self,
        symbol:              str,
        strategy_type:       str,
        entry_price:         float,
        strategy_confidence: float,
        indicators:          Dict,
        market_structure:    Dict,
        regime:              str,
        tier:                str,
        symbol_history:      str = "",
    ) -> AIEvaluation:

        self.stats["total_evaluated"] += 1
        try:
            prompt   = self._build_prompt(
                symbol, strategy_type, entry_price, strategy_confidence,
                indicators, market_structure, regime, tier, symbol_history
            )
            response = await self._call_claude(prompt)
            result   = self._parse_response(response, strategy_confidence, entry_price, tier)

            dec = result.decision.value
            if dec == "APPROVE":              self.stats["approved"] += 1
            elif dec == "APPROVE_WITH_CAUTION": self.stats["caution"] += 1
            elif dec == "DELAY_ENTRY":         self.stats["delayed"]  += 1
            else:                              self.stats["rejected"] += 1

            logger.info(
                f"🧠 {symbol} | {dec} | "
                f"Conf:{strategy_confidence:.0f}%→{result.adjusted_confidence:.0f}% | "
                f"R:R={result.risk_reward_ratio:.2f} | {result.timing_advice}"
            )
            return result

        except Exception as e:
            self.stats["api_errors"] += 1
            logger.error(f"❌ AI error {symbol}: {e}")
            return self._conservative_fallback(strategy_confidence, entry_price, tier)

    # ─── Prompt builder ───────────────────────────────────────────────────

    def _build_prompt(
        self,
        symbol, strategy_type, entry_price, strategy_confidence,
        indicators, market_structure, regime, tier,
        symbol_history: str = ""
    ) -> str:

        rsi        = indicators.get("rsi", 50)
        prev_rsi   = indicators.get("prev_rsi", 50)
        ema50      = indicators.get("ema50", entry_price)
        ema200     = indicators.get("ema200", entry_price)
        vs_ema50   = ((entry_price - ema50)  / ema50  * 100) if ema50  > 0 else 0
        vs_ema200  = ((entry_price - ema200) / ema200 * 100) if ema200 > 0 else 0
        macd_h     = indicators.get("macd_histogram", 0)
        macd_hp    = indicators.get("macd_histogram_prev", 0)
        volume     = indicators.get("volume", 0)
        avg_vol    = indicators.get("avg_volume_20d", 1)
        vol_ratio  = volume / avg_vol if avg_vol > 0 and volume > 0 else 0.0
        vol_ok     = not indicators.get("volume_missing", False)

        support    = market_structure.get("nearest_support",    entry_price * 0.95)
        resistance = market_structure.get("nearest_resistance", entry_price * 1.05)
        dist_sup   = ((entry_price - support)    / support     * 100) if support    > 0 else 5
        dist_res   = ((resistance  - entry_price) / entry_price * 100) if entry_price > 0 else 5
        rr_raw     = dist_res / dist_sup if dist_sup > 0 else 0

        tier_risk    = get_tier_risk(tier)
        ideal_stop   = tier_risk["stop_loss_pct"]
        ideal_target = tier_risk["take_profit_pct"]

        # P0/#3 — load from DB, not memory
        recent_str = ""
        recent_all  = self.outcomes_store.load_recent(5, tier)
        if recent_all:
            recent_str = "\nBOT TRACK RECORD (same tier, from DB):\n"
            for o in recent_all[:3]:
                emoji = "✅" if o.win else "❌"
                recent_str += f"  {emoji} {o.symbol} ({o.strategy}): {o.profit_pct:+.1f}% in {o.hold_hours:.0f}h\n"

        overall_wr = self.outcomes_store.win_rate()
        tier_wr    = self.outcomes_store.win_rate(tier)
        total_cnt  = self.outcomes_store.count()
        wr_line    = (f"\nOverall Win Rate: {overall_wr:.1f}% ({total_cnt} trades) | "
                      f"{tier} Win Rate: {tier_wr:.1f}%\n") if total_cnt > 0 else ""

        history_section = f"SYMBOL HISTORY (last 3 signals):\n{symbol_history}\n\n" if symbol_history else ""

        vol_display = (f"{vol_ratio:.2f}x average" if vol_ok
                       else "UNKNOWN (no data) — treat as unconfirmed")

        prompt = f"""You are a PROFESSIONAL CRYPTO TRADER with 10+ years experience.
Your mandate: BRUTAL HONESTY. Kill FOMO. Save the trader's money.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{history_section}SIGNAL TO EVALUATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Symbol:     {symbol} [{tier}]
Strategy:   {strategy_type}
Price:      ${entry_price:.6f}
Confidence: {strategy_confidence:.0f}%
Regime:     {regime}
{recent_str}{wr_line}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECHNICAL SNAPSHOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RSI:        {rsi:.1f} (prev {prev_rsi:.1f}, Δ{rsi-prev_rsi:+.1f})
  → {"🔴 OVERBOUGHT >70 — do NOT enter" if rsi > 70 else "🟡 High 65-70 — late entry" if rsi > 65 else "🟢 OK zone" if rsi >= 40 else "🟡 Oversold <40"}

vs EMA50:   {vs_ema50:+.2f}%
  → {"🔴 Extended >5% above EMA50 — missed entry" if vs_ema50 > 5 else "🟡 Slightly extended" if vs_ema50 > 3 else "🟢 Near EMA50 — good entry"}

vs EMA200:  {vs_ema200:+.2f}%
  → {"✅ Above EMA200 — uptrend confirmed" if vs_ema200 > 0 else "⚠️ Below EMA200 — against trend"}

MACD hist:  {macd_h:.6f} (prev {macd_hp:.6f})
  → {"🟢 Improving" if macd_h > macd_hp else "🔴 Weakening"}

Volume:     {vol_display}
  → {"🔴 PUMP ALERT >2.5x — likely manipulation" if vol_ok and vol_ratio > 2.5 else "🟡 High volume >1.5x — watch carefully" if vol_ok and vol_ratio > 1.5 else "🟢 Normal" if vol_ok else "⚠️ Volume data unavailable — extra caution"}

Support:    ${support:.6f} ({dist_sup:.1f}% below)
Resistance: ${resistance:.6f} ({dist_res:.1f}% above)
Raw R:R:    {rr_raw:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIER GUIDELINES [{tier}]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Typical stop:   -{ideal_stop}%
Typical target: +{ideal_target}%
Min R:R needed:  {MIN_RR_RATIO}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR 5 CHECKS (respond in Georgian):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. TIMING: RSI {rsi:.0f} — early/perfect/late?
2. ENTRY ZONE: Current price vs EMA50 — enter now or wait for pullback?
3. REALISTIC TARGET: Resistance is {dist_res:.1f}% away — is target achievable?
4. VOLUME: {vol_display} — real momentum or pump?
5. R:R: {rr_raw:.2f} — acceptable? (need >{MIN_RR_RATIO})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPOND IN JSON (Georgian text, English numbers/terms):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{
  "decision": "APPROVE" | "APPROVE_WITH_CAUTION" | "DELAY_ENTRY" | "REJECT",
  "adjusted_confidence": <0-100>,
  "risk_score": <0-100>,
  "timing_advice": "PERFECT_TIMING" | "ENTER_NOW" | "WAIT_FOR_PULLBACK" | "TOO_LATE",
  "entry_zone_min": <price>,
  "entry_zone_max": <price>,
  "realistic_target_pct": <number>,
  "suggested_stop_pct": <number>,
  "risk_reward_ratio": <number>,
  "pump_risk": <true|false>,
  "near_resistance": <true|false>,
  "reasoning": ["ქართული 1","ქართული 2","ქართული 3"],
  "red_flags": ["flag1","flag2"],
  "green_flags": ["flag1","flag2"]
}}

DECISION CRITERIA:
APPROVE:              RSI 40-62, near EMA50, R:R>2, volume normal, target clear
APPROVE_WITH_CAUTION: RSI 62-68, slightly extended, R:R 1.5-2, manageable risks
DELAY_ENTRY:          technically valid but PRICE TOO HIGH NOW — wait for dip
REJECT:               RSI>70, pump detected, R:R<1.5, no clear target, against trend

BE BRUTAL. One bad trade destroys trust."""
        return prompt

    # ─── Claude call (unchanged) ──────────────────────────────────────────

    async def _call_claude(self, prompt: str, retries: int = 2) -> str:
        for attempt in range(retries + 1):
            try:
                msg = await self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                return msg.content[0].text
            except anthropic.RateLimitError:
                wait = 20 * (attempt + 1)
                logger.warning(f"⚠️ Rate limit — waiting {wait}s")
                await asyncio.sleep(wait)
            except anthropic.APIError as e:
                if attempt < retries: await asyncio.sleep(5)
                else: raise e
        raise RuntimeError("Claude API failed after retries")

    # ─── Response parser (unchanged) ──────────────────────────────────────

    def _parse_response(self, text: str, orig_conf: float, entry_price: float, tier: str) -> AIEvaluation:
        try:
            if "```json" in text: text = text.split("```json")[1].split("```")[0]
            elif "```" in text:   text = text.split("```")[1].split("```")[0]
            data     = json.loads(text.strip())
            dec_str  = data.get("decision", "APPROVE_WITH_CAUTION").upper()
            if dec_str not in {"APPROVE","APPROVE_WITH_CAUTION","DELAY_ENTRY","REJECT"}:
                dec_str = "APPROVE_WITH_CAUTION"
            decision  = AIDecision[dec_str]
            adj_conf  = max(0.0, min(100.0, float(data.get("adjusted_confidence", orig_conf*0.85))))
            risk_sc   = max(0.0, min(100.0, float(data.get("risk_score", 55.0))))
            tgt_pct   = max(3.0,  min(50.0,  float(data.get("realistic_target_pct", 8.0))))
            stop_pct  = max(1.5,  min(15.0,  float(data.get("suggested_stop_pct", 5.0))))
            rr_ratio  = round(tgt_pct / stop_pct, 2) if stop_pct > 0 else 1.0
            zone_min  = float(data.get("entry_zone_min", entry_price*0.97))
            zone_max  = float(data.get("entry_zone_max", entry_price*0.995))
            return AIEvaluation(
                decision=decision,
                adjusted_confidence=adj_conf,
                risk_score=risk_sc,
                reasoning=self._ensure_list(data.get("reasoning", [])),
                timing_advice=data.get("timing_advice", "ENTER_NOW"),
                red_flags=self._ensure_list(data.get("red_flags", [])),
                green_flags=self._ensure_list(data.get("green_flags", [])),
                entry_zone_min=zone_min,
                entry_zone_max=zone_max,
                realistic_target_pct=tgt_pct,
                suggested_stop_pct=stop_pct,
                risk_reward_ratio=rr_ratio,
                pump_risk=bool(data.get("pump_risk", False)),
                near_resistance=bool(data.get("near_resistance", False)),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"⚠️ AI parse failed: {e} — conservative fallback")
            return self._conservative_fallback(orig_conf, entry_price, tier)

    # ─── Send decision helper (unchanged) ─────────────────────────────────

    def should_send_signal(self, evaluation: AIEvaluation) -> Tuple[bool, str]:
        if evaluation.decision == AIDecision.APPROVE:
            return True, "✅ AI დაადასტურა: პერფექტული timing"
        if evaluation.decision == AIDecision.APPROVE_WITH_CAUTION:
            if evaluation.adjusted_confidence >= AI_CAUTION_THRESHOLD:
                et = (f"Entry zone: ${evaluation.entry_zone_min:.4f}–${evaluation.entry_zone_max:.4f}"
                      if evaluation.entry_zone_min > 0 else "")
                return True, f"⚠️ AI: სიფრთხილით. {et}"
            return False, f"❌ AI: confidence {evaluation.adjusted_confidence:.0f}% — ძალიან დაბალია"
        if evaluation.decision == AIDecision.DELAY_ENTRY:
            return False, (f"⏳ AI: დაელოდე pullback-ს "
                           f"${evaluation.entry_zone_min:.4f}–${evaluation.entry_zone_max:.4f}")
        flags = evaluation.red_flags[:2] if evaluation.red_flags else ["სუსტი სიგნალი"]
        return False, f"❌ AI უარყო: {' | '.join(flags)}"

    # ─── P0/#3 — Persistent outcome recording ────────────────────────────

    def record_outcome(self, outcome: TradeOutcome):
        """Save to SQLite — survives restarts."""
        self.outcomes_store.save(outcome)
        wr = self.outcomes_store.win_rate()
        cnt = self.outcomes_store.count()
        logger.info(f"📊 Outcome saved: {outcome.symbol} {outcome.profit_pct:+.1f}% | "
                    f"DB Win rate: {wr:.1f}% ({cnt} total)")

    def get_win_rate(self, tier: str = None) -> float:
        return self.outcomes_store.win_rate(tier)

    # ─── Helpers ─────────────────────────────────────────────────────────

    def _conservative_fallback(self, conf: float, entry_price: float, tier: str) -> AIEvaluation:
        tr   = get_tier_risk(tier)
        stop = tr["stop_loss_pct"]
        tgt  = tr["take_profit_pct"] * 0.7
        rr   = round(tgt / stop, 2) if stop > 0 else 1.2
        return AIEvaluation(
            decision=AIDecision.APPROVE_WITH_CAUTION,
            adjusted_confidence=conf * 0.80,
            risk_score=60.0,
            reasoning=["AI დროებით მიუწვდომელია — კონსერვატიული შეფასება"],
            timing_advice="ENTER_NOW",
            red_flags=["AI სერვისი მიუწვდომელია"],
            green_flags=[],
            entry_zone_min=entry_price * 0.97,
            entry_zone_max=entry_price,
            realistic_target_pct=tgt,
            suggested_stop_pct=stop,
            risk_reward_ratio=rr,
            pump_risk=False, near_resistance=False,
        )

    @staticmethod
    def _ensure_list(val) -> List[str]:
        if isinstance(val, list):  return [str(v) for v in val]
        if isinstance(val, str):   return [val]
        return []

    def get_stats(self) -> Dict:
        total = max(self.stats["total_evaluated"], 1)
        return {
            **self.stats,
            "approval_rate":  f"{(self.stats['approved']+self.stats['caution'])/total*100:.1f}%",
            "rejection_rate": f"{self.stats['rejected']/total*100:.1f}%",
            "win_rate_all":   f"{self.get_win_rate():.1f}%",
            "outcomes_in_db": self.outcomes_store.count(),
        }