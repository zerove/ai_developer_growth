"""Tests for error types."""

import unittest

from errors import (
    AgentError,
    AgentFailureError,
    AgentTimeoutError,
    MalformedResponseError,
    MaxIterationsError,
)


class TestAgentError(unittest.TestCase):
    """Tests for the base AgentError."""

    def test_basic_message(self) -> None:
        err = AgentError("something broke")
        self.assertEqual(str(err), "something broke")
        self.assertIsNone(err.agent_role)
        self.assertIsNone(err.cause)

    def test_with_role(self) -> None:
        err = AgentError("fail", agent_role="PM")
        self.assertEqual(err.agent_role, "PM")

    def test_with_cause(self) -> None:
        original = ValueError("bad value")
        err = AgentError("wrapped", cause=original)
        self.assertIs(err.cause, original)

    def test_is_exception(self) -> None:
        err = AgentError("test")
        self.assertIsInstance(err, Exception)


class TestAgentTimeoutError(unittest.TestCase):
    def test_inheritance(self) -> None:
        err = AgentTimeoutError("timed out")
        self.assertIsInstance(err, AgentError)

    def test_with_role(self) -> None:
        err = AgentTimeoutError("timed out", agent_role="Coder")
        self.assertEqual(err.agent_role, "Coder")


class TestAgentFailureError(unittest.TestCase):
    def test_inheritance(self) -> None:
        err = AgentFailureError("crashed")
        self.assertIsInstance(err, AgentError)

    def test_with_cause(self) -> None:
        orig = RuntimeError("oops")
        err = AgentFailureError("agent crashed", cause=orig)
        self.assertIs(err.cause, orig)


class TestMaxIterationsError(unittest.TestCase):
    def test_iterations_count(self) -> None:
        err = MaxIterationsError("too many", iterations=5)
        self.assertEqual(err.iterations, 5)

    def test_inheritance(self) -> None:
        err = MaxIterationsError("maxed")
        self.assertIsInstance(err, AgentError)
        self.assertEqual(err.iterations, 0)


class TestMalformedResponseError(unittest.TestCase):
    def test_raw_output(self) -> None:
        err = MalformedResponseError("can't parse", raw_output="garbage")
        self.assertEqual(err.raw_output, "garbage")

    def test_inheritance(self) -> None:
        err = MalformedResponseError("bad")
        self.assertIsInstance(err, AgentError)


if __name__ == "__main__":
    unittest.main()
