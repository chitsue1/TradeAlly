"""
═══════════════════════════════════════════════════════════════════════════════
AI RISK EVALUATOR v3.0 — PROFESSIONAL GRADE
═══════════════════════════════════════════════════════════════════════════════

✅ შენარჩუნებული ძველიდან:
- BRUTAL honesty mandate
- 4 decision types (APPROVE / APPROVE_WITH_CAUTION / DELAY_ENTRY / REJECT)
- Entry zone optimization
- Realistic target assessment
- Georgian language responses
- claude-sonnet (fast + cost-effective)

✅ გაუმჯობესებები v3.0:
- ATR-based stop/target suggestions (არა random %)
- R:R ratio calculation და validation
- Tier-aware evaluation (MEME vs BLUE_CHIP სხვაგვარად)
- Volume spike analysis (pump detection)
- Support/resistance distance scoring
- Structured reasoning (5 explicit checks)
- Async client (non-blocking)
- Retry logic on API failure
- Trade outcome feedback loop (learning)
═══════════════════════════════════════════════════════════════════════════════
"""

import logging
import json
import asyncio
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


# ═══════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════

class AIDecision(Enum):
    APPROVE             = "APPROVE"
    APPROVE_WITH_CAUTION = "APPROVE_WITH_CAUTION"
    DELAY_ENTRY         = "DELAY_ENTRY"
    REJECT              = "REJECT"


@dataclass
class AIEvaluation:
    decision:            AIDecision
    adjusted_confidence: float
    risk_score:          float          # 0-100 (100 = max risk)
    reasoning:           List[str]
    timing_advice:       str            # ENTER_NOW / WAIT_FOR_PULLBACK / TOO_LATE / PERFECT_TIMING
    red_flags:           List[str]
    green_flags:         List[str]

    # Entry zone
    entry_zone_min:      float = 0.0
    entry_zone_max:      float = 0.0

    # Target & Stop
    realistic_target_pct: float = 0.0
    suggested_stop_pct:   float = 0.0
    risk_reward_ratio:    float = 0.0

    # Extra context
    pump_risk:           bool  = False
    near_resistance:     bool  = False


@dataclass
class TradeOutcome:
    """Trade feedback — AI სწავლობს"""
    symbol:        str
    strategy:      str
    tier:          str
    entry_price:   float
    exit_price:    float
    profit_pct:    float
    hold_hours:    float
    ai_decision:   str
    win:           bool


# ═══════════════════════════════════════════════════════════════════════════
# AI RISK EVALUATOR v3.0
# ═══════════════════════════════════════════════════════════════════════════

