"""V4 实战验证改进项测试：CLI 排除参数与行级排除（exclude_lines）。

覆盖三个产品化改进：
1. ``--exclude`` glob 模式（可重复）
2. ``--exclude-tests`` 便捷开关
3. 规则定义 ``exclude_lines`` 行级排除（字符串字面量误报治理）
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from tools.scripts.adg_cli.check import (
    _collect_check_files,
    _is_test_file,
    check_file,
)
from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns
from tools.scripts.rules_engine.rule_loader import load_rules


def _ns(**kwargs: object) -> argparse.Namespace:
    """构造最小 check 参数对象。"""
    base: dict[str, object] = {
        "path": ".",
        "since": None,
        "staged": False,
        "unstaged": False,
        "exclude": [],
        "exclude_tests": False,
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


class TestIsTestFile:
    """测试文件启发式判定。"""

    def test_tests_dir(self, tmp_path: Path) -> None:
        assert _is_test_file(tmp_path / "tests" / "x.py") is True

    def test_test_prefix(self) -> None:
        assert _is_test_file(Path("pkg/test_main.py")) is True

    def test_go_style(self) -> None:
        assert _is_test_file(Path("pkg/main_test.go")) is True

    def test_java_style(self) -> None:
        assert _is_test_file(Path("src/Main.java")) is False
        assert _is_test_file(Path("src/MainTest.java")) is True

    def test_conftest(self) -> None:
        assert _is_test_file(Path("conftest.py")) is True

    def test_normal_source(self) -> None:
        assert _is_test_file(Path("src/module.py")) is False


class TestCollectExclude:
    """_collect_check_files 的 CLI 级排除。"""

    @pytest.fixture()
    def project(self, tmp_path: Path) -> Path:
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        for rel in ("src/a.py", "src/b.py", "tests/test_a.py"):
            p = tmp_path / rel
            p.write_text("x = 1\n", encoding="utf-8")
        return tmp_path

    def test_no_exclude(self, project: Path) -> None:
        files, _ = _collect_check_files(project, _ns(), {})
        assert len(files) == 3

    def test_exclude_glob(self, project: Path) -> None:
        files, _ = _collect_check_files(project, _ns(exclude=["tests/*"]), {})
        assert len(files) == 2

    def test_exclude_repeatable(self, project: Path) -> None:
        files, _ = _collect_check_files(project, _ns(exclude=["tests/*", "*/b.py"]), {})
        assert [f.name for f in files] == ["a.py"]

    def test_exclude_tests_flag(self, project: Path) -> None:
        files, _ = _collect_check_files(project, _ns(exclude_tests=True), {})
        assert len(files) == 2
        assert all("tests" not in f.parts for f in files)

    def test_exclude_combined_with_skip_patterns(self, project: Path) -> None:
        # 与项目配置 skip_patterns 叠加生效
        cfg = {"skip_patterns": []}
        files, _ = _collect_check_files(project, _ns(exclude=["*/a.py"], exclude_tests=True), cfg)
        assert [f.name for f in files] == ["b.py"]


class TestExcludeLines:
    """规则 exclude_lines 行级排除（V4 rich 误报治理）。"""

    def test_string_literal_not_reported(self, tmp_path: Path) -> None:
        p = tmp_path / "lit.py"
        p.write_text('msg = "not called in except: block"\n', encoding="utf-8")
        issues = check_file(p, load_rules("python"))
        assert not [i for i in issues if i.rule_id == "py-bare-except"]

    def test_real_bare_except_still_reported(self, tmp_path: Path) -> None:
        p = tmp_path / "real.py"
        p.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")
        issues = check_file(p, load_rules("python"))
        bare = [i for i in issues if i.rule_id == "py-bare-except"]
        assert len(bare) == 1 and bare[0].line == 3

    def test_mixed_file_partial_exclude(self, tmp_path: Path) -> None:
        p = tmp_path / "both.py"
        p.write_text(
            'doc = "see except: clause"\ntry:\n    pass\nexcept:\n    pass\n',
            encoding="utf-8",
        )
        issues = check_file(p, load_rules("python"))
        bare = [i for i in issues if i.rule_id == "py-bare-except"]
        assert [i.line for i in bare] == [4]

    def test_engine_side_exclude_lines(self, tmp_path: Path) -> None:
        """rules_engine 引擎侧同样支持 exclude_lines。"""
        p = tmp_path / "eng.py"
        p.write_text(
            'x = "in except: block"\ntry:\n    pass\nexcept:\n    pass\n',
            encoding="utf-8",
        )
        pat = {
            "id": "py-bare-except",
            "severity": "error",
            "category": "error_handling",
            "pattern": r"except\s*:",
            "message": "m",
            "exclude_lines": [r"[^\s'\"#][^#]*['\"][^'\"]*except\s*:"],
        }
        rules = {"anti_patterns": [pat]}
        issues = check_anti_patterns(p, "python", rules)
        assert [i.line for i in issues] == [4]
