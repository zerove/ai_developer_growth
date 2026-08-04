"""Tests for protocol types (Message, AgentResponse, Agent protocol)."""

import unittest

from protocol import Agent, AgentResponse, Message, MessageRole


class TestMessage(unittest.TestCase):
    """Tests for the Message dataclass."""

    def test_basic_creation(self) -> None:
        msg = Message(role=MessageRole.PM, content="Hello")
        self.assertEqual(msg.role, MessageRole.PM)
        self.assertEqual(msg.content, "Hello")
        self.assertEqual(msg.metadata, {})

    def test_with_metadata(self) -> None:
        msg = Message(
            role=MessageRole.CODER,
            content="code here",
            metadata={"stage": "code"},
        )
        self.assertEqual(msg.metadata["stage"], "code")

    def test_frozen(self) -> None:
        msg = Message(role=MessageRole.PM, content="test")
        with self.assertRaises(AttributeError):
            msg.content = "changed"  # type: ignore[misc]

    def test_role_enum_values(self) -> None:
        self.assertEqual(MessageRole.USER.value, "user")
        self.assertEqual(MessageRole.PM.value, "PM")
        self.assertEqual(MessageRole.ARCHITECT.value, "Architect")
        self.assertEqual(MessageRole.CODER.value, "Coder")
        self.assertEqual(MessageRole.REVIEWER.value, "Reviewer")


class TestAgentResponse(unittest.TestCase):
    """Tests for the AgentResponse dataclass."""

    def test_basic_response(self) -> None:
        resp = AgentResponse(text="output")
        self.assertEqual(resp.text, "output")
        self.assertFalse(resp.passed)
        self.assertEqual(resp.metadata, {})

    def test_passing_response(self) -> None:
        resp = AgentResponse(text="PASS: looks good", passed=True)
        self.assertTrue(resp.passed)

    def test_with_metadata(self) -> None:
        resp = AgentResponse(
            text="code here",
            metadata={"stage": "code"},
        )
        self.assertEqual(resp.metadata["stage"], "code")


class TestAgentProtocol(unittest.TestCase):
    """Tests that objects satisfying the Agent protocol are recognized."""

    def test_satisfies_protocol(self) -> None:
        class FakeAgent:
            @property
            def role(self) -> MessageRole:
                return MessageRole.PM

            def run(self, history: list[Message]) -> AgentResponse:
                return AgentResponse(text="response")

        agent = FakeAgent()
        self.assertIsInstance(agent, Agent)

    def test_fails_protocol_without_role(self) -> None:
        class NoRole:
            def run(self, history: list[Message]) -> AgentResponse:
                return AgentResponse(text="response")

        self.assertNotIsInstance(NoRole(), Agent)

    def test_fails_protocol_without_run(self) -> None:
        class NoRun:
            @property
            def role(self) -> MessageRole:
                return MessageRole.PM

        self.assertNotIsInstance(NoRun(), Agent)


if __name__ == "__main__":
    unittest.main()
