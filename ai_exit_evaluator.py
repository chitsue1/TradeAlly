"""
═══════════════════════════════════════════════════════════════════════════════
AI EXIT EVALUATOR v1.0 — Hold-ის დროს Partial Exit რეკომენდაცია
═══════════════════════════════════════════════════════════════════════════════

გამოძახება: position +8%-ზეა (target-ის 70%)
AI ამოწმებს: RSI, MACD, volume, resistance distance
გადაწყვეტს: HOLD_ALL / TAKE_PARTIAL (50%) / TAKE_FULL

Telegram-ში იგზავნება:
  "📊 SOL/USD +8.2% | AI: გამოიტანე 50%
   🟡 Target ახლოსაა, momentum ასუსტებს
   100$ → $50 lock + $50 hold"
═══════════════════════════════════════════════════════════════════════════════
"""

import logging
import json
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum

import anthropic

from config import AI_MODEL, AI_MAX_TOKENS, ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)


class ExitAdvice(Enum):
    HOLD_ALL     = "HOLD_ALL"       # ნუ გაყიდი, momentum ძლიერია
    TAKE_PARTIAL = "TAKE_PARTIAL"   # 50% გაყიდე, 50% hold
    TAKE_FULL    = "TAKE_FULL"      # სრულად გაყიდე


@dataclass
class ExitEvaluation:
    advice:          ExitAdvice
    reasoning:       str            # ქართულად
    confidence:      float          # 0-100
    partial_pct:     float = 50.0   # რამდენი % გამოვიტანოთ
    sim_locked_usd:  float = 0.0    # 100$-დან locked profit
    sim_remain_usd:  float = 0.0    # რამდენი hold-ში რჩება
    warning:         str  = ""      # გაფრთხილება


