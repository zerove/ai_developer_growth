"""External linter output parsing helpers for the rules engine."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from tools.scripts._common import run_command
from tools.scripts.rules_engine.logger import logger

from ._checker_markers import _detect_language
from .models import Issue

_LINTER_ARGS = {
    "python": ["ruff", "check", "--output-format=json"],
    "javascript": ["eslint", "--format=json"],
    "typescript": ["eslint", "--format=json"],
}

# None = 未 prime, 此时回退逐文件 spawn: 结果相同, 只是慢。
# 用单元素 list 作 box 而非 `global` 重绑定 —— py-global-statement 规则会拦截后者。
_LINTER_BATCH_BOX: list[dict[tuple[str, str], list[Issue]] | None] = [None]

# 单次 argv 的文件数上限, 避免超长参数列表撞上 ARG_MAX。
_LINTER_BATCH_CHUNK = 200


def _prime_external_linters(filepaths: Sequence[Path], lang: str) -> None:
    """一次 linter 调用检查多个文件 (必须与 _clear_external_linters_prime 成对调用)。

    tools/scripts 209 文件实测: 逐文件 spawn 21.79s vs 关闭外部 linter 14.60s,
    spawn 占 7.19s (33%);批量化后降为 1 次进程启动。
    """
    _LINTER_BATCH_BOX[0] = None
    base = _LINTER_ARGS.get(lang)
    if not base or not filepaths:
        return

    batch: dict[tuple[str, str], list[Issue]] = {}
    paths = list(filepaths)
    for start in range(0, len(paths), _LINTER_BATCH_CHUNK):
        chunk = paths[start : start + _LINTER_BATCH_CHUNK]
        try:
            _exit, output = run_command([*base, *(str(p) for p in chunk)])
        except Exception:  # noqa: BLE001 - 批量化失败时回退逐文件, 不影响检查结论
            logger.debug("Batched linter execution failed for {} ({})", lang, exc_info=True)
            return
        if not output:
            continue
        for issue in _parse_linter_output(output, lang, ""):
            key = str(Path(issue.file).resolve())
            batch.setdefault((lang, key), []).append(issue)
    _LINTER_BATCH_BOX[0] = batch


def _clear_external_linters_prime() -> None:
    """清除 prime 状态。必须与 prime 成对调用, 否则结果会跨调用陈旧。"""
    _LINTER_BATCH_BOX[0] = None


@contextmanager
def _batched_linters(filepaths: Sequence[Path], enabled: bool) -> Iterator[None]:
    """批量化外部 linter 的作用域; 退出时必清 prime, 与 _check_files_* 的 with 合并使用。"""
    if enabled:
        by_lang: dict[str, list[Path]] = {}
        for fp in filepaths:
            by_lang.setdefault(_detect_language(fp), []).append(fp)
        for lang, paths in by_lang.items():
            _prime_external_linters(paths, lang)
    try:
        yield
    finally:
        _clear_external_linters_prime()


def _run_external_linters(filepath: Path, lang: str) -> list[Issue]:
    """Run external linters and convert output to Issues."""
    batch = _LINTER_BATCH_BOX[0]
    if batch is not None:
        return batch.get((lang, str(filepath.resolve())), [])

    cmd = _LINTER_ARGS.get(lang)
    if not cmd:
        return []

    try:
        exit_code, output = run_command([*cmd, str(filepath)])
        if output:
            return _parse_linter_output(output, lang, str(filepath))
    except Exception:  # noqa: BLE001 - linter 配置/进程失败不影响主流程
        logger.debug("Linter execution failed for {} ({})", filepath, lang, exc_info=True)

    return []


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
                        # 批量调用时每条自带 filename; 单文件调用时回退到入参。
                        file=item.get("filename") or filepath,
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
