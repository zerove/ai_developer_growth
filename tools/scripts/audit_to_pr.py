#!/usr/bin/env python3
"""
治理审计到 PR 报告生成器

用法:
    python tools/scripts/audit_to_pr.py --run-audit           # 运行审计并生成报告
    python tools/scripts/audit_to_pr.py --create-pr           # 创建 PR (需配合 --run-audit)
    python tools/scripts/audit_to_pr.py --output report.md    # 输出到文件
    echo '{"violations":[]}' | python tools/scripts/audit_to_pr.py --stdin  # 从 stdin 读取
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def run_governance_audit(full: bool = True) -> dict[str, Any]:
    """运行治理审计并返回结构化结果。"""
    cmd = [
        sys.executable,
        "tools/scripts/hooks_runner.py",
        "governance-audit",
        "--full" if full else "",
    ]
    # 移除空字符串
    cmd = [c for c in cmd if c]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=Path(__file__).resolve().parent.parent.parent,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Audit timed out after 600 seconds",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
        }


def parse_audit_output(output: str) -> dict[str, Any]:
    """解析审计输出，提取关键信息。"""
    checks = []
    failed_checks = []
    passed_checks = []

    lines = output.split("\n")

    for line in lines:
        # 检测章节标题
        if "————————————————————————————————————————" in line:
            continue
        stripped = line.strip()
        if ("✅ PASS" in stripped or "❌ FAIL" in stripped) and ":" in stripped:
            # 解析检查结果
            parts = stripped.split(":", 1)
            if len(parts) >= 2:
                status = parts[0].strip()
                name = parts[1].strip()
                if "PASS" in status:
                    passed_checks.append(name)
                else:
                    failed_checks.append(name)
                checks.append({"name": name, "passed": "PASS" in status})

        if "Failed checks:" in line:
            failed_checks = [c.strip() for c in line.replace("Failed checks:", "").split(",") if c.strip()]

    return {
        "total_checks": len(checks),
        "passed": len(passed_checks),
        "failed": len(failed_checks),
        "checks": checks,
        "failed_check_names": failed_checks,
        "passed_check_names": passed_checks,
    }


def _build_report_header(timestamp: str, success: bool) -> list[str]:
    """构建报告头部。"""
    return [
        "## ⚖️ 治理审计报告",
        f"**运行时间**: {timestamp}",
        f"**整体状态**: {'✅ 通过' if success else '❌ 失败'}",
        "",
        "### 📊 汇总",
    ]


def _build_summary_lines(parsed: dict[str, Any]) -> list[str]:
    """构建汇总行。"""
    return [
        f"- 总检查项: {parsed['total_checks']}",
        f"- ✅ 通过: {parsed['passed']}",
        f"- ❌ 失败: {parsed['failed']}",
        "",
    ]


def _build_failed_checks_section(parsed: dict[str, Any]) -> list[str]:
    """构建失败检查项章节。"""
    if parsed["failed"] == 0:
        return []
    lines = ["### ❌ 失败的检查项", ""]
    for check in parsed["checks"]:
        if not check["passed"]:
            lines.append(f"- **{check['name']}**")
    lines.append("")
    return lines


def _build_passed_checks_section(parsed: dict[str, Any]) -> list[str]:
    """构建通过检查项章节。"""
    if parsed["passed"] == 0:
        return []
    lines = ["### ✅ 通过的检查项", ""]
    for check in parsed["checks"]:
        if check["passed"]:
            lines.append(f"- {check['name']}")
    lines.append("")
    return lines


def _build_raw_output_section(audit_result: dict[str, Any], success: bool) -> list[str]:
    """构建原始输出章节。"""
    lines = []
    if audit_result.get("stdout"):
        lines.extend(
            [
                "<details>",
                "<summary>📄 完整审计输出 (点击展开)</summary>",
                "",
                "```",
                audit_result["stdout"],
                "```",
                "",
                "</details>",
                "",
            ]
        )
    if audit_result.get("stderr") and not success:
        lines.extend(
            [
                "<details>",
                "<summary>⚠️ 错误输出 (点击展开)</summary>",
                "",
                "```",
                audit_result["stderr"],
                "```",
                "",
                "</details>",
                "",
            ]
        )
    return lines


def _build_footer() -> list[str]:
    """构建报告尾部。"""
    return [
        "---",
        "*由 [AI-Native SDLC](https://github.com/zerove/ai_developer_growth) 自动生成*",
    ]


def format_pr_report(audit_result: dict[str, Any], parsed: dict[str, Any]) -> str:
    """格式化为 GitHub PR 报告。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    success = audit_result["success"]

    report = []
    report.extend(_build_report_header(timestamp, success))
    report.extend(_build_summary_lines(parsed))
    report.extend(_build_failed_checks_section(parsed))
    report.extend(_build_passed_checks_section(parsed))
    report.extend(_build_raw_output_section(audit_result, success))
    report.extend(_build_footer())

    return "\n".join(report)


