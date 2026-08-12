"""Tests for the Slack bot."""

from bot import GrowthBot, SlackMessage, create_bot


def test_create_bot():
    bot = create_bot()
    assert isinstance(bot, GrowthBot)


def test_help_command():
    bot = create_bot()
    msg = SlackMessage(text="!growth help", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "AI Developer Growth" in resp


def test_assess_without_scores():
    bot = create_bot()
    msg = SlackMessage(text="!growth assess", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "Skill Assessment" in resp
    assert "ai=70" in resp


def test_assess_with_scores():
    bot = create_bot()
    msg = SlackMessage(text="!growth assess ai=70 eng=60 learn=80", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "Overall" in resp
    assert "AI 理解力" in resp
    assert bot.user_scores["U123"]["AI 理解力"] == 70
    assert bot.user_scores["U123"]["学习方法"] == 80


def test_assess_invalid_score_clamped():
    bot = create_bot()
    msg = SlackMessage(text="!growth assess ai=150", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    # 超过 100 的分数无效，应回退到帮助提示且不保存分数
    assert "Skill Assessment" in resp
    assert bot.user_scores.get("U123") is None


def test_recommend_without_assessment():
    bot = create_bot()
    msg = SlackMessage(text="!growth recommend", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "assessment first" in resp


def test_recommend_with_assessment():
    bot = create_bot()
    bot.user_scores["U123"] = {"AI 理解力": 80, "工程整合": 30, "学习方法": 60}
    msg = SlackMessage(text="!growth recommend", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "Recommendations" in resp
    # 最弱维度应出现在推荐中
    assert "工程整合" in resp


def test_leaderboard_empty():
    bot = create_bot()
    msg = SlackMessage(text="!growth leaderboard", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "No assessments" in resp


def test_leaderboard_with_scores():
    bot = create_bot()
    bot.user_scores["U1"] = {"AI 理解力": 90, "工程整合": 80}
    bot.user_scores["U2"] = {"AI 理解力": 50, "工程整合": 40}
    msg = SlackMessage(text="!growth leaderboard", channel="#test", user="U3")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "Team Leaderboard" in resp
    assert "U1" in resp
    assert resp.index("U1") < resp.index("U2")


def test_progress_empty():
    bot = create_bot()
    msg = SlackMessage(text="!growth progress", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "No learning progress" in resp


def test_progress_with_documents():
    bot = create_bot()
    bot.user_progress["U123"] = ["docs/a.md", "docs/b.md"]
    msg = SlackMessage(text="!growth progress", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "2 documents" in resp


def test_non_growth_message():
    bot = create_bot()
    msg = SlackMessage(text="hello there", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is None


def test_empty_command():
    bot = create_bot()
    msg = SlackMessage(text="!growth", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "help" in resp.lower() or "Commands" in resp


def test_unknown_command_falls_back_to_help():
    bot = create_bot()
    msg = SlackMessage(text="!growth unknown", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "Commands" in resp


def test_level_boundaries():
    bot = create_bot()
    assert bot._level_for(19)[2] == "L0 - 观察者"
    assert bot._level_for(20)[2] == "L1 - 尝试者"
    assert bot._level_for(59)[2] == "L2 - 实践者"
    assert bot._level_for(60)[2] == "L3 - 专家"
    assert bot._level_for(100)[2] == "L4 - 架构师"
