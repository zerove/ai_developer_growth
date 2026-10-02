"""CI 存活心跳检测。

本项目的门禁体系依赖 GitHub Actions，但存在一个无法用 CI 自身解决的死锁：
私有仓库 Actions 配额耗尽时，run 被立即拒绝、0 job、时间戳零跨度，
而任何跑在 CI 内的检测器会与被检测对象一起死亡（见 ADR-057）。

因此检测器以本地 CLI 形式提供。它读取 GitHub Actions API 判断最近一次
workflow run 是否真正执行过 job。

失效判据（不依赖 GitHub 的错误文案，文案无法区分配额拒绝与语法错误）：
- total_count == 0            run 存在但从未调度 job
- updated_at == created_at    零执行时间
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from tools.scripts._common import get_project_root, handle_error, print_check, print_section

API_ROOT = "https://api.github.com"
DEFAULT_WORKFLOW = "ci.yml"
# 超过该小时数没有成功跑出 job，视为停滞（配额耗尽通常持续数天）
STALE_HOURS = 24
HTTP_TIMEOUT = 15
# 告警 Issue 用「前缀 + 工作流名」做去重锚点：同一工作流同一时间只允许存在
# 一条开放告警，且不同工作流互不覆盖（否则 A 恢复会误关 B 的告警）
ALERT_TITLE_PREFIX = "CI 心跳: 门禁失效"


@dataclass(frozen=True)
class HealthVerdict:
    """一次心跳检查的结论。"""

    ok: bool
    reason: str
    detail: str = ""
    run_id: int | None = None
    ran_at: str | None = None


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _api_call(method: str, path: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Content-Type": "application/json"} if data else {}),
        },
    )
    # nosec B310 - API_ROOT 是模块常量 https://api.github.com，path 为内部拼接
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


def _api_get(path: str, token: str) -> dict[str, Any]:
    return _api_call("GET", path, token)


def _repo_slug() -> str:
    for env in ("GITHUB_REPOSITORY", "CI_REPOSITORY"):
        value = os.environ.get(env, "")
        if value and "/" in value:
            return value
    # 本地兜底：从 git remote 推导，避免硬编码仓库名
    import subprocess

    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=get_project_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    url = result.stdout.strip()
    if url.endswith(".git"):
        url = url[: -len(".git")]
    parts = url.replace("git@github.com:", "https://github.com/").split("/")
    if len(parts) >= 2 and parts[-2]:
        return f"{parts[-2]}/{parts[-1]}"
    return ""


def _token() -> str:
    for env in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(env, "").strip()
        if value:
            return value
    return ""


def _no_job_verdict(run_id: int, status: str, conclusion: str, created: str, updated: str) -> HealthVerdict:
    return HealthVerdict(
        False,
        "CI 已失效：最近一次 run 产生 0 个 job",
        f"run #{run_id} 状态 {status}/{conclusion}，时间戳跨度 {created} → {updated}。"
        "若三者相同，说明 run 被立即拒绝（私有仓库配额耗尽或工作流无法解析）",
        run_id,
        created,
    )


def _stale_verdict(run_id: int, total: int, age_hours: float, stale_hours: int, created: str) -> HealthVerdict:
    return HealthVerdict(
        False,
        f"CI 停滞：{age_hours:.0f} 小时没有新的 run（阈值 {stale_hours}h）",
        f"最近 run #{run_id}，产出 {total} 个 job",
        run_id,
        created,
    )


def check_ci_health(repo: str, token: str, workflow: str, stale_hours: int) -> HealthVerdict:
    """查询最近一次 workflow run，判断门禁是否真的执行过。"""
    if not repo:
        return HealthVerdict(False, "无法确定仓库标识", "未设置 GITHUB_REPOSITORY 且无法从 git remote 推导")

    runs = _api_get(f"/repos/{repo}/actions/workflows/{workflow}/runs?per_page=5", token)
    items = runs.get("workflow_runs") or []
    if not items:
        return HealthVerdict(False, "该工作流从未有过 run", f"{repo} / {workflow}")

    latest = items[0]
    run_id = latest.get("id")
    created = latest.get("created_at", "")
    updated = latest.get("updated_at", "")
    status = latest.get("status", "?")
    conclusion = latest.get("conclusion") or "?"

    jobs = _api_get(f"/repos/{repo}/actions/runs/{run_id}/jobs", token)
    total = jobs.get("total_count", 0)

    # 配额耗尽/工作流损坏：run 存在但没有任何 job 被调度
    if total == 0:
        return _no_job_verdict(run_id, status, conclusion, created, updated)

    # 有 job 但长时间没有新 run，视为停滞
    newest = _parse_ts(latest.get("created_at", ""))
    if newest is not None and status == "completed":
        age_hours = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
        if age_hours > stale_hours:
            return _stale_verdict(run_id, total, age_hours, stale_hours, created)

    return HealthVerdict(
        True,
        f"CI 正常：最近一次 run 产出 {total} 个 job",
        f"run #{run_id} 状态 {status}/{conclusion}",
        run_id,
        created,
    )


def _local_fallback() -> HealthVerdict:
    """无 token 时不静默失败，而是给出可执行的排查指引。"""
    return HealthVerdict(
        False,
        "未配置 GITHUB_TOKEN，无法探测远端 CI",
        "设置 GITHUB_TOKEN（需 repo 权限）后重试；"
        "或手动访问 https://github.com/zerove/ai_developer_growth/actions 查看",
    )


def _probe(args: argparse.Namespace) -> HealthVerdict:
    """执行探测，把网络/鉴权异常统一收敛为 HealthVerdict。"""
    token = _token()
    if not token:
        return _local_fallback()
    try:
        return check_ci_health(args.repo or _repo_slug(), token, args.workflow, args.stale_hours)
    except urllib.error.HTTPError as exc:
        return HealthVerdict(False, f"GitHub API 返回 {exc.code}", str(exc.reason))
    except urllib.error.URLError as exc:
        return HealthVerdict(False, "无法连接 GitHub API", str(exc.reason))


def _render(verdict: HealthVerdict, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "ok": verdict.ok,
                    "reason": verdict.reason,
                    "detail": verdict.detail,
                    "run_id": verdict.run_id,
                    "ran_at": verdict.ran_at,
                },
                ensure_ascii=False,
            )
        )
        return
    print_section("CI HEARTBEAT - 门禁存活检测")
    print_check(verdict.reason, verdict.ok, verdict.detail)
    if not verdict.ok:
        print("")
        print("  参考 ADR-057：检测器必须运行在 CI 之外，")
        print("  因为配额耗尽时 CI 内的任何检测器都会一并死亡。")


def _alert_title(workflow: str) -> str:
    """按工作流生成唯一告警标题，使不同工作流的告警互不干扰。"""
    return f"{ALERT_TITLE_PREFIX} ({workflow})"


def _find_alert_issue(repo: str, token: str, workflow: str) -> int | None:
    """查找该工作流已存在的开放告警 Issue，返回其编号。"""
    query = urllib.parse.quote(f'repo:{repo} is:issue is:open in:title "{_alert_title(workflow)}"')
    result = _api_get(f"/search/issues?q={query}&per_page=1", token)
    items = result.get("items") or []
    return items[0]["number"] if items else None


def _issue_body(verdict: HealthVerdict, workflow: str, recovered: bool) -> str:
    """构造告警 Issue 正文；带检测时间戳，便于判断是否为陈旧告警。"""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    state = "已恢复" if recovered else "仍失效"
    lines = [
        "由 `make ci-alert` 自动维护，请勿手工关闭。",
        "",
        f"- 状态：**{state}**",
        f"- 工作流：`{workflow}`",
        f"- 结论：{verdict.reason}",
        f"- 检测时间：{stamp}",
    ]
    if verdict.detail:
        lines.append(f"- 详情：{verdict.detail}")
    if verdict.run_id:
        lines.append(f"- 相关 run：#{verdict.run_id}")
    lines += [
        "",
        "排查顺序：",
        "1. `make ci-heartbeat` 复现并查看详情",
        "2. 若提示配额耗尽，检查账户 Actions 用量：https://github.com/settings/billing",
        "3. 若提示工作流问题，运行 actionlint 检查 `.github/workflows/`",
        "",
        "背景见 ADR-057：检测器必须在 CI 之外运行，配额耗尽时 CI 内的检测器会一并死亡。",
    ]
    return "\n".join(lines)


def _raise_alert(repo: str, token: str, workflow: str, verdict: HealthVerdict) -> str:
    """失效时开或更新该工作流的唯一告警 Issue，返回动作描述。"""
    number = _find_alert_issue(repo, token, workflow)
    body = _issue_body(verdict, workflow, recovered=False)
    if number is not None:
        _api_call("PATCH", f"/repos/{repo}/issues/{number}", token, {"body": body})
        return f"已更新告警 Issue #{number}"
    created = _api_call(
        "POST",
        f"/repos/{repo}/issues",
        token,
        {"title": _alert_title(workflow), "body": body, "labels": ["bug"]},
    )
    return f"已创建告警 Issue #{created.get('number')}"


def _clear_alert(repo: str, token: str, workflow: str, verdict: HealthVerdict) -> str:
    """恢复时关闭该工作流的告警 Issue；无开放告警则不动作。"""
    number = _find_alert_issue(repo, token, workflow)
    if number is None:
        return "无开放告警，无需关闭"
    _api_call(
        "PATCH",
        f"/repos/{repo}/issues/{number}",
        token,
        {"state": "closed", "body": _issue_body(verdict, workflow, recovered=True)},
    )
    return f"已关闭告警 Issue #{number}"


def _run_alert(repo: str, token: str, workflow: str, verdict: HealthVerdict) -> str:
    if verdict.ok:
        return _clear_alert(repo, token, workflow, verdict)
    return _raise_alert(repo, token, workflow, verdict)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CI 存活心跳检测（必须在 CI 之外运行）")
    parser.add_argument("--repo", default="", help="owner/name，默认从环境或 git remote 推导")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help=f"工作流文件（默认 {DEFAULT_WORKFLOW}）")
    parser.add_argument("--stale-hours", type=int, default=STALE_HOURS, help="停滞判定小时数")
    parser.add_argument("--json", action="store_true", help="输出 JSON，便于被其他工具消费")
    parser.add_argument("--alert", action="store_true", help="失效时开/更新 Issue，恢复时自动关闭（去重）")
    args = parser.parse_args(argv)

    verdict = _probe(args)
    if args.alert and _token():
        action = _run_alert(args.repo or _repo_slug(), _token(), args.workflow, verdict)
        if not args.json:
            print(f"  告警动作: {action}")
    _render(verdict, args.json)
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - 顶层兜底，避免裸栈刷屏
        handle_error(exc, "ci_heartbeat")
        sys.exit(1)
