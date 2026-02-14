"""
AI Risk Intelligence Layer v1.1 FINAL
✅ Fixed Georgian output
✅ Better error handling
✅ Simpler, more reliable
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

class AIRiskEvaluator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        self.MIN_CONFIDENCE_THRESHOLD = 45
        self.HIGH_RISK_THRESHOLD = 75
        self.CAUTION_CONFIDENCE_THRESHOLD = 55
        logger.info("🧠 AI Risk Evaluator initialized")

    async def evaluate_signal(self, symbol: str, strategy_type: str, entry_price: float,
                             strategy_confidence: float, indicators: Dict, market_structure: Dict,
                             regime: str, tier: str) -> AIEvaluation:
        try:
            logger.debug(f"🧠 Calling Claude API for {symbol}...")

            prompt = self._build_prompt(symbol, strategy_type, entry_price,
                                       strategy_confidence, indicators, market_structure, regime, tier)

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text
            logger.debug(f"🧠 Response: {result_text[:200]}...")

            evaluation = self._parse_response(result_text, strategy_confidence)

            logger.info(f"🧠 {symbol}: {evaluation.decision.value} | "
                       f"{strategy_confidence}% → {evaluation.adjusted_confidence}%")

            return evaluation

        except Exception as e:
            logger.error(f"❌ AI error for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # Fallback
            return AIEvaluation(
                decision=AIDecision.APPROVE_WITH_CAUTION,
                adjusted_confidence=strategy_confidence * 0.85,
                risk_score=50.0,
                reasoning=["AI შეფასება დროებით მიუწვდომელია"],
                timing_advice="ENTER_NOW",
                red_flags=["AI API შეცდომა - სერვისი დროებით გამორთულია"],
                green_flags=[]
            )

    def _build_prompt(self, symbol: str, strategy_type: str, entry_price: float,
                     strategy_confidence: float, indicators: Dict, market_structure: Dict,
                     regime: str, tier: str) -> str:

        rsi = indicators.get('rsi', 50)
        prev_rsi = indicators.get('prev_rsi', 50)
        ema50 = indicators.get('ema50', entry_price)
        ema200 = indicators.get('ema200', entry_price)
        macd_hist = indicators.get('macd_histogram', 0)
        volume = indicators.get('volume', 1000000)
        avg_volume = indicators.get('avg_volume_20d', 1000000)
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        return f"""Evaluate this crypto trading signal. Be SKEPTICAL and REALISTIC.

Symbol: {symbol} ({tier})
Strategy: {strategy_type}
Entry Price: ${entry_price:.4f}
Strategy Confidence: {strategy_confidence}%

Technical Data:
- RSI: {rsi:.1f} (previous: {prev_rsi:.1f})
- EMA50: ${ema50:.2f}
- EMA200: ${ema200:.2f}
- MACD Histogram: {macd_hist:.6f}
- Volume: {volume_ratio:.2f}x average
- Market Regime: {regime}

Your task:
1. Is this a REAL opportunity or FAKE breakout?
2. Is RSI too high (overbought)?
3. Is volume confirming or suspicious?
4. Should we enter NOW or WAIT?
5. What's REALISTIC confidence? (Strategy says {strategy_confidence}%)

Respond in this EXACT JSON format (no markdown, no extra text):

{{
  "decision": "APPROVE",
  "adjusted_confidence": 52,
  "risk_score": 45,
  "timing_advice": "ENTER_NOW",
  "reasoning": [
    "RSI ბალანსირებულია - არც overbought არცერთი",
    "EMA50 ტრენდი დადებითია"
  ],
  "red_flags": [
    "Volume spike საეჭვოა",
    "Resistance ძალიან ახლოსაა"
  ],
  "green_flags": [
    "Support ძლიერია $X-ზე",
    "MACD დადებითი momentum"
  ]
}}

