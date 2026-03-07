"""
═══════════════════════════════════════════════════════════════════════════════
SELL SIGNAL MESSAGE GENERATOR - v2.0
═══════════════════════════════════════════════════════════════════════════════

CHANGES v2.0:
  - WIN message: გრანდიოზული ფორმატი, 🎉 სახელოსნო, მოგება პირველ ადგილზე
  - LOSS with intra-hold profit: ✅ "მაინც მომგებიანი მომენტი" შეტყობინება
  - "პროგნოზი სწორი" — ახლა ჩანს მხოლოდ მაშინ როცა ბოტი გამოიტანა sell profit-ით
    (ადრე ეწერა "პროგნოზი არასწორი" მაშინ კი სიგნალი მომგებიანი იყო)
  - max_profit section: ყიდვა-გაყიდვის შუალედის პიკი ყოველთვის ჩანს
"""

from exit_signals_handler import ExitAnalysis, ExitReason


class SellSignalMessageGenerator:

    @staticmethod
    def generate_sell_message(
        symbol: str,
        exit_analysis: ExitAnalysis,
        market_context: str = ""
    ) -> str:
        """
        Sell signal — ორი სცენარი:
          A) profit_pct > 0  →  გრანდიოზული WIN ბლოკი
          B) profit_pct <= 0 →  ზარალი, მაგრამ max_profit ჩანს თუ > 0
        """

        is_win = exit_analysis.profit_pct > 0

        # ════════════════════════════════════════════════════════════════════
        # EXIT REASON LABELS
        # ════════════════════════════════════════════════════════════════════
        exit_reason_emoji = {
            ExitReason.TARGET_HIT:    "🎯",
            ExitReason.STOP_LOSS:     "🛑",
            ExitReason.TIMEOUT:       "⏰",
            ExitReason.MANUAL:        "✋",
            ExitReason.PARTIAL_EXIT:  "📊",
            ExitReason.TRAILING_STOP: "🔒",
        }
        exit_reason_text = {
            ExitReason.TARGET_HIT:    "სამიზნე მიღწეულია",
            ExitReason.STOP_LOSS:     "ზარალი ჩაჩეკა",
            ExitReason.TIMEOUT:       "დრო გასული",
            ExitReason.MANUAL:        "ხელით დახურვა",
            ExitReason.PARTIAL_EXIT:  "ნაწილობრივი გასვლა",
            ExitReason.TRAILING_STOP: "Trailing Stop",
        }
        emoji       = exit_reason_emoji.get(exit_analysis.exit_reason, "📊")
        reason_text = exit_reason_text.get(exit_analysis.exit_reason, "გაყიდვა")

        if is_win:
            return SellSignalMessageGenerator._win_message(
                symbol, exit_analysis, emoji, reason_text
            )
        else:
            return SellSignalMessageGenerator._loss_message(
                symbol, exit_analysis, emoji, reason_text
            )

    # ════════════════════════════════════════════════════════════════════════
    # WIN MESSAGE — გრანდიოზული
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _win_message(symbol, ea: ExitAnalysis, emoji: str, reason_text: str) -> str:
        msg = f"🎉🟢 **დაკეტებული მოგებით: {ea.profit_pct:+.2f}%** 🟢🎉\n"
        msg += f"💡 შემდეგი ტრეიდი უფრო ზუსტი იქნება 🚀\n"
        msg += "═" * 50 + "\n\n"

        # HEADER
        msg += f"{emoji} **{reason_text.upper()}** | {symbol}\n\n"

        # ── ფასი ──────────────────────────────────────────────
        msg += "**💰 ფასის მოძრაობა:**\n"
        msg += f"🔵 შესვლა:  ${ea.entry_price:.4f}\n"
        msg += f"🟢 გასვლა:  ${ea.exit_price:.4f}\n\n"

        # ── მოგება (მთავარი — დიდი ბლოკი) ───────────────────
        msg += "**📈 მოგება:**\n"
        msg += f"📊 პროცენტი:  **{ea.profit_pct:+.2f}%**\n"
        msg += f"💵 $100 → **${ea.final_value:.2f}**  (${ea.simulated_profit_usd:+.2f})\n\n"

        # ── მაქს მოგება ──────────────────────────────────────
        msg += "**📈 მაქსიმალური მოგება ყიდვა→გაყიდვა შუალედში:**\n"
        msg += f"🔝 {ea.max_profit_pct_during_hold:+.2f}%\n"

        left_on_table = ea.max_profit_pct_during_hold - ea.profit_pct
        if left_on_table > 0.5:
            msg += f"⚠️ სხვაობა:   {left_on_table:.2f}% (პიკზე ადრე გავედი)\n"
        msg += "\n"

        # ── ✅ სიგნალი სწორი იყო (ბოტმა sell გამოიტანა მოგებით) ──
        msg += "**🎯 პროგნოზი vs რეალობა:**\n"
        msg += f"📌 მოსალოდნელი:  {ea.expected_profit_min:.1f}% - {ea.expected_profit_max:.1f}%\n"
        msg += f"📊 რეალური:     {ea.profit_pct:.2f}%\n"
        # ✅ ბოტი გამოიტანა sell მოგებით → სიგნალი ყოველთვის სწორი
        msg += "✅ **სიგნალი სწორი იყო!**\n\n"

        # ── ხანგრძლივობა + ნდობა ─────────────────────────────
        msg += f"⏱️ ვაჭრობის დრო: {ea.hold_duration_human}\n"
        msg += f"🧠 ნდობა: {ea.signal_confidence:.0f}%\n"

        return msg

    # ════════════════════════════════════════════════════════════════════════
    # LOSS MESSAGE — ზარალი, მაგრამ max_profit ყოველთვის ჩანს
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _loss_message(symbol, ea: ExitAnalysis, emoji: str, reason_text: str) -> str:
        msg = "═" * 50 + "\n"
        msg += f"{emoji} **{reason_text.upper()}** | {symbol}\n"
        msg += "═" * 50 + "\n\n"

        # ── ფასი ──────────────────────────────────────────────
        msg += "**💰 ფასის მოძრაობა:**\n"
        msg += f"🔵 შესვლა:  ${ea.entry_price:.4f}\n"
        msg += f"🔴 გასვლა:  ${ea.exit_price:.4f}\n\n"

        # ── ზარალი ───────────────────────────────────────────
        msg += "**📉 ზარალი:**\n"
        msg += f"📊 პროცენტი:  {ea.profit_pct:+.2f}%\n"
        msg += f"💵 $100 → ${ea.final_value:.2f}  (${ea.simulated_profit_usd:+.2f})\n\n"

        # ── მაქს მოგება hold-ში ── (ყოველთვის ჩანს!)
        msg += "**📈 მაქსიმალური მოგება ყიდვა→გაყიდვა შუალედში:**\n"
        msg += f"🔝 {ea.max_profit_pct_during_hold:+.2f}%\n"

        # თუ hold-ში მოგება ჰქონდა მაგრამ დახურდა ზარალით
        if ea.max_profit_pct_during_hold > 1.0:
            msg += f"💡 სიგნალის პერიოდში **+{ea.max_profit_pct_during_hold:.2f}%** შეიძლებოდა\n"
        msg += "\n"

        # ── პროგნოზი vs რეალობა ───────────────────────────────
        msg += "**🎯 პროგნოზი vs რეალობა:**\n"
        msg += f"📌 მოსალოდნელი:  {ea.expected_profit_min:.1f}% - {ea.expected_profit_max:.1f}%\n"
        msg += f"📊 რეალური:     {ea.profit_pct:.2f}%\n"
        # ✅ ზარალის დროს ვწერთ "ნაწილობრივ" თუ max_profit ჰქონდა, სხვა შემთხვევაში — ❌
        if ea.max_profit_pct_during_hold >= ea.expected_profit_min:
            msg += "🟡 **ნაწილობრივ სწორი (სიგნალი მომგებიანი მომენტი ჰქონდა)**\n\n"
        else:
            msg += "❌ **პროგნოზი ვერ სრულდება**\n\n"

        # ── ხანგრძლივობა + ნდობა ─────────────────────────────
        msg += f"⏱️ ვაჭრობის დრო: {ea.hold_duration_human}\n"
        msg += f"🧠 ნდობა: {ea.signal_confidence:.0f}%\n\n"

        msg += "═" * 50 + "\n"
        msg += f"❌ **დაკეტებული ზარალით: {ea.profit_pct:+.2f}%**\n"
        msg += "💡 შემდეგი ტრეიდი უფრო ზუსტი იქნება 🚀\n"

        return msg

    # ════════════════════════════════════════════════════════════════════════
    # BRIEF (unchanged)
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    def generate_brief_sell_message(symbol: str, exit_analysis: ExitAnalysis) -> str:
        emoji = "🎯" if exit_analysis.exit_reason == ExitReason.TARGET_HIT else "🛑"
        msg = f"{emoji} **გაყიდვა** | {symbol}\n\n"
        msg += f"Entry:  ${exit_analysis.entry_price:.4f}\n"
        msg += f"Exit:   ${exit_analysis.exit_price:.4f}\n"
        msg += f"P&L:    {exit_analysis.profit_pct:+.2f}% (${exit_analysis.profit_usd:+.2f})\n\n"
        msg += f"100$:   ${exit_analysis.simulated_profit_usd:+.2f} "
        msg += f"({exit_analysis.simulated_profit_pct:+.2f}%)\n"
        msg += f"Hold:   {exit_analysis.hold_duration_human}\n"
        return msg

    @staticmethod
    def generate_position_summary(exit_history: list) -> str:
        if not exit_history:
            return "📭 **არ არის დახურული positions**"

        msg = "📊 **TRADES SUMMARY:**\n\n"
        total_profit = 0
        wins = 0
        losses = 0

        for trade in exit_history[-10:]:
            profit_pct = trade['profit_pct']
            total_profit += profit_pct
            if profit_pct > 0:
                wins += 1
                emoji = "✅"
            else:
                losses += 1
                emoji = "❌"
            msg += f"{emoji} {trade['symbol']} - {profit_pct:+.2f}%\n"

        msg += f"\n📈 **სულ:** {wins}/{len(exit_history[-10:])} win rate\n"
        msg += f"💰 **საშუალო:** {total_profit / len(exit_history[-10:]):+.2f}%\n"
        return msg