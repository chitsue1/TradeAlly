"""
═══════════════════════════════════════════════════════════════════════════════
SELL SIGNAL MESSAGE GENERATOR - PRODUCTION v1.0
═══════════════════════════════════════════════════════════════════════════════

✅ დეტალური გაყიდვის რეპორტი:
- Entry vs Exit analysis
- Profit/Loss დაბრკოლებით
- 100$ სიმულაცია (თან პროცენტი)
- Expectation analysis
- Maximum profit during hold
- Performance verdict

AUTHOR: Trading System Architecture Team
DATE: 2024-02-14
"""

from exit_signals_handler import ExitAnalysis, ExitReason

class SellSignalMessageGenerator:
    """
    SELL SIGNAL MESSAGE GENERATOR

    ✅ პროფესიონალური დაბრკოლებული რეპორტი
    """

    @staticmethod
    def generate_sell_message(
        symbol: str,
        exit_analysis: ExitAnalysis,
        market_context: str = ""
    ) -> str:
        """
        SELL signal message (Telegram format)

        ფოკუსირებული:
        1. რა მოხდა (Target/Stop/Timeout)?
        2. რა იქნებოდა 100$ დაინვესტირებული?
        3. რა იყო მოსალოდნელი?
        4. რა დაიკარგა (max profit)?
        5. მოგება/ზარალი?
        """

        # ════════════════════════════════════════════════════════════════════
        # 1. HEADER
        # ════════════════════════════════════════════════════════════════════

        exit_reason_emoji = {
            ExitReason.TARGET_HIT: "🎯",
            ExitReason.STOP_LOSS: "🛑",
            ExitReason.TIMEOUT: "⏰",
            ExitReason.MANUAL: "✋",
            ExitReason.PARTIAL_EXIT: "📊"
        }

        exit_reason_text = {
            ExitReason.TARGET_HIT: "სამიზნე მიღწეულია",
            ExitReason.STOP_LOSS: "ზარალი ჩაჩეკა",
            ExitReason.TIMEOUT: "დრო გასული",
            ExitReason.MANUAL: "ხელით დახურვა",
            ExitReason.PARTIAL_EXIT: "ნაწილობრივი გასვლა"
        }

        emoji = exit_reason_emoji.get(exit_analysis.exit_reason, "📊")
        reason_text = exit_reason_text.get(exit_analysis.exit_reason, "გაყიდვა")

        msg = f"{emoji} **{reason_text.upper()}** | {symbol}\n"
        msg += "═" * 50 + "\n\n"

        # ════════════════════════════════════════════════════════════════════
        # 2. PRICE ACTION
        # ════════════════════════════════════════════════════════════════════

        msg += "**💰 ფასის მოძრაობა:**\n"
        msg += f"🔵 შესვლა:  ${exit_analysis.entry_price:.4f}\n"

        if exit_analysis.exit_reason == ExitReason.TARGET_HIT:
            msg += f"🟢 გასვლა:  ${exit_analysis.exit_price:.4f}\n"
        elif exit_analysis.exit_reason == ExitReason.STOP_LOSS:
            msg += f"🔴 გასვლა:  ${exit_analysis.exit_price:.4f}\n"
        else:
            msg += f"🟡 გასვლა:  ${exit_analysis.exit_price:.4f}\n"

        msg += "\n"

        # ════════════════════════════════════════════════════════════════════
        # 3. PROFIT/LOSS (მთავარი)
        # ════════════════════════════════════════════════════════════════════

        profit_emoji = "📈" if exit_analysis.profit_pct > 0 else "📉"

        msg += f"**{profit_emoji} პროფიტი/დანაკარგი:**\n"
        msg += f"📊 პროცენტი:  {exit_analysis.profit_pct:+.2f}%\n"
        msg += f"💵 თანხა:     ${exit_analysis.profit_usd:+.2f}\n"
        msg += "\n"

        # ════════════════════════════════════════════════════════════════════
        # 4. 100$ SIMULATION (ძალიან მნიშვნელოვანი!)
        # ════════════════════════════════════════════════════════════════════

        msg += "**💯 თუ 100$ ინვესტიცია გაკეთებული იქნებოდა:**\n"
        msg += f"💰 საწყისი:    ${exit_analysis.initial_investment:.2f}\n"
        msg += f"💰 საბოლოო:    ${exit_analysis.final_value:.2f}\n"

        if exit_analysis.simulated_profit_usd >= 0:
            msg += f"✅ მოგება:     ${exit_analysis.simulated_profit_usd:+.2f} "
            msg += f"({exit_analysis.simulated_profit_pct:+.2f}%)\n"
        else:
            msg += f"❌ დანაკარგი:  ${exit_analysis.simulated_profit_usd:+.2f} "
            msg += f"({exit_analysis.simulated_profit_pct:+.2f}%)\n"

        msg += "\n"

        # ════════════════════════════════════════════════════════════════════
        # 5. EXPECTATION ANALYSIS
        # ════════════════════════════════════════════════════════════════════

        msg += "**🎯 პროგნოზი vs რეალობა:**\n"
        msg += f"📌 მოსალოდნელი:  {exit_analysis.expected_profit_min:.1f}% - "
        msg += f"{exit_analysis.expected_profit_max:.1f}%\n"
        msg += f"📊 რეალური:     {exit_analysis.profit_pct:.2f}%\n"

        if exit_analysis.expectation_met:
            msg += "✅ **პროგნოზი სწორი იყო!**\n"
        elif exit_analysis.realistic_target_met:
            msg += "🟡 **ნაწილობრივ სწორი**\n"
        else:
            msg += "❌ **პროგნოზი არასწორი იყო**\n"

        msg += "\n"

        # ════════════════════════════════════════════════════════════════════
        # 6. MAX PROFIT DURING HOLD
        # ════════════════════════════════════════════════════════════════════

        msg += "**📈 მაქსიმალური მოგება დაკავებისას:**\n"
        msg += f"🔝 ჯამი:       {exit_analysis.max_profit_pct_during_hold:+.2f}%\n"
        msg += f"💵 თანხა:      ${exit_analysis.max_profit_during_hold:+.2f}\n"

        # რა დაიკარგა?
        left_on_table = exit_analysis.max_profit_pct_during_hold - exit_analysis.profit_pct
        if left_on_table > 0.5:
            msg += f"⚠️ დაკარგული:  {left_on_table:.2f}% (ძალიან მაქვს!)\n"
        elif left_on_table > 0:
            msg += f"⚠️ დაკარგული:  {left_on_table:.2f}%\n"

        msg += "\n"

        # ════════════════════════════════════════════════════════════════════
        # 7. HOLD DURATION
        # ════════════════════════════════════════════════════════════════════

        msg += "**⏱️ დაკავების ხანგრძლივობა:**\n"
        msg += f"⏳ დრო:        {exit_analysis.hold_duration_human}\n"
        msg += f"📊 საათები:    {exit_analysis.hold_duration_hours:.1f}h\n"
        msg += "\n"

        # ════════════════════════════════════════════════════════════════════
        # 8. SIGNAL QUALITY
        # ════════════════════════════════════════════════════════════════════

        msg += "**🔬 სიგნალის ხარისხი:**\n"
        msg += f"🧠 ნდობა:      {exit_analysis.signal_confidence:.0f}%\n"
        msg += f"🤖 AI:        {'✅ დამტკიცებული' if exit_analysis.ai_approved else '❌ რჩენილი'}\n"

        # გამოწერილი/მოუწერელი
        if exit_analysis.expectation_met:
            verdict = "⭐ **სიგნალი ტყუილი აღმოჩნდა!**"
        elif exit_analysis.realistic_target_met:
            verdict = "👍 **მისაღები ხარისხი**"
        else:
            verdict = "⚠️ **ხარი საჭირო მონიტორინგი**"

        msg += verdict + "\n\n"

        # ════════════════════════════════════════════════════════════════════
        # 9. FINAL SUMMARY
        # ════════════════════════════════════════════════════════════════════

        msg += "═" * 50 + "\n"

        if exit_analysis.profit_pct > 0:
            msg += f"✅ **დაკეტებული მოგებით: {exit_analysis.profit_pct:+.2f}%**\n"
        else:
            msg += f"❌ **დაკეტებული ზარალით: {exit_analysis.profit_pct:+.2f}%**\n"

        msg += f"💡 შემდეგი ტრეიდი უფრო ზუსტი იქნება 🚀\n"

        return msg

    @staticmethod
    def generate_brief_sell_message(
        symbol: str,
        exit_analysis: ExitAnalysis
    ) -> str:
        """
        მოკლე ვერსია (მსუბუქი)
        """

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
        """
        დახურული positions-ების summary
        """

        if not exit_history:
            return "📭 **არ არის დახურული positions**"

        msg = "📊 **TRADES SUMMARY:**\n\n"

        total_profit = 0
        wins = 0
        losses = 0

        for trade in exit_history[-10:]:  # ბოლო 10
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