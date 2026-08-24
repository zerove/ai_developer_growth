"""Slack bot for AI Developer Growth - knowledge navigation and assessment."""

from __future__ import annotations

import re
from dataclasses import dataclass

DIMENSION_KEYS = {
    "ai": "AI 理解力",
    "eng": "工程整合",
    "learn": "学习方法",
    "innov": "创新思维",
    "output": "输出质量",
}

LEVELS = [
    (0, 19, "L0 - 观察者", "刚开始接触 AI 工具，主要观望"),
    (20, 39, "L1 - 尝试者", "能用 AI 完成简单任务，但缺乏系统方法"),
    (40, 59, "L2 - 实践者", "熟练使用 AI 协作开发，有固定工作流"),
    (60, 79, "L3 - 专家", "深度整合 AI 到全周期，能指导团队采用"),
    (80, 100, "L4 - 架构师", "定义 AI 协作范式，构建组织级 AI 能力体系"),
]


@dataclass
class SlackMessage:
    text: str
    channel: str
    user: str
    ts: str = ""


class GrowthBot:
    """Slack bot for team learning management."""

    def __init__(self) -> None:
        self.commands = {
            "assess": self.cmd_assess,
            "progress": self.cmd_progress,
            "recommend": self.cmd_recommend,
            "leaderboard": self.cmd_leaderboard,
            "help": self.cmd_help,
        }
        self.user_scores: dict[str, dict[str, int]] = {}
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

    def _parse_scores(self, text: str) -> dict[str, int]:
        """Parse score arguments like ai=70 eng=60 learn=80."""
        scores: dict[str, int] = {}
        for key, name in DIMENSION_KEYS.items():
            match = re.search(rf"{key}=(\d+)", text)
            if match:
                value = int(match.group(1))
                if 0 <= value <= 100:
                    scores[name] = value
        return scores

    @staticmethod
    def _level_for(overall: int) -> tuple[int, int, str, str]:
        """Get level info for an overall score."""
        for level in LEVELS:
            if level[0] <= overall <= level[1]:
                return level
        return LEVELS[0]

    def cmd_assess(self, msg: SlackMessage) -> str:
        """Start a skill assessment (supports scores)."""
        scores = self._parse_scores(msg.text)
        if not scores:
            return (
                "📊 *Skill Assessment*\n"
                "Rate yourself on each dimension (0-100):\n"
                "• AI 理解力 (ai)\n• 工程整合 (eng)\n• 学习方法 (learn)\n"
                "• 创新思维 (innov)\n• 输出质量 (output)\n\n"
                "Use: `!growth assess ai=70 eng=60 learn=80 innov=50 output=65`"
            )

        self.user_scores[msg.user] = scores
        overall = round(sum(scores.values()) / len(scores))
        level = self._level_for(overall)

        lines = ["📊 *Assessment Result*"]
        for name, score in scores.items():
            bar = "█" * (score // 10) + "░" * (10 - score // 10)
            lines.append(f"• {name}: {score} {bar}")
        lines.append(f"\n*Overall: {overall}%* → {level[2]}")
        lines.append(f"_{level[3]}_")
        return "\n".join(lines)

    def cmd_progress(self, msg: SlackMessage) -> str:
        """Show learning progress."""
        progress = self.user_progress.get(msg.user, [])
        if not progress:
            return "📚 No learning progress yet. Start with `!growth assess`"
        return f"📚 You've completed {len(progress)} documents:\n" + "\n".join(f"• {d}" for d in progress[-5:])

    def cmd_recommend(self, msg: SlackMessage) -> str:
        """Get learning recommendations based on actual scores."""
        scores = self.user_scores.get(msg.user)
        if not scores:
            return "Take an assessment first: `!growth assess ai=70 eng=60`"

        weak = sorted(scores.items(), key=lambda x: x[1])[:2]
        recs = []
        for name, score in weak:
            if score < 40:
                recs.append(f"• *{name}* ({score}%) - 建议从基础文档开始，先掌握核心概念")
            elif score < 70:
                recs.append(f"• *{name}* ({score}%) - 建议通过实践项目强化，参考案例库")
            else:
                recs.append(f"• *{name}* ({score}%) - 建议进阶学习，尝试指导他人")
        return "🎯 *Recommendations*:\n" + "\n".join(recs)

    def cmd_leaderboard(self, msg: SlackMessage) -> str:
        """Show team leaderboard."""
        if not self.user_scores:
            return "🏆 No assessments yet. Be the first with `!growth assess ai=70`"

        ranked = sorted(
            self.user_scores.items(),
            key=lambda kv: sum(kv[1].values()) / len(kv[1]),
            reverse=True,
        )
        lines = ["🏆 *Team Leaderboard*"]
        for i, (user, scores) in enumerate(ranked[:5], 1):
            avg = round(sum(scores.values()) / len(scores))
            level = self._level_for(avg)
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
            lines.append(f"{medal} <@{user}> - {avg}% ({level[2]})")
        return "\n".join(lines)

    def cmd_help(self, msg: SlackMessage) -> str:
        """Show help."""
        return (
            "🌱 *AI Developer Growth Bot*\n\n"
            "Commands:\n"
            "• `!growth assess ai=70 eng=60` - Skill assessment with scores\n"
            "• `!growth progress` - View learning progress\n"
            "• `!growth recommend` - Personalized recommendations\n"
            "• `!growth leaderboard` - Team leaderboard\n"
            "• `!growth help` - Show this help"
        )


def create_bot() -> GrowthBot:
    """Factory function."""
    return GrowthBot()