class AIRiskEvaluator:
    """
    Professional AI Risk Evaluator

    ყოველი სიგნალი გადის 5-ეტაპიანი შემოწმებით:
    1. Timing Check (RSI, EMA position)
    2. Entry Zone (სადაა ახლა ფასი — კარგი თუ გვიანი?)
    3. Realistic Target (resistance-ზე დაყრდნობით)
    4. Volume Analysis (pump detection)
    5. Risk/Reward (min 1.5:1 required)
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.client  = anthropic.AsyncAnthropic(api_key=self.api_key)
        self.model   = AI_MODEL
        self.max_tokens = AI_MAX_TOKENS

        # Learning feedback
        self.trade_outcomes: List[TradeOutcome] = []
        self.MAX_OUTCOMES = 100

        # Stats
        self.stats = {
            "total_evaluated": 0,
            "approved":        0,
            "caution":         0,
            "delayed":         0,
            "rejected":        0,
            "api_errors":      0,
        }

        logger.info(f"🧠 AIRiskEvaluator v3.0 initialized | Model: {self.model}")

    # ═══════════════════════════════════════════════════════════════════════
    # MAIN EVALUATE
    # ═══════════════════════════════════════════════════════════════════════

    async def evaluate_signal(
        self,
        symbol:              str,
        strategy_type:       str,
        entry_price:         float,
        strategy_confidence: float,
        indicators:          Dict,
        market_structure:    Dict,
        regime:              str,
        tier:                str
    ) -> AIEvaluation:

        self.stats["total_evaluated"] += 1

        try:
            prompt   = self._build_prompt(
                symbol, strategy_type, entry_price,
                strategy_confidence, indicators,
                market_structure, regime, tier
            )
            response = await self._call_claude(prompt)
            result   = self._parse_response(response, strategy_confidence, entry_price, tier)

            # Update stats
            dec = result.decision.value
            if dec == "APPROVE":             self.stats["approved"] += 1
            elif dec == "APPROVE_WITH_CAUTION": self.stats["caution"] += 1
            elif dec == "DELAY_ENTRY":       self.stats["delayed"]  += 1
            else:                            self.stats["rejected"] += 1

            logger.info(
                f"🧠 {symbol} | {dec} | "
                f"Conf: {strategy_confidence:.0f}%→{result.adjusted_confidence:.0f}% | "
                f"R:R={result.risk_reward_ratio:.2f} | "
                f"Timing: {result.timing_advice}"
            )
            return result

        except Exception as e:
            self.stats["api_errors"] += 1
            logger.error(f"❌ AI error for {symbol}: {e}")
            return self._conservative_fallback(strategy_confidence, entry_price, tier)

    # ═══════════════════════════════════════════════════════════════════════
    # PROMPT BUILDER
    # ═══════════════════════════════════════════════════════════════════════

    def _build_prompt(
        self,
        symbol: str, strategy_type: str, entry_price: float,
        strategy_confidence: float, indicators: Dict,
        market_structure: Dict, regime: str, tier: str
    ) -> str:

        rsi        = indicators.get("rsi", 50)
        prev_rsi   = indicators.get("prev_rsi", 50)
        rsi_delta  = rsi - prev_rsi

        ema50      = indicators.get("ema50", entry_price)
        ema200     = indicators.get("ema200", entry_price)

        vs_ema50   = ((entry_price - ema50)  / ema50  * 100) if ema50  > 0 else 0
        vs_ema200  = ((entry_price - ema200) / ema200 * 100) if ema200 > 0 else 0

        macd_hist      = indicators.get("macd_histogram", 0)
        macd_hist_prev = indicators.get("macd_histogram_prev", 0)

        volume    = indicators.get("volume", 1_000_000)
        avg_vol   = indicators.get("avg_volume_20d", 1_000_000)
        vol_ratio = volume / avg_vol if avg_vol > 0 else 1.0

        support    = market_structure.get("nearest_support",    entry_price * 0.95)
        resistance = market_structure.get("nearest_resistance", entry_price * 1.05)

        dist_sup = ((entry_price - support)    / support    * 100) if support    > 0 else 5
        dist_res = ((resistance  - entry_price) / entry_price * 100) if entry_price > 0 else 5
        rr_raw   = dist_res / dist_sup if dist_sup > 0 else 0

        tier_risk   = get_tier_risk(tier)
        ideal_stop  = tier_risk["stop_loss_pct"]
        ideal_target = tier_risk["take_profit_pct"]

        # Recent outcomes for context
        recent_str = ""
        if self.trade_outcomes:
            recent = [o for o in self.trade_outcomes[-5:] if o.tier == tier]
            if recent:
                recent_str = "\nBOT TRACK RECORD (same tier):\n"
                for o in recent[-3:]:
                    emoji = "✅" if o.win else "❌"
                    recent_str += f"  {emoji} {o.symbol} ({o.strategy}): {o.profit_pct:+.1f}% in {o.hold_hours:.0f}h\n"

        prompt = f"""You are a PROFESSIONAL CRYPTO TRADER with 10+ years experience.
