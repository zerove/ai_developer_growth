"""CI 里跑本仓库测试套件的工作流必须检出完整 git 历史。

背景（真实失效形态）:
    `governance-audit` 作业会跑**完整** pytest 套件, 但 checkout 用默认的
    浅克隆 (depth 1)。`tests/test_release.py::test_get_git_log_real_repo`
    断言 `git log` 条数 > 5 → 浅克隆只有 1 个提交, 必失败; 依赖既有 tag 的
    用例同理。

    症状极具误导性: 同一个套件在 `test-311` 全绿 (那里有 fetch-depth: 0),
    在审计作业里却红, 而审计输出又被截断, 看起来像"审计器自己坏了"。
    根因是**两个作业的前置条件不一致**, 不是代码缺陷。

    因此: 任何真正执行本仓库测试的工作流, 其 checkout 都必须
    `fetch-depth: 0`; 新增此类作业时若忘了加, 本测试直接失败。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

#: 给**其他项目**用的模板/示例工作流, 测的是别处的 `tests/`, 不适用本仓库口径。
EXCLUDED = {"example-ci-template.yml"}

#: 真正执行本仓库测试套件的命令（`pytest tests/`、`python -m pytest tests/` 等）。
_RUNS_LOCAL_SUITE = re.compile(r"(?:python -m )?pytest\s+(?:tests/|ai-dev-framework/tests/)")


def _workflow_files() -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.yml") if p.name not in EXCLUDED)


def _steps(data: dict) -> list[dict]:
    steps: list[dict] = []
    for job in data.get("jobs", {}).values():
        steps.extend(job.get("steps", []) or [])
    return steps


def _runs_local_suite(data: dict) -> bool:
    """是否存在执行**本仓库**测试套件的步骤。

    `cd examples/<x> && pytest tests/` 测的是示例项目自己的套件（各自有
    pyproject 与依赖），不属于本仓库口径, 故按 `examples/` 排除。
    """
    for step in _steps(data):
        run = str(step.get("run", ""))
        if "examples/" in run:
            continue
        if _RUNS_LOCAL_SUITE.search(run):
            return True
    return False


def _test_running_workflows() -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    for path in _workflow_files():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if _runs_local_suite(data):
            found.append((path.name, data))
    return found


def test_discovery_is_not_vacuous() -> None:
    """防止正则失配后"零个工作流需要检查"式假通过。"""
    names = {name for name, _ in _test_running_workflows()}
    assert "jobs-tests.yml" in names, f"未识别出权威测试作业, 检查规则可能已失效: {names}"


@pytest.mark.parametrize(("name", "data"), _test_running_workflows(), ids=lambda v: v if isinstance(v, str) else "")
def test_full_history_checked_out(name: str, data: dict) -> None:
    checkouts = [s for s in _steps(data) if str(s.get("uses", "")).startswith("actions/checkout")]
    assert checkouts, f"{name} 没有 checkout 步骤"
    depths = [str((s.get("with") or {}).get("fetch-depth", "")) for s in checkouts]
    assert any(d == "0" for d in depths), (
        f"{name} 会执行本仓库测试套件, 但 checkout 未设 fetch-depth: 0 (当前: {depths}); test_release 依赖完整 git 历史"
    )