def _check_git_repo() -> dict[str, Any] | None:
    """检查是否在 git 仓库中。返回 None 表示通过，否则返回错误字典。"""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return {"success": False, "error": "Not a git repository"}
    return None


def _check_gh_cli() -> dict[str, Any] | None:
    """检查 gh CLI 是否可用。返回 None 表示通过，否则返回错误字典。"""
    try:
        subprocess.run(["gh", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"success": False, "error": "GitHub CLI (gh) not found or not authenticated"}
    return None


def _get_current_branch() -> str:
    """获取当前分支名称。"""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _create_temp_branch() -> str:
    """创建临时分支并返回分支名。"""
    import uuid

    head_branch = f"audit-report-{uuid.uuid4().hex[:8]}"
    subprocess.run(["git", "checkout", "-b", head_branch], check=True, capture_output=True)
    return head_branch


def _push_branch(head_branch: str) -> None:
    """推送分支到远程。"""
    subprocess.run(["git", "push", "-u", "origin", head_branch], check=True, capture_output=True)


def _create_pr_with_body(title: str, body_file: str, base_branch: str, head_branch: str) -> dict[str, Any]:
    """使用 body 文件创建 PR。"""
    cmd = [
        "gh",
        "pr",
        "create",
        "--title",
        title,
        "--body-file",
        body_file,
        "--base",
        base_branch,
        "--head",
        head_branch,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return {"success": True, "pr_url": result.stdout.strip()}
    return {"success": False, "error": result.stderr}


def create_github_pr(title: str, body: str, base_branch: str = "main") -> dict[str, Any]:
    """使用 GitHub CLI 创建 PR。"""
    # 检查前置条件
    if error := _check_git_repo():
        return error
    if error := _check_gh_cli():
        return error

    # 创建临时文件存储 PR body
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        body_file = f.name

    try:
        # 获取当前分支
        head_branch = _get_current_branch()

        # 如果在 main/master 分支，创建临时分支
        if head_branch in ["main", "master"]:
            head_branch = _create_temp_branch()

        # 推送分支
        _push_branch(head_branch)

        # 创建 PR
        return _create_pr_with_body(title, body_file, base_branch, head_branch)

    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}
    finally:
        # 清理临时文件
        try:
            os.unlink(body_file)
        except Exception:  # noqa: BLE001 - ignore cleanup failures
            pass


def format_audit_results_json(json_input: str) -> str:
    """兼容旧版本：将 JSON 违规数据格式化为 PR 评论。"""
    try:
        violations = json.loads(json_input)
    except json.JSONDecodeError:
        return "❌ Error: Invalid JSON input provided to audit-to-pr."

    if not violations:
        return "✨ **治理审计**: 未发现规范违规。做得好！"

    critical_count = sum(1 for v in violations if v.get("severity") == "Critical")
    warning_count = sum(1 for v in violations if v.get("severity") == "Warning")
    info_count = sum(1 for v in violations if v.get("severity") == "Info")

    report = [
        "## ⚖️ 治理审计报告 (JSON 输入模式)",
        f"自动审计发现 **{len(violations)}** 个规范违规。",
        f"- 🔴 **Critical**: {critical_count}",
        f"- 🟡 **Warning**: {warning_count}",
        f"- 🔵 **Info**: {info_count}",
        "",
        "### 📋 违规详情",
        "| Severity | Rule ID | Message |",
        "| :--- | :--- | :--- |",
    ]

    for v in violations:
        severity_icon = "🔴" if v.get("severity") == "Critical" else "🟡" if v.get("severity") == "Warning" else "🔵"
        report.append(
            f"| {severity_icon} {v.get('severity', 'Unknown')} | `{v.get('rule_id', 'N/A')}` | {v.get('message', 'N/A')} |"
        )

    report.append("\n---\n")
    report.append("**如何解决？**")
    report.append("1. **修复代码**: 使变更符合项目规范。")
    report.append("2. **覆盖规则**: 若为有意偏离，使用本地覆盖并提交至 `.ai-audit-history.json`。")

    return "\n".join(report)


def _handle_stdin_mode() -> int:
    """处理 stdin 模式（兼容旧版本）。"""
    input_data = sys.stdin.read()
    if not input_data:
        print("❌ Error: No input provided to audit-to-pr.")
        return 1
    print(format_audit_results_json(input_data))
    return 0


def _run_audit_and_generate_report(full: bool) -> tuple[dict[str, Any], str]:
    """运行审计并生成报告。"""
    print("🔍 运行治理审计...", file=sys.stderr)
    audit_result = run_governance_audit(full=full)
    parsed = parse_audit_output(audit_result.get("stdout", ""))
    report = format_pr_report(audit_result, parsed)
    return audit_result, report


def _handle_output(report: str, output: Path | None) -> None:
    """处理输出到文件。"""
    if output:
        output.write_text(report, encoding="utf-8")
        print(f"📝 报告已写入: {output}", file=sys.stderr)


def _handle_create_pr(report: str, title: str, base: str) -> int:
    """处理创建 PR。"""
    print("📤 创建 GitHub PR...", file=sys.stderr)
    pr_result = create_github_pr(title, report, base)
    if pr_result["success"]:
        print(f"✅ PR 创建成功: {pr_result['pr_url']}", file=sys.stderr)
        return 0
    else:
        print(f"❌ PR 创建失败: {pr_result['error']}", file=sys.stderr)
        return 1


def _handle_stdout_output(report: str, output: Path | None, create_pr: bool) -> None:
    """处理标准输出。"""
    if not output and not create_pr:
        print(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="治理审计到 PR 报告生成器")
    parser.add_argument("--run-audit", action="store_true", help="运行完整治理审计")
    parser.add_argument("--create-pr", action="store_true", help="创建 GitHub PR (需配合 --run-audit)")
    parser.add_argument("--output", type=Path, help="输出报告到文件")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取 JSON 数据 (旧版本兼容)")
    parser.add_argument("--title", default="chore: governance audit report", help="PR 标题")
    parser.add_argument("--base", default="main", help="PR 基础分支")
    parser.add_argument("--no-full", action="store_true", help="运行快速审计 (不含 security/test)")

    args = parser.parse_args()

    # 兼容旧版本：从 stdin 读取 JSON
    if args.stdin:
        return _handle_stdin_mode()

    # 运行审计
    if args.run_audit or args.create_pr:
        audit_result, report = _run_audit_and_generate_report(full=not args.no_full)

        # 输出到文件
        _handle_output(report, args.output)

        # 创建 PR
        if args.create_pr:
            return _handle_create_pr(report, args.title, args.base)

        # 如果没有指定输出文件，打印到 stdout
        _handle_stdout_output(report, args.output, args.create_pr)

        return 0 if audit_result["success"] else 1

    # 无参数时显示帮助
    parser.print_help()
    return 1


# 向后兼容别名
format_audit_results = format_audit_results_json


if __name__ == "__main__":
    sys.exit(main())