class AIExitEvaluator:
    """
    Hold-ის დროს AI-ს ეკითხება: გავაგრძელოთ თუ ნაწილი გამოვიტანოთ?

    გამოძახდება position_monitor.py-დან:
    - target-ის 70%-ზე მიღწევისას
    - RSI > 68 hold-ის დროს
    - ყოველ 4 საათში (swing სტრატეგიისთვის)
    """

    def __init__(self, api_key: str = None):
        self.client = anthropic.AsyncAnthropic(api_key=api_key or ANTHROPIC_API_KEY)
        self.model  = AI_MODEL
        logger.info("✅ AIExitEvaluator initialized")

    async def evaluate_exit(
        self,
        symbol:       str,
        entry_price:  float,
        current_price: float,
        target_price: float,
        stop_loss:    float,
        strategy:     str,
        tier:         str,
        hold_hours:   float,
        indicators:   Dict,
        symbol_history: str = "",   # SignalMemory.get_summary()
    ) -> ExitEvaluation:

        profit_pct  = (current_price - entry_price) / entry_price * 100
        to_target   = (target_price - current_price) / current_price * 100
        to_stop     = (current_price - stop_loss) / current_price * 100
        target_progress = profit_pct / ((target_price - entry_price) / entry_price * 100) * 100

        # 100$ simulation
        sim_current = 100 * (1 + profit_pct / 100)
        sim_profit  = sim_current - 100

        rsi        = indicators.get("rsi", 50)
        macd_hist  = indicators.get("macd_histogram", 0)
        macd_prev  = indicators.get("macd_histogram_prev", 0)
        volume     = indicators.get("volume", 1)
        avg_vol    = indicators.get("avg_volume_20d", 1)
        vol_ratio  = volume / max(avg_vol, 1)

        prompt = f"""You are a professional crypto trader making a HOLD vs TAKE PROFIT decision.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POSITION STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Symbol:    {symbol} [{tier}]
Strategy:  {strategy}
Hold time: {hold_hours:.1f} hours

Entry:   ${entry_price:.4f}
Current: ${current_price:.4f}  ({profit_pct:+.2f}%)
Target:  ${target_price:.4f}  ({to_target:.1f}% away)
Stop:    ${stop_loss:.4f}  ({to_stop:.1f}% below)

Target progress: {target_progress:.0f}%

100$ simulation:
  Current value: ${sim_current:.2f}
  Profit so far: ${sim_profit:+.2f}

{f'Symbol history: {symbol_history}' if symbol_history else ''}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT INDICATORS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RSI:     {rsi:.1f}  {'🔴 overbought' if rsi > 70 else '🟡 high' if rsi > 65 else '🟢 ok'}
MACD:    {macd_hist:.6f} (prev {macd_prev:.6f})  {'🔴 weakening' if macd_hist < macd_prev else '🟢 strengthening'}
Volume:  {vol_ratio:.2f}x average  {'🔴 dropping' if vol_ratio < 0.7 else '🟢 ok'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DECISION CRITERIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOLD_ALL:     RSI < 65, MACD strengthening, target > 5% away, momentum strong
TAKE_PARTIAL: RSI 65-72, MACD weakening OR target < 4% away — lock 50% profit
TAKE_FULL:    RSI > 72 OR MACD turning negative OR target < 2% away

RESPOND IN JSON (Georgian text):
{{
  "advice": "HOLD_ALL" | "TAKE_PARTIAL" | "TAKE_FULL",
  "confidence": <0-100>,
  "partial_pct": <50 or 75>,
  "reasoning": "ქართული ახსნა 1-2 წინადადება",
  "warning": "გაფრთხილება ან ცარიელი სტრიქონი"
}}"""

        try:
            msg = await self.client.messages.create(
                model=self.model,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            text = msg.content[0].text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data   = json.loads(text.strip())
            advice = ExitAdvice[data.get("advice", "HOLD_ALL")]
            partial_pct = float(data.get("partial_pct", 50))

            # Calculate 100$ simulation for partial
            locked_pct  = partial_pct / 100
            locked_val  = sim_current * locked_pct
            remain_val  = sim_current * (1 - locked_pct)

            result = ExitEvaluation(
                advice         = advice,
                reasoning      = data.get("reasoning", ""),
                confidence     = float(data.get("confidence", 60)),
                partial_pct    = partial_pct,
                sim_locked_usd = locked_val - 100 * locked_pct,   # profit from locked portion
                sim_remain_usd = remain_val,
                warning        = data.get("warning", ""),
            )

            logger.info(
                f"🧠 Exit eval {symbol}: {advice.value} | "
                f"Conf={result.confidence:.0f}% | "
                f"Profit so far={profit_pct:+.2f}%"
            )
            return result

        except Exception as e:
            logger.error(f"❌ AIExitEvaluator error {symbol}: {e}")
            # Conservative fallback
            return ExitEvaluation(
                advice    = ExitAdvice.HOLD_ALL,
                reasoning = "AI მიუწვდომელია — hold სტრატეგია",
                confidence = 50,
            )

    def format_telegram_message(
        self,
        symbol:       str,
        profit_pct:   float,
        evaluation:   ExitEvaluation,
        entry_price:  float,
        current_price: float,
    ) -> str:
        """Telegram-ში გასაგზავნი შეტყობინება."""

        sim_current = 100 * (1 + profit_pct / 100)
        sim_profit  = sim_current - 100

        if evaluation.advice == ExitAdvice.HOLD_ALL:
            emoji  = "📈"
            action = "გააგრძელე HOLD"
        elif evaluation.advice == ExitAdvice.TAKE_PARTIAL:
            emoji  = "📊"
            action = f"გამოიტანე {evaluation.partial_pct:.0f}%"
        else:
            emoji  = "💰"
            action = "სრულად გაყიდე"

        msg = (
            f"{emoji} {symbol} — AI Exit შეფასება\n\n"
            f"📈 მიმდინარე: {profit_pct:+.2f}%\n"
            f"💵 ${entry_price:.4f} → ${current_price:.4f}\n\n"
            f"🧠 AI რეკომენდაცია: {action}\n"
            f"📝 {evaluation.reasoning}\n\n"
            f"💰 100$ სიმულაცია:\n"
            f"├─ ახლა: ${sim_current:.2f} (+${sim_profit:.2f})\n"
        )

        if evaluation.advice == ExitAdvice.TAKE_PARTIAL:
            locked_portion = evaluation.partial_pct / 100
            locked_val  = sim_current * locked_portion
            remain_val  = sim_current * (1 - locked_portion)
            msg += (
                f"├─ Lock {evaluation.partial_pct:.0f}%: ${locked_val:.2f}\n"
                f"└─ Hold {100-evaluation.partial_pct:.0f}%: ${remain_val:.2f}\n"
            )
        elif evaluation.advice == ExitAdvice.TAKE_FULL:
            msg += f"└─ გამოიტანე: ${sim_current:.2f}\n"

        if evaluation.warning:
            msg += f"\n⚠️ {evaluation.warning}\n"

        msg += f"\n⚠️ არ არის ფინანსური რჩევა"
        return msg
