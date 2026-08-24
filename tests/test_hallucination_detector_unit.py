"""hallucination_detector 纯函数回归测试（覆盖率门禁提升配套）。"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine.hallucination_detector import (
    _create_finding,
    _is_comment,
    _is_in_string,
    _should_ignore_file,
)


class TestShouldIgnoreFile:
    def test_ignores_node_modules(self) -> None:
        assert _should_ignore_file(Path("proj/node_modules/pkg/a.py")) is True

    def test_ignores_internal_tool_files(self) -> None:
        assert _should_ignore_file(Path("tools/auto_fix.py")) is True

    def test_normal_source_not_ignored(self) -> None:
        assert _should_ignore_file(Path("src/main.py")) is False


class TestIsInString:
    def test_inside_double_quotes(self) -> None:
        line = 'x = "hello world"'
        assert _is_in_string(line, 8) is True

    def test_outside_string(self) -> None:
        line = 'x = "a" + b'
        assert _is_in_string(line, 10) is False

    def test_escaped_quote(self) -> None:
        line = r'x = "a\"b" + c'
        # 转义引号不结束字符串，pos 在字符串内部
        assert _is_in_string(line, 9) is True

    def test_single_quotes(self) -> None:
        line = "y = 'abc'"
        assert _is_in_string(line, 6) is True


class TestIsComment:
    def test_hash_comment(self) -> None:
        assert _is_comment("# full comment", 5) is True

    def test_slash_slash_comment(self) -> None:
        line = "let x = 1; // trailing"
        assert _is_comment(line, 18) is True

    def test_code_is_not_comment(self) -> None:
        assert _is_comment("return value", 3) is False


class TestCreateFinding:
    def test_fields_mapped(self, tmp_path: Path) -> None:
        pattern = {
            "id": "hallucinated-api",
            "severity": "error",
            "category": "api",
            "message": "Nonexistent API",
            "confidence": 0.9,
        }
        finding = _create_finding(tmp_path / "a.py", 12, 4, pattern, "  foo.bar(")
        assert finding.file == str(tmp_path / "a.py")
        assert finding.line == 12
        assert finding.pattern_id == "hallucinated-api"
        assert finding.severity == "error"
        assert finding.confidence == 0.9
        assert finding.evidence == "foo.bar("
