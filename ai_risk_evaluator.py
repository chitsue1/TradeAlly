"""
AI Risk Intelligence v2.0 PROFESSIONAL
✅ BRUTAL timing analysis
✅ REALISTIC target assessment
✅ Entry zone optimization
✅ No FOMO, no optimism
"""
import logging, json
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import anthropic

logger = logging.getLogger(__name__)

class AIDecision(Enum):
    APPROVE = "APPROVE"
    APPROVE_WITH_CAUTION = "APPROVE_WITH_CAUTION"
    DELAY_ENTRY = "DELAY_ENTRY"
    REJECT = "REJECT"

@dataclass
class AIEvaluation:
    decision: AIDecision
    adjusted_confidence: float
    risk_score: float
    reasoning: List[str]
    timing_advice: str
    red_flags: List[str]
    green_flags: List[str]
    entry_zone_min: float = 0.0  # NEW: Better entry price (lower bound)
    entry_zone_max: float = 0.0  # NEW: Better entry price (upper bound)
    realistic_target_pct: float = 0.0  # NEW: More realistic target

class AIRiskEvaluator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        self.MIN_CONFIDENCE_THRESHOLD = 40  # Lowered from 45
        self.HIGH_RISK_THRESHOLD = 75
        self.CAUTION_CONFIDENCE_THRESHOLD = 50  # Lowered from 55
        logger.info("🧠 AI Risk Evaluator v2.0 PROFESSIONAL initialized")

    async def evaluate_signal(self, symbol: str, strategy_type: str, entry_price: float,
                             strategy_confidence: float, indicators: Dict, market_structure: Dict,
                             regime: str, tier: str) -> AIEvaluation:
        try:
            logger.debug(f"🧠 Professional analysis: {symbol}...")

            prompt = self._build_professional_prompt(
                symbol, strategy_type, entry_price, strategy_confidence,
                indicators, market_structure, regime, tier
            )

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text
            logger.debug(f"🧠 Response: {len(result_text)} chars")

            evaluation = self._parse_professional_response(result_text, strategy_confidence, entry_price)

            logger.info(
                f"🧠 {symbol}: {evaluation.decision.value} | "
                f"Conf: {strategy_confidence}% → {evaluation.adjusted_confidence:.0f}% | "
                f"Entry Zone: ${evaluation.entry_zone_min:.4f}-${evaluation.entry_zone_max:.4f}"
            )

            return evaluation

        except Exception as e:
            logger.error(f"❌ AI error: {e}")
            import traceback
            logger.error(traceback.format_exc())

            return AIEvaluation(
                decision=AIDecision.APPROVE_WITH_CAUTION,
                adjusted_confidence=strategy_confidence * 0.75,
                risk_score=55.0,
                reasoning=["AI დროებით მიუწვდომელია - კონსერვატიული დამტკიცება"],
                timing_advice="ENTER_NOW",
                red_flags=["AI სერვისი დროებით გამორთულია"],
                green_flags=[],
                entry_zone_min=entry_price * 0.97,
                entry_zone_max=entry_price,
                realistic_target_pct=8.0
            )

    def _build_professional_prompt(self, symbol: str, strategy_type: str, entry_price: float,
                                   strategy_confidence: float, indicators: Dict,
                                   market_structure: Dict, regime: str, tier: str) -> str:

        rsi = indicators.get('rsi', 50)
        prev_rsi = indicators.get('prev_rsi', 50)
        rsi_change = rsi - prev_rsi

        ema50 = indicators.get('ema50', entry_price)
        ema200 = indicators.get('ema200', entry_price)

        price_vs_ema50 = ((entry_price - ema50) / ema50 * 100) if ema50 > 0 else 0
        price_vs_ema200 = ((entry_price - ema200) / ema200 * 100) if ema200 > 0 else 0

        macd_hist = indicators.get('macd_histogram', 0)
        macd_prev = indicators.get('macd_histogram_prev', 0)

        volume = indicators.get('volume', 1000000)
        avg_volume = indicators.get('avg_volume_20d', 1000000)
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        support = market_structure.get('nearest_support', entry_price * 0.95)
        resistance = market_structure.get('nearest_resistance', entry_price * 1.05)

        distance_to_support = ((entry_price - support) / support * 100) if support > 0 else 5
        distance_to_resistance = ((resistance - entry_price) / entry_price * 100) if entry_price > 0 else 5

        return f"""You are a PROFESSIONAL TRADER with 10+ years experience. Analyze this signal with BRUTAL HONESTY.

**MANDATE:**
- Kill all FOMO and optimism
- Focus on TIMING: are we early, perfect, or late?
- Provide REALISTIC targets, not dreams
- Suggest better entry zones if current price is bad

═══════════════════════════════════════════════════════════

**SIGNAL ANALYSIS:**

Symbol: {symbol} ({tier})
Strategy: {strategy_type}
Current Price: ${entry_price:.4f}
Strategy Confidence: {strategy_confidence}% ← VERIFY THIS!

**TECHNICAL SNAPSHOT:**

RSI: {rsi:.1f} (was {prev_rsi:.1f}, change: {rsi_change:+.1f})
  → {f"🔴 OVERBOUGHT! RSI > 65" if rsi > 65 else f"🟡 High {rsi:.0f}" if rsi > 60 else "🟢 OK"}

Price vs EMA50: {price_vs_ema50:+.2f}%
  → {f"🔴 FAR ABOVE EMA50 - ფასი გადაჭარბებულია" if price_vs_ema50 > 5 else "🟢 Near EMA50"}

Price vs EMA200: {price_vs_ema200:+.2f}%

MACD: {macd_hist:.6f} (previous: {macd_prev:.6f})
  → {"🟢 Improving" if macd_hist > macd_prev else "🔴 Weakening"}

Volume: {volume_ratio:.2f}x average
  → {f"🔴 SUSPICIOUS SPIKE! >2x average" if volume_ratio > 2.0 else f"🟡 High volume" if volume_ratio > 1.5 else "🟢 Normal"}

Support: ${support:.4f} ({distance_to_support:.1f}% ქვემოთ)
Resistance: ${resistance:.4f} ({distance_to_resistance:.1f}% ზემოთ)

Market Regime: {regime}

═══════════════════════════════════════════════════════════

**YOUR CRITICAL QUESTIONS:**

1. **TIMING CHECK:**
   - RSI {rsi:.0f}: Are we TOO LATE? Already overbought?
   - Price vs EMA50 ({price_vs_ema50:+.1f}%): Did we miss the entry?
   - MACD turning: Is momentum real or fading?

   → If RSI > 65 OR price > EMA50+3%: "გვიან ხარ - ფასი უკვე გაიზარდა"

2. **ENTRY ZONE OPTIMIZATION:**
   - Current: ${entry_price:.4f}
   - Better entry if pullback: ${entry_price * 0.97:.4f} - ${entry_price * 0.99:.4f}?
   - Support zone: ${support:.4f}

   → Suggest: Wait for dip OR aggressive entry now?

3. **REALISTIC TARGET:**
   - Distance to resistance: {distance_to_resistance:.1f}%
   - Distance to EMA200: {price_vs_ema200:+.1f}%

   → What's ACHIEVABLE target? Not fantasy!
   → If resistance close (<5%): "Target unrealistic"

4. **VOLUME ANALYSIS:**
   - {volume_ratio:.2f}x: Real momentum or PUMP?
   → If >2.0x: "Volume spike საეჭვოა - pump risk"

5. **RISK/REWARD:**
   - Support distance: {distance_to_support:.1f}%
   - Resistance distance: {distance_to_resistance:.1f}%
   → Is R:R worth it? (need >1.5)

═══════════════════════════════════════════════════════════

**RESPOND IN GEORGIAN (use ქართული for text, keep numbers/terms English):**

{{
  "decision": "APPROVE" or "APPROVE_WITH_CAUTION" or "DELAY_ENTRY" or "REJECT",
  "adjusted_confidence": 42,
  "risk_score": 65,
  "timing_advice": "TOO_LATE" or "WAIT_FOR_PULLBACK" or "ENTER_NOW" or "PERFECT_TIMING",
  "entry_zone_min": {entry_price * 0.96:.4f},
  "entry_zone_max": {entry_price * 0.98:.4f},
  "realistic_target_pct": 7.5,
  "reasoning": [
    "RSI 68 - overbought, ფასი უკვე გაიზარდა +5%",
    "უკეთესი შესვლა: დაელოდე pullback ${entry_price * 0.97:.4f}-მდე",
    "რეალისტური Target: +7-8%, არა +16%"
  ],
  "red_flags": [
    "ფასი EMA50-ზე +{price_vs_ema50:.1f}% - გვიან ხარ შესვლისთვის",
    "Volume {volume_ratio:.1f}x - საეჭვო spike, pump რისკი",
    "Resistance {distance_to_resistance:.1f}% ზემოთ - ახლოსაა, rejection რისკი"
  ],
  "green_flags": [
    "EMA50 > EMA200 - გრძელვადიანი uptrend",
    "Support ${support:.4f}-ზე ძლიერია",
    "MACD momentum დადებითია"
  ]
}}

═══════════════════════════════════════════════════════════

**DECISION LOGIC:**

APPROVE:
  - Perfect timing (RSI 45-60, price near EMA50)
  - Strong structure (support strong, R:R > 2)
  - Realistic target achievable

APPROVE_WITH_CAUTION:
  - OK timing but late entry (RSI 60-65)
  - R:R decent (1.5-2.0)
  - Some red flags but manageable

DELAY_ENTRY:
  - Too late now (RSI > 65, price extended)
  - Wait for pullback to better zone
  - Structure OK but timing bad

REJECT:
  - Overbought (RSI > 70)
  - Fake pump (volume spike >2.5x)
  - R:R terrible (<1.5)
  - Target unrealistic

═══════════════════════════════════════════════════════════

BE BRUTAL. BE HONEST. SAVE THE TRADER'S MONEY."""

    def _parse_professional_response(self, text: str, original_conf: float, entry_price: float) -> AIEvaluation:
        try:
            text = text.strip()

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            text = text.strip()
            data = json.loads(text)

            decision_str = data.get("decision", "APPROVE_WITH_CAUTION")
            if decision_str not in ["APPROVE", "APPROVE_WITH_CAUTION", "DELAY_ENTRY", "REJECT"]:
                decision_str = "APPROVE_WITH_CAUTION"

            decision = AIDecision[decision_str]

            adjusted_conf = float(data.get("adjusted_confidence", original_conf * 0.8))
            risk_score = float(data.get("risk_score", 55.0))
            timing = data.get("timing_advice", "ENTER_NOW")

            entry_zone_min = float(data.get("entry_zone_min", entry_price * 0.97))
            entry_zone_max = float(data.get("entry_zone_max", entry_price * 0.99))
            realistic_target = float(data.get("realistic_target_pct", 8.0))

            reasoning = data.get("reasoning", ["AI ანალიზი ჩატარდა"])
            red_flags = data.get("red_flags", [])
            green_flags = data.get("green_flags", [])

            if not isinstance(reasoning, list):
                reasoning = [str(reasoning)]
            if not isinstance(red_flags, list):
                red_flags = []
            if not isinstance(green_flags, list):
                green_flags = []

            adjusted_conf = max(0.0, min(100.0, adjusted_conf))
            risk_score = max(0.0, min(100.0, risk_score))
            realistic_target = max(3.0, min(20.0, realistic_target))

            return AIEvaluation(
                decision=decision,
                adjusted_confidence=adjusted_conf,
                risk_score=risk_score,
                reasoning=reasoning,
                timing_advice=timing,
                red_flags=red_flags,
                green_flags=green_flags,
                entry_zone_min=entry_zone_min,
                entry_zone_max=entry_zone_max,
                realistic_target_pct=realistic_target
            )

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse: {e}")
            logger.error(f"Response: {text[:300]}")

            return AIEvaluation(
                AIDecision.APPROVE_WITH_CAUTION,
                original_conf * 0.75, 60.0,
                ["JSON parsing შეცდომა - კონსერვატიული დამტკიცება"],
                "ENTER_NOW", ["Parsing error"], [],
                entry_price * 0.97, entry_price * 0.99, 8.0
            )
        except Exception as e:
            logger.error(f"❌ Parse error: {e}")
            return AIEvaluation(
                AIDecision.APPROVE_WITH_CAUTION,
                original_conf * 0.75, 60.0,
                ["Parse შეცდომა"], "ENTER_NOW",
                ["Unknown error"], [],
                entry_price * 0.97, entry_price * 0.99, 8.0
            )

    def should_send_signal(self, evaluation: AIEvaluation) -> Tuple[bool, str]:
        if evaluation.decision == AIDecision.APPROVE:
            return True, "AI დაადასტურა: პერფექტული timing"

        elif evaluation.decision == AIDecision.APPROVE_WITH_CAUTION:
            if evaluation.adjusted_confidence >= self.CAUTION_CONFIDENCE_THRESHOLD:
                return True, f"AI დაადასტურა სიფრთხილით (Entry Zone: ${evaluation.entry_zone_min:.4f}-${evaluation.entry_zone_max:.4f})"
            else:
                return False, f"AI დაბლოკა: ქონფიდენსი {evaluation.adjusted_confidence:.0f}% ძალიან დაბალია"

        elif evaluation.decision == AIDecision.DELAY_ENTRY:
            return False, f"AI: {evaluation.timing_advice} - დაელოდე უკეთეს ფასს ${evaluation.entry_zone_min:.4f}-${evaluation.entry_zone_max:.4f}"

        elif evaluation.decision == AIDecision.REJECT:
            flags = evaluation.red_flags[:2] if evaluation.red_flags else ["სუსტი სიგნალი"]
            return False, f"AI უარყო: {' | '.join(flags)}"

        return False, "AI გაურკვეველი"