Decision types:
- APPROVE: Strong signal, enter now
- APPROVE_WITH_CAUTION: Decent but risky
- DELAY_ENTRY: Wait 1-4 hours
- REJECT: Weak signal, don't enter

BE HARSH. Lower confidence if uncertain. Use Georgian for reasoning/flags."""

    def _parse_response(self, text: str, original_conf: float) -> AIEvaluation:
        try:
            # Clean response
            text = text.strip()

            # Remove markdown if present
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            text = text.strip()

            # Parse JSON
            data = json.loads(text)

            decision_str = data.get("decision", "APPROVE_WITH_CAUTION")

            # Handle decision string variations
            if decision_str not in ["APPROVE", "APPROVE_WITH_CAUTION", "DELAY_ENTRY", "REJECT"]:
                decision_str = "APPROVE_WITH_CAUTION"

            decision = AIDecision[decision_str]

            adjusted_confidence = float(data.get("adjusted_confidence", original_conf * 0.9))
            risk_score = float(data.get("risk_score", 50.0))
            timing_advice = data.get("timing_advice", "ENTER_NOW")
            reasoning = data.get("reasoning", ["AI შეფასება ჩატარდა"])
            red_flags = data.get("red_flags", [])
            green_flags = data.get("green_flags", [])

            # Ensure lists
            if not isinstance(reasoning, list):
                reasoning = [str(reasoning)]
            if not isinstance(red_flags, list):
                red_flags = [str(red_flags)] if red_flags else []
            if not isinstance(green_flags, list):
                green_flags = [str(green_flags)] if green_flags else []

            # Validate ranges
            adjusted_confidence = max(0.0, min(100.0, adjusted_confidence))
            risk_score = max(0.0, min(100.0, risk_score))

            return AIEvaluation(
                decision=decision,
                adjusted_confidence=adjusted_confidence,
                risk_score=risk_score,
                reasoning=reasoning,
                timing_advice=timing_advice,
                red_flags=red_flags,
                green_flags=green_flags
            )

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            logger.error(f"   Response was: {text[:300]}")

            return AIEvaluation(
                decision=AIDecision.APPROVE_WITH_CAUTION,
                adjusted_confidence=original_conf * 0.85,
                risk_score=55.0,
                reasoning=["AI პასუხის ფორმატი არასწორია"],
                timing_advice="ENTER_NOW",
                red_flags=["JSON parsing შეცდომა"],
                green_flags=[]
            )

        except Exception as e:
            logger.error(f"❌ Parse error: {e}")

            return AIEvaluation(
                decision=AIDecision.APPROVE_WITH_CAUTION,
                adjusted_confidence=original_conf * 0.85,
                risk_score=55.0,
                reasoning=["AI შეფასება ნაწილობრივ ჩატარდა"],
                timing_advice="ENTER_NOW",
                red_flags=["Parsing შეცდომა"],
                green_flags=[]
            )

    def should_send_signal(self, evaluation: AIEvaluation) -> Tuple[bool, str]:
        if evaluation.decision == AIDecision.APPROVE:
            return True, "AI დაადასტურა: ძლიერი სიგნალი"

        elif evaluation.decision == AIDecision.APPROVE_WITH_CAUTION:
            if evaluation.adjusted_confidence >= self.CAUTION_CONFIDENCE_THRESHOLD:
                return True, "AI დაადასტურა სიფრთხილით"
            else:
                return False, f"AI დაბლოკა: ქონფიდენსი {evaluation.adjusted_confidence:.0f}%"

        elif evaluation.decision == AIDecision.DELAY_ENTRY:
            return False, f"AI: დაელოდე {evaluation.timing_advice}"

        elif evaluation.decision == AIDecision.REJECT:
            flags = ", ".join(evaluation.red_flags[:2]) if evaluation.red_flags else "სუსტი სიგნალი"
            return False, f"AI უარყო: {flags}"

        return False, "AI გაურკვეველი"