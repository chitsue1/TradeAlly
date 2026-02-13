"""
AI Risk Intelligence Layer v1.0 - PRODUCTION
✅ Independent confidence recalculation
✅ Fake breakout detection
✅ Timing optimization
✅ Realistic risk assessment

Uses Claude API for intelligent signal evaluation
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import anthropic

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# DECISION TYPES
# ════════════════════════════════════════════════════════════════

class AIDecision(Enum):
    """AI evaluation decisions"""
    APPROVE = "APPROVE"  # Strong signal, enter now
    APPROVE_WITH_CAUTION = "APPROVE_WITH_CAUTION"  # Enter but lower confidence
    DELAY_ENTRY = "DELAY_ENTRY"  # Wait for better confirmation
    REJECT = "REJECT"  # Weak signal, do not enter

@dataclass
class AIEvaluation:
    """AI evaluation result"""
    decision: AIDecision
    adjusted_confidence: float  # Recalculated confidence (0-100)
    risk_score: float  # Risk level (0-100, higher = riskier)
    reasoning: List[str]  # Why this decision
    timing_advice: str  # ENTER_NOW, WAIT_1H, WAIT_4H
    red_flags: List[str]  # Warning signs detected
    green_flags: List[str]  # Positive confirmations

# ════════════════════════════════════════════════════════════════
# AI RISK EVALUATOR
# ════════════════════════════════════════════════════════════════

class AIRiskEvaluator:
    """
    🧠 AI Risk Intelligence Layer

    Acts as independent validator using Claude API
    - Kills optimism bias
    - Detects fake breakouts
    - Recalculates confidence realistically
    - Optimizes entry timing
    """

    def __init__(self, api_key: str):
        """
        Initialize AI Risk Evaluator

        Args:
            api_key: Anthropic API key
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"  # Latest Sonnet

        # Thresholds
        self.MIN_CONFIDENCE_THRESHOLD = 45  # Below this = REJECT
        self.HIGH_RISK_THRESHOLD = 75  # Above this = DELAY or REJECT
        self.CAUTION_CONFIDENCE_THRESHOLD = 55  # Below this = APPROVE_WITH_CAUTION

        logger.info("🧠 AI Risk Evaluator initialized (Claude Sonnet 4)")

    async def evaluate_signal(
        self,
        symbol: str,
        strategy_type: str,
        entry_price: float,
        strategy_confidence: float,
        indicators: Dict,
        market_structure: Dict,
        regime: str,
        tier: str
    ) -> AIEvaluation:
        """
        Evaluate signal with AI intelligence

        Returns:
            AIEvaluation with decision and reasoning
        """

        try:
            # Build evaluation prompt
            prompt = self._build_evaluation_prompt(
                symbol=symbol,
                strategy_type=strategy_type,
                entry_price=entry_price,
                strategy_confidence=strategy_confidence,
                indicators=indicators,
                market_structure=market_structure,
                regime=regime,
                tier=tier
            )

            # Call Claude API
            logger.debug(f"🧠 Evaluating {symbol} signal via Claude API...")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            result_text = response.content[0].text
            logger.debug(f"🧠 AI response received: {len(result_text)} chars")

            # Extract structured data from response
            evaluation = self._parse_ai_response(result_text, strategy_confidence)

            logger.info(
                f"🧠 {symbol}: {evaluation.decision.value} | "
                f"Confidence: {strategy_confidence}% → {evaluation.adjusted_confidence}% | "
                f"Risk: {evaluation.risk_score}%"
            )

            return evaluation

        except Exception as e:
            logger.error(f"❌ AI evaluation failed for {symbol}: {e}")

            # Fallback: conservative approval
            return AIEvaluation(
                decision=AIDecision.APPROVE_WITH_CAUTION,
                adjusted_confidence=strategy_confidence * 0.85,  # Reduce by 15%
                risk_score=50.0,
                reasoning=["⚠️ AI evaluation failed - using conservative approval"],
                timing_advice="ENTER_NOW",
                red_flags=["AI evaluation unavailable"],
                green_flags=[]
            )

    def _build_evaluation_prompt(
        self,
        symbol: str,
        strategy_type: str,
        entry_price: float,
        strategy_confidence: float,
        indicators: Dict,
        market_structure: Dict,
        regime: str,
        tier: str
    ) -> str:
        """Build AI evaluation prompt"""

        # Extract key indicators
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

        prompt = f"""You are an OPTIMISM KILLER and FAKE BREAKOUT DETECTOR for crypto trading signals.

**CRITICAL MISSION:**
- Be EXTREMELY SKEPTICAL
- Assume signals are WEAK until proven strong
- Detect FAKE BREAKOUTS ruthlessly
- Recalculate confidence REALISTICALLY (usually LOWER than strategy suggests)
- Focus on TIMING - is this the RIGHT moment or should we WAIT?

**SIGNAL TO EVALUATE:**

Symbol: {symbol} ({tier} tier)
Strategy: {strategy_type}
Entry Price: ${entry_price:.2f}
Strategy Confidence: {strategy_confidence}% ← CHALLENGE THIS!

**TECHNICAL DATA:**

RSI: {rsi:.1f} (previous: {prev_rsi:.1f}, change: {rsi_change:+.1f})
EMA50: ${ema50:.2f} | EMA200: ${ema200:.2f}
Price vs EMA50: {((entry_price - ema50) / ema50 * 100):+.2f}%
Price vs EMA200: {((entry_price - ema200) / ema200 * 100):+.2f}%

MACD Histogram: {macd_hist:.4f} ({macd_momentum})
Previous MACD: {macd_hist_prev:.4f}

Volume: {volume_ratio:.2f}x average ({volume_trend} trend)
BB Squeeze Ratio: {squeeze_ratio:.2f} (< 0.7 = squeeze)

Support: ${support:.2f} ({((entry_price - support) / support * 100):.1f}% away)
Resistance: ${resistance:.2f} ({((resistance - entry_price) / resistance * 100):.1f}% away)

Market Regime: {regime}

**YOUR EVALUATION CHECKLIST:**

1. **FAKE BREAKOUT DETECTION:**
   - Is volume REALLY confirming? Or suspicious spike?
   - Is this breakout REAL or will it fail?
   - Are we entering at LOCAL TOP?

2. **MOMENTUM ANALYSIS:**
   - Is RSI momentum GENUINE or just noise?
   - Is MACD confirming or just turning?
   - Is volume SUSTAINABLE?

3. **STRUCTURE QUALITY:**
   - Is support STRONG enough?
   - Is resistance CLOSE (risk of rejection)?
   - Is price action CLEAN or CHOPPY?

4. **TIMING:**
   - Should we enter NOW or WAIT for better confirmation?
   - Are we entering too EARLY?
   - Is this FOMO or LOGIC?

5. **REALISTIC CONFIDENCE:**
   - Strategy says {strategy_confidence}% - is this REALISTIC?
   - What's ACTUAL probability of success?
   - What could GO WRONG?

**RESPOND IN THIS EXACT JSON FORMAT:**

{{
  "decision": "APPROVE" or "APPROVE_WITH_CAUTION" or "DELAY_ENTRY" or "REJECT",
  "adjusted_confidence": 45.5,
  "risk_score": 67.0,
  "timing_advice": "ENTER_NOW" or "WAIT_1H" or "WAIT_4H",
  "reasoning": [
    "Point 1 why this decision",
    "Point 2",
    "Point 3"
  ],
  "red_flags": [
    "Warning sign 1",
    "Warning sign 2"
  ],
  "green_flags": [
    "Positive confirmation 1",
    "Positive confirmation 2"
  ]
}}

**DECISION CRITERIA:**

- **APPROVE:** Strong setup, all confirmations present, enter NOW
- **APPROVE_WITH_CAUTION:** Decent setup but some concerns, reduce position size
- **DELAY_ENTRY:** Setup forming but needs better confirmation, wait 1-4 hours
- **REJECT:** Weak setup, fake breakout likely, or too risky

**BE HARSH. BE REALISTIC. KILL OPTIMISM.**

Respond with ONLY the JSON object, no other text."""

        return prompt

    def _parse_ai_response(
        self,
        response_text: str,
        original_confidence: float
    ) -> AIEvaluation:
        """Parse Claude's JSON response"""

        try:
            # Extract JSON from response
            response_text = response_text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            response_text = response_text.strip()

            # Parse JSON
            data = json.loads(response_text)

            # Extract fields
            decision_str = data.get("decision", "APPROVE_WITH_CAUTION")
            decision = AIDecision[decision_str]

            adjusted_confidence = float(data.get("adjusted_confidence", original_confidence * 0.9))
            risk_score = float(data.get("risk_score", 50.0))
            timing_advice = data.get("timing_advice", "ENTER_NOW")
            reasoning = data.get("reasoning", [])
            red_flags = data.get("red_flags", [])
            green_flags = data.get("green_flags", [])

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

        except Exception as e:
            logger.error(f"❌ Failed to parse AI response: {e}")
            logger.error(f"   Response text: {response_text[:500]}")

            # Fallback
            return AIEvaluation(
                decision=AIDecision.APPROVE_WITH_CAUTION,
                adjusted_confidence=original_confidence * 0.85,
                risk_score=55.0,
                reasoning=["⚠️ AI response parsing failed - conservative approval"],
                timing_advice="ENTER_NOW",
                red_flags=["AI parsing error"],
                green_flags=[]
            )

    def should_send_signal(self, evaluation: AIEvaluation) -> Tuple[bool, str]:
        """
        Decide if signal should be sent based on AI evaluation

        Returns:
            (should_send: bool, reason: str)
        """

        if evaluation.decision == AIDecision.APPROVE:
            return True, "AI approved: Strong signal"

        elif evaluation.decision == AIDecision.APPROVE_WITH_CAUTION:
            if evaluation.adjusted_confidence >= self.CAUTION_CONFIDENCE_THRESHOLD:
                return True, "AI approved with caution: Decent setup"
            else:
                return False, f"AI blocked: Confidence too low ({evaluation.adjusted_confidence:.0f}%)"

        elif evaluation.decision == AIDecision.DELAY_ENTRY:
            return False, f"AI delayed: {evaluation.timing_advice} - needs better confirmation"

        elif evaluation.decision == AIDecision.REJECT:
            return False, f"AI rejected: {', '.join(evaluation.red_flags[:2])}"

        return False, "AI evaluation unclear"