"""锁定示例项目的覆盖率门禁。

历史失效模式：各示例 pyproject 里写着 `[tool.coverage.report].fail_under`，
但 CI 的 `pytest tests/` 从不带 `--cov`，阈值从未生效 —— 配置看起来存在，
门禁实际不存在。

本测试锁定三件事：
1. CI 安装 pytest-cov 并以 `--cov` 运行（否则 fail_under 不被读取）；
2. 每个示例项目都声明了 `[tool.coverage.run].source` 与
   `[tool.coverage.report].fail_under`；
3. 工作流矩阵覆盖 examples/ 下所有项目，避免新增示例被静默漏检。
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "jobs-example-tests.yml"
EXAMPLES = sorted(p for p in (ROOT / "examples").iterdir() if (p / "pyproject.toml").exists())


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _run_commands() -> list[str]:
    job = _workflow()["jobs"]["test-examples"]
    return [step["run"] for step in job["steps"] if "run" in step]


def _matrix_examples() -> list[str]:
    data = _workflow()
    default = data[True]["workflow_call"]["inputs"]["examples"]["default"]
    return json.loads(default)


def test_ci_installs_pytest_cov() -> None:
    assert any("pytest-cov" in cmd for cmd in _run_commands()), "CI 未安装 pytest-cov，--cov 无法生效"


def test_ci_runs_pytest_with_coverage() -> None:
    commands = [cmd for cmd in _run_commands() if "pytest" in cmd and "tests/" in cmd]
    assert commands, "未找到示例测试命令"
    assert any("--cov" in cmd for cmd in commands), "示例测试未启用 --cov，fail_under 形同虚设"


def test_every_example_declares_source_and_threshold() -> None:
    assert EXAMPLES, "未发现示例项目"
    for project in EXAMPLES:
        with (project / "pyproject.toml").open("rb") as fh:
            config = tomllib.load(fh)
        coverage = config.get("tool", {}).get("coverage", {})
        assert coverage.get("run", {}).get("source"), f"{project.name} 未声明 coverage source"
        threshold = coverage.get("report", {}).get("fail_under")
        assert isinstance(threshold, int) and threshold > 0, f"{project.name} 未声明有效 fail_under"


def test_workflow_matrix_covers_all_examples() -> None:
    names = _matrix_examples()
    expected = {p.name for p in EXAMPLES}
    assert expected <= set(names), f"以下示例未纳入 CI 矩阵: {sorted(expected - set(names))}"
