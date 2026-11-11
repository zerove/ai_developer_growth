"""A-01: adg CLI parser 工厂与 handler 解析契约测试。"""

from __future__ import annotations

import unittest

from tools.scripts.adg_cli.commands import get_command_handler
from tools.scripts.adg_cli.parser import _COMMAND_BUILDERS, _build_parser


class TestAdgCliParserFactory(unittest.TestCase):
    """CLI 子命令装配必须来自单一注册表，不得散落在 _build_parser 本体。"""

    def test_command_builders_registry_covers_expected_commands(self) -> None:
        """注册表包含全部 18 个子命令（核心 9 + 新增 9）。"""
        registered = {command for command, _builder in _COMMAND_BUILDERS}
        expected = {
            "check",
            "detect",
            "list-rules",
            "install-hooks",
            "report",
            "fix",
            "rule",
            "trend",
            "notify",
            "html-report",
            "recommend",
            "lsp",
            "dashboard",
            "marketplace",
            "monorepo",
            "bench",
            "cicd",
            "pattern-learner",
        }
        self.assertEqual(registered, expected)

    def test_build_parser_check_parses(self) -> None:
        """check 子命令参数解析保持不变。"""
        parser = _build_parser()
        args = parser.parse_args(["check", "src", "--json"])
        self.assertEqual(args.command, "check")
        self.assertEqual(args.path, "src")
        self.assertTrue(args.json)

    def test_build_parser_html_report_parses(self) -> None:
        """html-report 子命令参数解析保持不变。"""
        parser = _build_parser()
        args = parser.parse_args(["html-report", "src", "-o", "out.html"])
        self.assertEqual(args.command, "html-report")
        self.assertEqual(args.output, "out.html")

    def test_build_parser_no_command_shows_help(self) -> None:
        """无子命令 → command 为 None（由 main 据此打印帮助）。"""
        parser = _build_parser()
        args = parser.parse_args([])
        self.assertIsNone(args.command)

    def test_get_command_handler_resolves_known_command(self) -> None:
        """handler 解析走注册表（含 '-'→'_' 规范化）。"""
        handler = get_command_handler("check")
        self.assertTrue(callable(handler))

        html_handler = get_command_handler("html-report")
        self.assertTrue(callable(html_handler))

    def test_get_command_handler_unknown_command_raises(self) -> None:
        """未知子命令 → KeyError（argparse 层先拦截非法子命令，此处只验解析失败路径）。"""
        with self.assertRaises(KeyError):
            get_command_handler("definitely-not-a-command")


if __name__ == "__main__":
    unittest.main()
