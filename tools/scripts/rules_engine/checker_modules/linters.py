"""外部 Linter 集成模块。

集成常用的外部 linter 工具：
- ruff (Python)
- eslint (JavaScript/TypeScript)
- bandit (Python 安全扫描)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.models import Issue


def run_external_linters(filepath: Path, lang: str) -> list[Any]:
    """运行外部 linters。

    Args:
        filepath: 文件路径
        lang: 语言标识

    Returns:
        Issue 列表
    """
    issues: list[Any] = []

    if lang == "python":
        from tools.scripts.rules_engine.checker_modules.linters import run_bandit, run_ruff

        issues.extend(run_ruff(filepath))
        issues.extend(run_bandit(filepath))
    elif lang in ("javascript", "typescript"):
        from tools.scripts.rules_engine.checker_modules.linters import run_eslint

        issues.extend(run_eslint(filepath))
    elif lang == "rust":
        from tools.scripts.rules_engine.checker_modules.linters import run_clippy

        issues.extend(run_clippy(filepath))
    elif lang == "go":
        from tools.scripts.rules_engine.checker_modules.linters import run_golangci

        issues.extend(run_golangci(filepath))

    return issues


def run_ruff(filepath: Path) -> list[Any]:
    """运行 ruff 检查 Python 文件。

    Args:
        filepath: Python 文件路径

    Returns:
        Issue 列表
    """
    import subprocess

    issues: list[Any] = []

    try:
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", str(filepath)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.stdout:
            import json

            ruff_issues = json.loads(result.stdout)
            for ruff_issue in ruff_issues:
                issues.append(
                    Issue(
                        file=str(filepath),
                        line=ruff_issue.get("location", {}).get("row", 0),
                        column=ruff_issue.get("location", {}).get("column", 0),
                        severity=_map_ruff_severity(ruff_issue.get("level", "warning")),
                        category="lint",
                        rule_id=f"ruff-{ruff_issue.get('code', 'unknown')}",
                        message=ruff_issue.get("message", ""),
                    )
                )
    except Exception:
        # ruff 运行失败不阻断流程
        pass

    return issues


def run_eslint(filepath: Path) -> list[Any]:
    """运行 eslint 检查 JS/TS 文件。

    Args:
        filepath: JS/TS 文件路径

    Returns:
        Issue 列表
    """
    import subprocess

    issues: list[Any] = []

    try:
        result = subprocess.run(
            ["eslint", "--format=json", str(filepath)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.stdout:
            import json

            eslint_results = json.loads(result.stdout)
            for file_result in eslint_results:
                for msg in file_result.get("messages", []):
                    issues.append(
                        Issue(
                            file=str(filepath),
                            line=msg.get("line", 0),
                            column=msg.get("column", 0),
                            severity=_map_eslint_severity(msg.get("severity", 1)),
                            category="lint",
                            rule_id=f"eslint-{msg.get('ruleId', 'unknown')}",
                            message=msg.get("message", ""),
                        )
                    )
    except Exception:
        pass

    return issues


def run_bandit(filepath: Path) -> list[Any]:
    """运行 bandit 安全扫描。

    Args:
        filepath: Python 文件路径

    Returns:
        Issue 列表
    """
    import subprocess

    issues: list[Any] = []

    try:
        result = subprocess.run(
            ["bandit", "-f", "json", "-q", str(filepath)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.stdout:
            import json

            bandit_result = json.loads(result.stdout)
            for result_item in bandit_result.get("results", []):
                issues.append(
                    Issue(
                        file=str(filepath),
                        line=result_item.get("line_number", 0),
                        column=0,
                        severity=_map_bandit_severity(result_item.get("severity", "medium")),
                        category="security",
                        rule_id=f"bandit-{result_item.get('test_id', 'unknown')}",
                        message=result_item.get("issue_text", ""),
                    )
                )
    except Exception:
        pass

    return issues


def _map_ruff_severity(level: str) -> str:
    """映射 ruff 严重度。"""
    return {"error": "error", "warning": "warning", "info": "info"}.get(level.lower(), "warning")


def _map_eslint_severity(severity: int) -> str:
    """映射 eslint 严重度。"""
    if severity >= 2:
        return "error"
    return "warning"


def _map_bandit_severity(severity: str) -> str:
    """映射 bandit 严重度。"""
    return {"high": "error", "medium": "warning", "low": "info"}.get(severity.lower(), "warning")


def run_clippy(filepath: Path) -> list[Any]:
    """运行 cargo clippy 检查 Rust 文件。"""
    import subprocess

    issues: list[Any] = []
    try:
        result = subprocess.run(
            ["cargo", "clippy", "--message-format=json"],
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.stdout:
            import json

            for line in result.stdout.splitlines():
                try:
                    msg = json.loads(line)
                    if msg.get("reason") == "compiler-message":
                        message = msg.get("message", {})
                        rendered = message.get("rendered", "")
                        spans = message.get("span", [])
                        line_num = spans[0].get("line_start", 0) if spans else 0
                        level = message.get("level", "warning")
                        severity = "error" if level == "error" else "warning"
                        issues.append(
                            Issue(
                                file=str(filepath),
                                line=line_num,
                                column=0,
                                severity=severity,
                                category="lint",
                                rule_id="clippy-diagnostic",
                                message=rendered.strip() or message.get("message", ""),
                            )
                        )
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return issues


def run_golangci(filepath: Path) -> list[Any]:
    """运行 golangci-lint 检查 Go 文件。"""
    import subprocess

    issues: list[Any] = []
    try:
        result = subprocess.run(
            ["golangci-lint", "run", "--out-format=json", str(filepath)],
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.stdout:
            import json

            data = json.loads(result.stdout)
            for issue_item in data.get("Issues", []):
                issues.append(
                    Issue(
                        file=str(filepath),
                        line=issue_item.get("Pos", {}).get("Line", 0),
                        column=issue_item.get("Pos", {}).get("Column", 0),
                        severity="warning",
                        category="lint",
                        rule_id=f"golangci-{issue_item.get('FromLinter', 'unknown')}",
                        message=issue_item.get("Text", ""),
                    )
                )
    except Exception:
        pass
    return issues
