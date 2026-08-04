"""Slack bot for AI Developer Growth - knowledge navigation and assessment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SlackMessage:
    text: str
    channel: str
    user: str
    ts: str = ""


class GrowthBot:
    """Slack bot for team learning management."""

    def __init__(self):
        self.commands = {
            "assess": self.cmd_assess,
            "progress": self.cmd_progress,
            "recommend": self.cmd_recommend,
            "help": self.cmd_help,
        }
        self.user_scores: dict[str, dict] = {}
        self.user_progress: dict[str, list[str]] = {}

    def handle_message(self, msg: SlackMessage) -> str | None:
        """Handle an incoming Slack message."""
        text = msg.text.strip()
        if not text.startswith("!growth"):
            return None

        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            return self.cmd_help(msg)

        cmd = parts[1].lower()
        handler = self.commands.get(cmd, self.cmd_help)
        return handler(msg)

    def cmd_assess(self, msg: SlackMessage) -> str:
        """Start a skill assessment."""
        return (
            "📊 *Skill Assessment*\n"
            "Rate yourself on each dimension (0-100):\n"
            "• AI 理解力\n• 工程整合\n• 学习方法\n• 创新思维\n• 输出质量\n\n"
            "Use: `!growth assess ai=70 eng=60 learn=80 innov=50 output=65`"
        )

    def cmd_progress(self, msg: SlackMessage) -> str:
        """Show learning progress."""
        progress = self.user_progress.get(msg.user, [])
        if not progress:
            return "📚 No learning progress yet. Start with `!growth assess`"
        return f"📚 You've completed {len(progress)} documents:\n" + "\n".join(f"• {d}" for d in progress[-5:])

    def cmd_recommend(self, msg: SlackMessage) -> str:
        """Get learning recommendations."""
        scores = self.user_scores.get(msg.user)
        if not scores:
            return "Take an assessment first: `!growth assess`"

        weak = sorted(scores.items(), key=lambda x: x[1])[:2]
        recs = []
        for dim, score in weak:
            recs.append(f"• {dim}: {score}% - Read recommended docs")
        return "🎯 *Recommendations*:\n" + "\n".join(recs)

    def cmd_help(self, msg: SlackMessage) -> str:
        """Show help."""
        return (
            "🌱 *AI Developer Growth Bot*\n\n"
            "Commands:\n"
            "• `!growth assess` - Start skill assessment\n"
            "• `!growth progress` - View learning progress\n"
            "• `!growth recommend` - Get personalized recommendations\n"
            "• `!growth help` - Show this help"
        )


def create_bot() -> GrowthBot:
    """Factory function."""
    return GrowthBot()
