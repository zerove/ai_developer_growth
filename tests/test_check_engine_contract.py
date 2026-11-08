"""adg check / rules_engine 检查引擎共享不变量契约（对应 docs/agent-dev/check-engine-contract-matrix.md）。

只锁定**已验证可对齐**的部分：文件覆盖 + 核心规则。不假设 issue 总数相等
（adg_cli 规则集包含 common-*，见矩阵“已知差异”）。
"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.adg_cli import load_rules_for_language
from tools.scripts.adg_cli.check import check_directory as cli_check_directory
from tools.scripts.rules_engine.checker import check_directory as engine_check_directory


def _fixture(tmp_path: Path) -> Path:
    (tmp_path / "a.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("eval('1+1')\n", encoding="utf-8")
    (tmp_path / "c.js").write_text("var x = 1;\n", encoding="utf-8")
    (tmp_path / "d.txt").write_text("hello\n", encoding="utf-8")
    return tmp_path


def test_python_file_coverage_matches(tmp_path: Path) -> None:
    root = _fixture(tmp_path)

    engine_results = engine_check_directory(
        root,
        languages=["python"],
        jobs=1,
        run_linters=False,
        use_cache=False,
    )
    cli_issues = cli_check_directory(root, rules=load_rules_for_language("python"), jobs=1)

    engine_files = {Path(r.file).name for r in engine_results}
    cli_files = {Path(i.file).name for i in cli_issues}
    assert engine_files == {"a.py", "b.py"}
    assert cli_files == engine_files


def test_core_python_rules_present_in_both(tmp_path: Path) -> None:
    root = _fixture(tmp_path)

    engine_results = engine_check_directory(
        root,
        languages=["python"],
        jobs=1,
        run_linters=False,
        use_cache=False,
    )
    cli_issues = cli_check_directory(root, rules=load_rules_for_language("python"), jobs=1)

    engine_rules = {i.rule_id for r in engine_results for i in r.issues}
    cli_rules = {i.rule_id for i in cli_issues}
    for rule_id in ("py-eval-exec", "py-print-statement", "py-log-print"):
        assert rule_id in engine_rules
        assert rule_id in cli_rules, f"adg_cli 缺少核心规则 {rule_id}"
