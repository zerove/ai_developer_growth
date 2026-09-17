"""External linter output parsing helpers for the rules engine."""

from __future__ import annotations

from pathlib import Path

from tools.scripts._common import run_command
from tools.scripts.rules_engine.logger import logger

from .models import Issue


def _run_external_linters(filepath: Path, lang: str) -> list[Issue]:
    """Run external linters and convert output to Issues."""
    issues: list[Issue] = []

    linters = {
        "python": ["ruff", "check", "--output-format=json", str(filepath)],
        "javascript": ["eslint", "--format=json", str(filepath)],
        "typescript": ["eslint", "--format=json", str(filepath)],
    }

    cmd = linters.get(lang)
    if not cmd:
        return issues

    try:
        exit_code, output = run_command(cmd)
        if output:
            issues.extend(_parse_linter_output(output, lang, str(filepath)))
    except Exception:
        # Linter 配置问题或进程失败: loguru debug 记录, 不影响主流程
        logger.debug("Linter execution failed for {} ({})", filepath, lang, exc_info=True)

    return issues


def _parse_linter_output(output: str, lang: str, filepath: str) -> list[Issue]:
    """Parse linter JSON output to Issues."""
    issues: list[Issue] = []
    try:
        import json

        data = json.loads(output)

        if lang == "python" and isinstance(data, list):
            # Ruff JSON format
            for item in data:
                issues.append(
                    Issue(
                        rule_id=item.get("code", "ruff"),
                        severity=_map_severity(item.get("level", "warning")),
                        category="linter",
                        file=filepath,
                        line=item.get("location", {}).get("row", 1),
                        column=item.get("location", {}).get("column", 1),
                        message=item.get("message", ""),
                    )
                )
        elif lang in ("javascript", "typescript") and isinstance(data, list):
            # ESLint JSON format
            for file_result in data:
                for msg in file_result.get("messages", []):
                    issues.append(
                        Issue(
                            rule_id=msg.get("ruleId", "eslint"),
                            severity=_map_severity(msg.get("severity", 1)),
                            category="linter",
                            file=filepath,
                            line=msg.get("line", 1),
                            column=msg.get("column", 1),
                            message=msg.get("message", ""),
                        )
                    )
    except Exception:
        # Linter 输出 JSON 解析失败: loguru debug 记录 (数据格式问题时排错)
        logger.debug("Linter JSON parse failed for {}", filepath, exc_info=True)

    return issues


def _map_severity(level: str | int) -> str:
    """Map various severity formats to standard levels."""
    if isinstance(level, int):
        return "error" if level == 2 else "warning"
    level = level.lower()
    if level in ("error", "critical", "fatal"):
        return "error"
    return "warning"
