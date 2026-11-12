"""CI 工作流与分支保护必需检查的契约测试。

背景（真实失效形态）:
    `master` 的分支保护把 **CI Summary** 设为必需检查。若 `pull_request`
    触发器上带 `paths-ignore`（例如只改文档的 PR 不触发 CI），该检查在
    这类 PR 上**永远不会上报**，GitHub 会一直显示
    "Expected — Waiting for status to be reported"，PR 无法合并。

    这类缺陷没有任何报错：CI 全绿、PR 却卡死。因此把「必需检查的名字」
    与「触发器不得过滤」两件事都用测试锁住，避免有人为了省 CI 分钟数
    把 paths-ignore 加回去。
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

#: 分支保护里配置的必需检查名（与 ci.yml 的聚合 job 名一致）。
REQUIRED_CHECK = "CI Summary"


def _workflow() -> dict:
    # PyYAML 会把裸 `on:` 解析成布尔键 True, 这里只需 jobs/触发器之外的结构,
    # 因此统一按字符串取值。
    return yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))


def _trigger(data: dict, name: str) -> dict:
    """取触发器配置；兼容 PyYAML 把 `on` 解析成 True 的行为。"""
    trigger = data.get("on", data.get(True, {}))
    assert isinstance(trigger, dict), f"触发器结构异常: {trigger!r}"
    return trigger[name]


def test_summary_job_name_matches_required_check() -> None:
    """聚合 job 的 name 必须与分支保护里登记的必需检查完全一致（含大小写）。"""
    jobs = _workflow()["jobs"]
    assert "ci-summary" in jobs, "缺少聚合 job ci-summary"
    assert jobs["ci-summary"]["name"] == REQUIRED_CHECK


def test_pull_request_trigger_is_not_path_filtered() -> None:
    """PR 触发器不得使用 paths/paths-ignore 过滤。

    纯文档 PR 也必须跑 CI，否则必需检查永远缺报，PR 卡在等待状态。
    """
    pull_request = _trigger(_workflow(), "pull_request")
    assert "paths" not in pull_request, f"pull_request 触发器不得按路径过滤: {pull_request}"
    assert "paths-ignore" not in pull_request, f"pull_request 触发器不得忽略路径: {pull_request}"


def test_summary_uses_always_and_tolerates_skipped() -> None:
    """聚合 job 必须 always() 运行，且只按 failure/cancelled 判定失败。

    PR fast 分层会刻意跳过 test-312/test-313/combine-coverage, 若把 skipped
    也算失败, 每个 PR 都会被自己的分层策略判红。
    """
    job = _workflow()["jobs"]["ci-summary"]
    assert "always()" in str(job.get("if", "")), "聚合 job 必须始终运行, 否则前置作业失败时不上报"
    script = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "'failure'" in script, "未统计 failure 作业"
    assert "'cancelled'" in script, "未统计 cancelled 作业"