Your mandate: BRUTAL HONESTY. Kill FOMO. Save the trader's money.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SIGNAL TO EVALUATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Symbol:     {symbol} [{tier}]
Strategy:   {strategy_type}
Price:      ${entry_price:.6f}
Confidence: {strategy_confidence:.0f}%
Regime:     {regime}
{recent_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECHNICAL SNAPSHOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RSI:        {rsi:.1f} (prev {prev_rsi:.1f}, Δ{rsi_delta:+.1f})
  → {"🔴 OVERBOUGHT >70 — do NOT enter" if rsi > 70 else "🟡 High 65-70 — late entry" if rsi > 65 else "🟢 OK zone" if rsi >= 40 else "🟡 Oversold <40"}

vs EMA50:   {vs_ema50:+.2f}%
  → {"🔴 Extended >5% above EMA50 — missed entry" if vs_ema50 > 5 else "🟡 Slightly extended" if vs_ema50 > 3 else "🟢 Near EMA50 — good entry"}

vs EMA200:  {vs_ema200:+.2f}%
  → {"✅ Above EMA200 — uptrend confirmed" if vs_ema200 > 0 else "⚠️ Below EMA200 — against trend"}

MACD hist:  {macd_hist:.6f} (prev {macd_hist_prev:.6f})
  → {"🟢 Improving" if macd_hist > macd_hist_prev else "🔴 Weakening"}

Volume:     {vol_ratio:.2f}x average
  → {"🔴 PUMP ALERT >2.5x — likely manipulation" if vol_ratio > 2.5 else "🟡 High volume >1.5x — watch carefully" if vol_ratio > 1.5 else "🟢 Normal"}

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
4. VOLUME: {vol_ratio:.1f}x — real momentum or pump?
5. R:R: {rr_raw:.2f} — acceptable? (need >{MIN_RR_RATIO})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPOND IN JSON (Georgian text, English numbers/terms):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{
  "decision": "APPROVE" | "APPROVE_WITH_CAUTION" | "DELAY_ENTRY" | "REJECT",
  "adjusted_confidence": <number 0-100>,
  "risk_score": <number 0-100, 100=max danger>,
  "timing_advice": "PERFECT_TIMING" | "ENTER_NOW" | "WAIT_FOR_PULLBACK" | "TOO_LATE",
  "entry_zone_min": <price — lower bound of ideal entry>,
  "entry_zone_max": <price — upper bound of ideal entry>,
  "realistic_target_pct": <number — realistic % gain>,
  "suggested_stop_pct": <number — suggested stop % below entry>,
  "risk_reward_ratio": <calculated ratio>,
  "pump_risk": <true|false>,
  "near_resistance": <true|false>,
  "reasoning": [
    "ქართული ახსნა 1",
    "ქართული ახსნა 2",
    "ქართული ახსნა 3"
  ],
  "red_flags": ["flag1", "flag2"],
  "green_flags": ["flag1", "flag2"]
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DECISION CRITERIA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
APPROVE:             RSI 40-62, near EMA50, R:R>2, volume normal, target clear
APPROVE_WITH_CAUTION: RSI 62-68, slightly extended, R:R 1.5-2, manageable risks
DELAY_ENTRY:         technically valid but PRICE TOO HIGH NOW — wait for dip
REJECT:              RSI>70, pump detected, R:R<1.5, no clear target, against trend

BE BRUTAL. One bad trade destroys trust. Save the trader's money."""

        return prompt

    # ═══════════════════════════════════════════════════════════════════════
    # CLAUDE API CALL
    # ═══════════════════════════════════════════════════════════════════════

    async def _call_claude(self, prompt: str, retries: int = 2) -> str:
        for attempt in range(retries + 1):
            try:
                message = await self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )
                return message.content[0].text
            except anthropic.RateLimitError:
                wait = 20 * (attempt + 1)
                logger.warning(f"⚠️ Rate limit — waiting {wait}s")
                await asyncio.sleep(wait)
            except anthropic.APIError as e:
                if attempt < retries:
                    await asyncio.sleep(5)
                else:
                    raise e
        raise RuntimeError("Claude API failed after retries")

    # ═══════════════════════════════════════════════════════════════════════
    # RESPONSE PARSER
    # ═══════════════════════════════════════════════════════════════════════

    def _parse_response(
        self,
        text: str,
        original_conf: float,
        entry_price: float,
        tier: str
    ) -> AIEvaluation:

        try:
            # Extract JSON block
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text.strip())

            # Decision
            dec_str = data.get("decision", "APPROVE_WITH_CAUTION").upper()
            if dec_str not in {"APPROVE", "APPROVE_WITH_CAUTION", "DELAY_ENTRY", "REJECT"}:
                dec_str = "APPROVE_WITH_CAUTION"
            decision = AIDecision[dec_str]

            # Numerics
            adj_conf     = float(data.get("adjusted_confidence", original_conf * 0.85))
            risk_score   = float(data.get("risk_score", 55.0))
            target_pct   = float(data.get("realistic_target_pct", 8.0))
            stop_pct     = float(data.get("suggested_stop_pct", 5.0))
            rr_ratio     = float(data.get("risk_reward_ratio", 1.5))
            zone_min     = float(data.get("entry_zone_min", entry_price * 0.97))
            zone_max     = float(data.get("entry_zone_max", entry_price * 0.995))

            # Validate & clamp
            adj_conf   = max(0.0, min(100.0, adj_conf))
            risk_score = max(0.0, min(100.0, risk_score))
            target_pct = max(3.0, min(50.0, target_pct))
            stop_pct   = max(1.5, min(15.0, stop_pct))
            rr_ratio   = max(0.1, min(10.0, rr_ratio))

            # If AI gives R:R but didn't compute correctly — recalculate
            if stop_pct > 0 and target_pct > 0:
                rr_ratio = round(target_pct / stop_pct, 2)

            return AIEvaluation(
                decision=decision,
                adjusted_confidence=adj_conf,
                risk_score=risk_score,
                reasoning=self._ensure_list(data.get("reasoning", [])),
                timing_advice=data.get("timing_advice", "ENTER_NOW"),
                red_flags=self._ensure_list(data.get("red_flags", [])),
                green_flags=self._ensure_list(data.get("green_flags", [])),
                entry_zone_min=zone_min,
                entry_zone_max=zone_max,
                realistic_target_pct=target_pct,
                suggested_stop_pct=stop_pct,
                risk_reward_ratio=rr_ratio,
                pump_risk=bool(data.get("pump_risk", False)),
                near_resistance=bool(data.get("near_resistance", False)),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"⚠️ AI parse failed: {e} — using conservative fallback")
            return self._conservative_fallback(original_conf, entry_price, tier)

    # ═══════════════════════════════════════════════════════════════════════
    # SEND DECISION HELPER
    # ═══════════════════════════════════════════════════════════════════════

    def should_send_signal(self, evaluation: AIEvaluation) -> Tuple[bool, str]:
        """Returns (should_send, reason_text)"""

        if evaluation.decision == AIDecision.APPROVE:
            return True, "✅ AI დაადასტურა: პერფექტული timing"

        if evaluation.decision == AIDecision.APPROVE_WITH_CAUTION:
            if evaluation.adjusted_confidence >= AI_CAUTION_THRESHOLD:
                entry_txt = (
                    f"Entry zone: ${evaluation.entry_zone_min:.4f}–${evaluation.entry_zone_max:.4f}"
                    if evaluation.entry_zone_min > 0 else ""
                )
                return True, f"⚠️ AI: სიფრთხილით. {entry_txt}"
            return False, f"❌ AI: confidence {evaluation.adjusted_confidence:.0f}% — ძალიან დაბალია"

        if evaluation.decision == AIDecision.DELAY_ENTRY:
            return False, (
                f"⏳ AI: დაელოდე pullback-ს "
                f"${evaluation.entry_zone_min:.4f}–${evaluation.entry_zone_max:.4f}"
            )

        # REJECT
        flags = evaluation.red_flags[:2] if evaluation.red_flags else ["სუსტი სიგნალი"]
        return False, f"❌ AI უარყო: {' | '.join(flags)}"

    # ═══════════════════════════════════════════════════════════════════════
    # LEARNING FEEDBACK
    # ═══════════════════════════════════════════════════════════════════════

    def record_outcome(self, outcome: TradeOutcome):
        """Trade outcome ჩაწერა — AI context-ისთვის"""
        self.trade_outcomes.append(outcome)
        if len(self.trade_outcomes) > self.MAX_OUTCOMES:
            self.trade_outcomes.pop(0)

        win_count  = sum(1 for o in self.trade_outcomes if o.win)
        total      = len(self.trade_outcomes)
        win_rate   = win_count / total * 100 if total > 0 else 0
        logger.info(f"📊 Trade recorded: {outcome.symbol} {outcome.profit_pct:+.1f}% | Win rate: {win_rate:.1f}%")

    def get_win_rate(self, tier: str = None) -> float:
        outcomes = self.trade_outcomes
        if tier:
            outcomes = [o for o in outcomes if o.tier == tier]
        if not outcomes:
            return 0.0
        return sum(1 for o in outcomes if o.win) / len(outcomes) * 100

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _conservative_fallback(
        self, conf: float, entry_price: float, tier: str
    ) -> AIEvaluation:
        tier_risk = get_tier_risk(tier)
        stop_pct  = tier_risk["stop_loss_pct"]
        tgt_pct   = tier_risk["take_profit_pct"] * 0.7   # conservative
        rr        = round(tgt_pct / stop_pct, 2) if stop_pct > 0 else 1.2

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
            realistic_target_pct=tgt_pct,
            suggested_stop_pct=stop_pct,
            risk_reward_ratio=rr,
            pump_risk=False,
            near_resistance=False,
        )

    @staticmethod
    def _ensure_list(val) -> List[str]:
        if isinstance(val, list):
            return [str(v) for v in val]
        if isinstance(val, str):
            return [val]
        return []

    def get_stats(self) -> Dict:
        total = max(self.stats["total_evaluated"], 1)
        return {
            **self.stats,
            "approval_rate": f"{(self.stats['approved'] + self.stats['caution']) / total * 100:.1f}%",
            "rejection_rate": f"{self.stats['rejected'] / total * 100:.1f}%",
            "win_rate_all":  f"{self.get_win_rate():.1f}%",
        }
