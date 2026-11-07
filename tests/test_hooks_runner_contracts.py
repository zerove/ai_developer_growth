"""hooks_runner CLI 分发契约测试（Phase 2 可维护性）。

覆盖高价值边界：命令注册、默认 typecheck 走对齐口径别名、
doctor/baseline/ci-heartbeat 分发、以及 fail-open 防护行为。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.scripts.hooks_runner import _SIMPLE_COMMANDS, _build_handlers, _dispatch, main
from tools.scripts.secret_scanner import SecretScanResult


class TestDispatchContracts(unittest.TestCase):
    """核心分发契约：保持 monkeypatch/别名语义稳定。"""

    def test_simple_commands_use_expected_aliases(self) -> None:
        self.assertEqual(
            _SIMPLE_COMMANDS,
            {
                "lint": "run_lint",
                "format": "run_format_check",
                "typecheck": "run_typecheck",
                "test": "run_tests",
                "security": "run_security",
            },
        )

    def test_handlers_register_key_commands(self) -> None:
        handlers = _build_handlers()
        for cmd in ("doctor", "ci-heartbeat", "baseline", "secret-scan", "quality-gate-new"):
            self.assertIn(cmd, handlers, f"缺少 handler: {cmd}")

    def test_typecheck_dispatch_uses_run_typecheck_alias(self) -> None:
        """默认 typecheck 必须走 run_typecheck 别名（对齐 CI/hook 口径由该实现保证）。"""

        with patch("sys.argv", ["hooks_runner.py", "typecheck"]):
            with patch("tools.scripts.hooks_runner.run_typecheck", return_value=(True, "ok")) as mock:
                result = main()
        self.assertEqual(result, 0)
        mock.assert_called_once_with()

    def test_lint_fix_passes_fix_flag(self) -> None:

        with patch("sys.argv", ["hooks_runner.py", "lint", "--fix"]):
            with patch("tools.scripts.hooks_runner.run_lint", return_value=(True, "ok")) as mock:
                result = main()
        self.assertEqual(result, 0)
        mock.assert_called_once()
        self.assertTrue(mock.call_args.kwargs.get("fix") or mock.call_args[1].get("fix"))

    def test_unknown_command_returns_1(self) -> None:
        args = MagicMock()
        args.command = "definitely-not-a-command"
        args.lang = None
        args.incremental = False
        self.assertEqual(_dispatch(args), 1)


class TestFailClosedContracts(unittest.TestCase):
    """失败必须可见：防止扫描/门禁 fail-open。"""

    @patch("tools.scripts.hooks_runner.scan_secrets")
    def test_secret_scan_fails_when_no_tools_available(self, mock_scan: MagicMock) -> None:

        mock_scan.return_value = SecretScanResult(
            findings=[],
            tools_used=[],
            errors=["no scanner"],
            scan_duration_ms=1,
        )
        with patch("sys.argv", ["hooks_runner.py", "secret-scan", "--path", "."]):
            result = main()
        self.assertEqual(result, 1, "无可用扫描工具时不得返回成功（fail-open）")

    @patch("tools.scripts.hooks_runner.scan_secrets")
    def test_secret_scan_passes_when_clean_and_tool_ran(self, mock_scan: MagicMock) -> None:

        mock_scan.return_value = SecretScanResult(
            findings=[],
            tools_used=["builtin"],
            errors=[],
            scan_duration_ms=1,
        )
        with patch("sys.argv", ["hooks_runner.py", "secret-scan", "--path", "."]):
            result = main()
        self.assertEqual(result, 0)

    @patch("tools.scripts.hooks.domain_checks.validate_baseline_structure")
    def test_baseline_validate_propagates_failure(self, mock_validate: MagicMock) -> None:

        mock_validate.return_value = (False, "broken")
        with patch("sys.argv", ["hooks_runner.py", "baseline", "validate"]):
            result = main()
        self.assertEqual(result, 1)


class TestCliSmoke(unittest.TestCase):
    """端到端轻量烟雾：解析器与 handler 接线。"""

    @patch("tools.scripts.hooks_runner._handle_doctor", return_value=0)
    def test_doctor_dispatches(self, mock_doctor: MagicMock) -> None:

        with patch("sys.argv", ["hooks_runner.py", "doctor"]):
            result = main()
        self.assertEqual(result, 0)
        mock_doctor.assert_called_once()

    @patch("tools.scripts.hooks_runner._handle_ci_heartbeat", return_value=0)
    def test_ci_heartbeat_dispatches(self, mock_hb: MagicMock) -> None:

        with patch("sys.argv", ["hooks_runner.py", "ci-heartbeat"]):
            result = main()
        self.assertEqual(result, 0)
        mock_hb.assert_called_once()


if __name__ == "__main__":
    unittest.main()
