"""adg check 的文件级增量缓存（复用 rules_engine `CheckStore`，ADR-082）。

## 为什么需要

`adg check` 走 `adg_cli` 路径，与 `rules_engine.checker` 各查一遍时**结果无法复用**：
重复扫描全仓时，未改动的文件会被重新读取、重新匹配规则，耗时随文件数线性增长。

## 设计约束

- **缓存实现唯一**：复用 `tools.scripts.rules_engine.store.CheckStore`（同一张
  `check_cache` 表），不另起炉灶 —— 两套缓存实现必然漂移。
- **缓存键**：`(file_path, mtime, size, effective_rules_signature)`。文件内容或
  **最终生效规则**（语言规则 + 框架规则 + custom rules + severity 覆盖 + severity
  过滤档位）任一变化，键即不匹配 → 自然失效，不会吃到陈旧结果。
- **统计真实**：`hits/misses` 是真实计数；未启用或不可知一律 `None`（不臆造 0，
  0 会被下游读成"缓存全未命中"）。
- **失败降级**：缓存读/写异常只降级为完整检查（**结论不受影响**），并计入
  `cache_degraded`；绝不静默吞掉。
- **默认关闭**：只有显式 `--cache` 才启用，避免默认产生磁盘产物与意外复用。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli.core import Issue
from tools.scripts.rules_engine.store import CheckStore

#: 缓存实现标识（与 rules_engine 路径一致，下游按此识别实现）。
CACHE_ENGINE_ID = "rules_engine_check_store"

#: 未启用缓存时的原因（与 rules_engine 路径一致）。
CACHE_REASON_DISABLED = "cache_disabled"

#: 缓存初始化失败时的原因（用户显式要求了缓存，但存储不可用）。
CACHE_REASON_INIT_FAILED = "cache_init_failed"

CheckFn = Callable[[Path, dict[str, Any], str | None], list[Issue]]


def effective_rules_signature(rules: dict[str, Any], severity_filter: str | None = None) -> str:
    """计算**最终生效规则集**的签名（sha256 前 32 位十六进制）。

    只纳入真正影响单文件检查结论的输入：生效规则内容 + severity 过滤档位。
    规则或过滤档位一变签名就变，旧缓存键自然不匹配 → 重查而非复用陈旧结果。
    """
    canonical = json.dumps(rules, sort_keys=True, ensure_ascii=False, default=str)
    payload = f"{canonical}|severity={severity_filter or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _issue_payload(issue: Issue) -> dict[str, Any]:
    """Issue → 可 JSON 化负载（字段与 `adg_cli.core.Issue.__init__` 对齐）。"""
    return {
        "rule_id": issue.rule_id,
        "severity": issue.severity,
        "category": issue.category,
        "file": issue.file,
        "line": issue.line,
        "column": issue.column,
        "message": issue.message,
        "fix_hint": issue.fix_hint,
        "related_docs": list(issue.related_docs),
    }


def _issue_from_payload(payload: dict[str, Any]) -> Issue:
    """负载 → Issue（缺字段用保守默认值，不因缓存数据残缺而崩）。"""
    return Issue(
        rule_id=str(payload.get("rule_id", "")),
        severity=str(payload.get("severity", "warning")),
        category=str(payload.get("category", "style")),
        file=str(payload.get("file", "")),
        line=int(payload.get("line", 1) or 1),
        column=int(payload.get("column", 0) or 0),
        message=str(payload.get("message", "")),
        fix_hint=str(payload.get("fix_hint", "")),
        related_docs=list(payload.get("related_docs") or []),
    )


def hit_rate(hits: int | None, misses: int | None) -> float | None:
    """`hits/(hits+misses)`；计数不可知或全为 0 时返回 None（不臆造 0）。"""
    if hits is None or misses is None:
        return None
    total = hits + misses
    if total <= 0:
        return None
    return hits / total


class FileCheckCache:
    """按文件复用的增量检查结果缓存（串行/并行共用同一实现）。"""

    def __init__(self, db_path: str | Path, signature: str) -> None:
        self.db_path = str(db_path)
        self.signature = signature
        self.store = CheckStore(self.db_path)
        self.hits = 0
        self.misses = 0
        self.degraded = 0

    def close(self) -> None:
        """关闭存储连接（失败不影响检查结论）。"""
        try:
            self.store.close()
        except Exception:  # noqa: BLE001 - 关闭失败属可忽略故障
            pass

    def check_file(
        self,
        filepath: Path,
        rules: dict[str, Any],
        severity_filter: str | None,
        check_fn: CheckFn,
    ) -> tuple[list[Issue], bool]:
        """带缓存的单文件检查，返回 `(issues, cache_hit)`。

        命中 → 直接复用上次 issues；未命中 → 完整检查并写回缓存。
        缓存读/写异常 → 降级为完整检查（结论不受影响），并计入 `degraded`。
        """
        stat = None
        try:
            stat = filepath.stat()
        except OSError:
            stat = None

        if stat is not None:
            try:
                cached = self.store.get_cached_result(str(filepath), stat.st_mtime, stat.st_size, self.signature)
            except Exception:  # noqa: BLE001 - 缓存损坏/并发冲突 → 重算
                self.degraded += 1
                cached = None
            if cached is not None:
                self.hits += 1
                return [_issue_from_payload(item) for item in cached.get("issues", [])], True

        issues = check_fn(filepath, rules, severity_filter)
        self.misses += 1

        if stat is not None:
            try:
                self.store.set_cached_result(
                    str(filepath),
                    stat.st_mtime,
                    stat.st_size,
                    {
                        "language": filepath.suffix.lstrip("."),
                        "passed": not any(i.severity == "error" for i in issues),
                        "errors": sum(1 for i in issues if i.severity == "error"),
                        "warnings": sum(1 for i in issues if i.severity == "warning"),
                        "info": sum(1 for i in issues if i.severity == "info"),
                        "issues": [_issue_payload(i) for i in issues],
                    },
                    self.signature,
                )
            except Exception:  # noqa: BLE001 - 缓存写入失败仅丢性能
                self.degraded += 1
        return issues, False


# ── worker 侧（ProcessPoolExecutor initializer 注入）──────────────────────

_WORKER_CACHE: FileCheckCache | None = None


def init_worker_cache(db_path: str | None, signature: str) -> None:
    """在 worker 进程中打开一次缓存连接（仅 worker 进程内执行）。"""
    global _WORKER_CACHE
    _WORKER_CACHE = None
    if not db_path:
        return
    try:
        _WORKER_CACHE = FileCheckCache(db_path, signature)
    except Exception:  # noqa: BLE001 - 初始化失败 → 退化为无缓存完整检查
        _WORKER_CACHE = None


def worker_cache() -> FileCheckCache | None:
    """取得 worker 进程内的缓存实例（未初始化时返回 None）。"""
    return _WORKER_CACHE
