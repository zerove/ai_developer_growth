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


def test_assess_command():
    bot = create_bot()
    msg = SlackMessage(text="!growth assess", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "Skill Assessment" in resp


def test_progress_empty():
    bot = create_bot()
    msg = SlackMessage(text="!growth progress", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "No learning progress" in resp


def test_recommend_without_assessment():
    bot = create_bot()
    msg = SlackMessage(text="!growth recommend", channel="#test", user="U123")
    resp = bot.handle_message(msg)
    assert resp is not None
    assert "assessment first" in resp


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
