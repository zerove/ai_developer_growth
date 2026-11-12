"""变异测试工作流的契约测试。

背景（真实失效形态）:
    1. `mutmut run --max-runtime=1800` —— 该选项属于 mutmut 3.x, 2.x 没有,
       作业在第一步就失败，变异测试从未真正跑起来。
    2. `mutmut results --show-all` —— 2.x 没有该参数，报告步骤必失败。
    3. mutmut 2.x 把变异状态写进 SQLite 缓存 (`.mutmut-cache`)，主进程与变异
       worker 进程并发写同一文件，默认 journal 模式下必然 "database is locked"，
       作业在检查阶段直接崩溃。
    4. 变异范围不限定时，每个 mutant 都要跑一次测试 —— 对整个 rules_engine
       而言是数小时的量级，夜间作业必然超时。

这些缺陷都不产生"看不懂"的报错，只是流水线恒红，因此用测试锁住契约。
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MUTATION_WORKFLOW = ROOT / ".github" / "workflows" / "mutation-testing.yml"


def _steps() -> list[dict]:
    data = yaml.safe_load(MUTATION_WORKFLOW.read_text(encoding="utf-8"))
    return data["jobs"]["mutation-testing"]["steps"]


def _script(step_name: str) -> str:
    for step in _steps():
        if step.get("name") == step_name:
            return str(step.get("run", ""))
    raise AssertionError(f"未找到步骤: {step_name}")


def test_run_command_uses_mutmut2_options() -> None:
    """--max-runtime 是 mutmut 3.x 的选项, 2.x 没有 → 必须去掉。"""
    script = _script("Run mutation testing")
    assert "--max-runtime" not in script, "mutmut 2.x 不支持 --max-runtime"
    assert "--paths-to-mutate" in script, "必须显式限定变异范围"


def test_report_command_matches_mutmut2_cli() -> None:
    """`mutmut results --show-all` 在 2.x 不存在。"""
    script = _script("Generate mutation report")
    assert "--show-all" not in script, "mutmut 2.x 的 results 没有 --show-all"
    assert "mutmut results" in script


def test_cache_database_uses_wal_mode() -> None:
    """mutmut 2.x 的 SQLite 缓存必须用 WAL, 否则并发写必然 "database is locked"。"""
    script = _script("Prepare mutmut cache database")
    assert "journal_mode=WAL" in script, "变异缓存未启用 WAL, 并发写会锁库"
    assert ".mutmut-cache" in script


def test_runner_is_scoped_to_dedicated_tests() -> None:
    """变异 runner 必须只跑对应模块的测试, 否则单个 mutant 的耗时会拖垮作业。"""
    script = _script("Run mutation testing")
    assert "--runner" in script
    assert "tests/test_supply_chain_compliance_policy.py" in script


def test_surviving_mutants_are_reported_not_silent() -> None:
    """存活变异体必须进报告 (artifact), 不能悄悄消失。"""
    report = _script("Generate mutation report")
    assert "mutation-report.txt" in report
    upload = [s for s in _steps() if s.get("name") == "Upload mutation report"]
    assert upload, "缺少变异报告上传步骤"
    assert upload[0]["with"]["path"] == "mutation-report.txt"


def test_mutation_score_gate_exists() -> None:
    """必须有击杀率阈值门禁 —— "跑完就算过"是假绿。"""
    steps = [s for s in _steps() if s.get("name") == "Check mutation score"]
    assert steps, "缺少变异得分门禁步骤"
    script = str(steps[0].get("run", ""))
    assert "mutation_score" in script
    assert "--min-rate" in script


def test_workflow_has_timeout_guard() -> None:
    """变异测试必须有超时兜底, 否则卡死会一直占着夜间作业。"""
    data = yaml.safe_load(MUTATION_WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"]["mutation-testing"]
    assert job.get("timeout-minutes"), "作业缺少超时兜底"
    assert "timeout " in _script("Run mutation testing"), "缺少 shell 级超时"
