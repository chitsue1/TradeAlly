"""
AI Risk Intelligence Layer v1.0 FINAL
✅ Independent confidence recalculation
✅ Fake breakout detection
✅ Georgian language output
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
            prompt = self._build_evaluation_prompt(symbol, strategy_type, entry_price,
                                                  strategy_confidence, indicators, market_structure, regime, tier)

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text
            evaluation = self._parse_ai_response(result_text, strategy_confidence)

            logger.info(f"🧠 {symbol}: {evaluation.decision.value} | "
                       f"Conf: {strategy_confidence}% → {evaluation.adjusted_confidence}%")

            return evaluation

        except Exception as e:
            logger.error(f"❌ AI failed for {symbol}: {e}")
            return AIEvaluation(
                decision=AIDecision.APPROVE_WITH_CAUTION,
                adjusted_confidence=strategy_confidence * 0.85,
                risk_score=50.0,
                reasoning=["AI შეფასება ვერ მოხერხდა"],
                timing_advice="ENTER_NOW",
                red_flags=["AI არ მუშაობს"],
                green_flags=[]
            )

    def _build_evaluation_prompt(self, symbol: str, strategy_type: str, entry_price: float,
                                 strategy_confidence: float, indicators: Dict, market_structure: Dict,
                                 regime: str, tier: str) -> str:
        rsi = indicators.get('rsi', 50)
        prev_rsi = indicators.get('prev_rsi', 50)
        rsi_change = rsi - prev_rsi
        ema50 = indicators.get('ema50', entry_price)
        ema200 = indicators.get('ema200', entry_price)
        macd_hist = indicators.get('macd_histogram', 0)
        macd_hist_prev = indicators.get('macd_histogram_prev', 0)
        macd_momentum = "turning positive" if macd_hist > macd_hist_prev else "weakening"
        bb_width = indicators.get('bb_width', 0)
        avg_bb_width = indicators.get('avg_bb_width_20d', bb_width)
        squeeze_ratio = bb_width / avg_bb_width if avg_bb_width > 0 else 1.0
        volume = indicators.get('volume', 1000000)
        avg_volume = indicators.get('avg_volume_20d', 1000000)
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
        support = market_structure.get('nearest_support', entry_price * 0.95)
        resistance = market_structure.get('nearest_resistance', entry_price * 1.05)
        volume_trend = market_structure.get('volume_trend', 'stable')

        return f"""You are an OPTIMISM KILLER and FAKE BREAKOUT DETECTOR for crypto signals.

**MISSION:** Be EXTREMELY SKEPTICAL. Assume signals are WEAK until proven strong.

**SIGNAL:**
Symbol: {symbol} ({tier})
Strategy: {strategy_type}
Entry: ${entry_price:.2f}
Strategy Confidence: {strategy_confidence}% ← CHALLENGE THIS!

**DATA:**
RSI: {rsi:.1f} (prev: {prev_rsi:.1f}, change: {rsi_change:+.1f})
EMA50: ${ema50:.2f} | EMA200: ${ema200:.2f}
Price vs EMA50: {((entry_price - ema50) / ema50 * 100):+.2f}%
MACD: {macd_hist:.4f} ({macd_momentum})
Volume: {volume_ratio:.2f}x avg ({volume_trend})
BB Squeeze: {squeeze_ratio:.2f}
Support: ${support:.2f} ({((entry_price - support) / support * 100):.1f}% away)
Resistance: ${resistance:.2f}
Regime: {regime}

**CHECKLIST:**
1. FAKE BREAKOUT? Volume real or spike? Entering at top?
2. MOMENTUM? RSI genuine? MACD confirming?
3. STRUCTURE? Support strong? Resistance close?
4. TIMING? Enter NOW or WAIT?
5. REALISTIC CONFIDENCE? {strategy_confidence}% accurate?

**RESPOND IN GEORGIAN (ქართული):**

Provide analysis in Georgian language with technical terms in English where needed.

**JSON FORMAT:**

{{
  "decision": "APPROVE" or "APPROVE_WITH_CAUTION" or "DELAY_ENTRY" or "REJECT",
  "adjusted_confidence": 45.5,
  "risk_score": 67.0,
  "timing_advice": "ENTER_NOW" or "WAIT_1H" or "WAIT_4H",
  "reasoning": [
    "მიზეზი 1 ქართულად",
    "მიზეზი 2 ქართულად"
  ],
  "red_flags": [
    "გაფრთხილება 1 ქართულად",
    "გაფრთხილება 2 ქართულად"
  ],
  "green_flags": [
    "დადებითი 1 ქართულად",
    "დადებითი 2 ქართულად"
  ]
}}

**DECISIONS:**
- APPROVE: ძლიერი სიგნალი, შედი ახლავე
- APPROVE_WITH_CAUTION: კარგი სიგნალი, მაგრამ რისკია
- DELAY_ENTRY: დაელოდე 1-4 საათი
- REJECT: სუსტი სიგნალი, არ შედიხარ

BE HARSH. KILL OPTIMISM. Respond ONLY with JSON."""

    def _parse_ai_response(self, response_text: str, original_confidence: float) -> AIEvaluation:
        try:
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()

            data = json.loads(response_text)
            decision_str = data.get("decision", "APPROVE_WITH_CAUTION")
            decision = AIDecision[decision_str]
            adjusted_confidence = float(data.get("adjusted_confidence", original_confidence * 0.9))
            risk_score = float(data.get("risk_score", 50.0))
            timing_advice = data.get("timing_advice", "ENTER_NOW")
            reasoning = data.get("reasoning", [])
            red_flags = data.get("red_flags", [])
            green_flags = data.get("green_flags", [])

            adjusted_confidence = max(0.0, min(100.0, adjusted_confidence))
            risk_score = max(0.0, min(100.0, risk_score))

            return AIEvaluation(decision, adjusted_confidence, risk_score, reasoning,
                              timing_advice, red_flags, green_flags)
        except Exception as e:
            logger.error(f"❌ Parse failed: {e}")
            return AIEvaluation(
                AIDecision.APPROVE_WITH_CAUTION, original_confidence * 0.85, 55.0,
                ["AI პასუხის პარსინგი ვერ მოხერხდა"], "ENTER_NOW",
                ["პარსინგის შეცდომა"], []
            )

    def should_send_signal(self, evaluation: AIEvaluation) -> Tuple[bool, str]:
        if evaluation.decision == AIDecision.APPROVE:
            return True, "AI დაადასტურა: ძლიერი სიგნალი"
        elif evaluation.decision == AIDecision.APPROVE_WITH_CAUTION:
            if evaluation.adjusted_confidence >= self.CAUTION_CONFIDENCE_THRESHOLD:
                return True, "AI დაადასტურა სიფრთხილით"
            else:
                return False, f"AI დაბლოკა: ქონფიდენსი ძალიან დაბალია ({evaluation.adjusted_confidence:.0f}%)"
        elif evaluation.decision == AIDecision.DELAY_ENTRY:
            return False, f"AI: დაელოდე {evaluation.timing_advice}"
        elif evaluation.decision == AIDecision.REJECT:
            return False, f"AI უარყო: {', '.join(evaluation.red_flags[:2])}"
        return False, "AI გაურკვეველი"