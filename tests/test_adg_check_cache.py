"""ADR-082: `adg check` 引入 CheckStore 文件级增量缓存（cache/stats 第二阶段）。

契约要点：
- **默认关闭**：只有显式 `--cache` 才启用，避免默认产生磁盘产物与意外复用；
- **缓存实现唯一**：复用 `rules_engine.store.CheckStore`（同一张 `check_cache` 表）；
- **键含生效规则签名**：文件内容或规则变化 → 键不匹配 → 重查而非复用陈旧结果；
- **统计真实**：`hits/misses/hit_rate` 是真实计数，未启用时一律 `None`（不臆造 0）；
- **缓存不改变结论**：命中缓存与完整检查产出的 issue 集合一致；
- **失败降级**：缓存读写异常只退化为完整检查，并计入 `cache_degraded`。
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
from typing import Any

import pytest


def _run_check(
    target: Path,
    *,
    cache: bool = False,
    jobs: int = 1,
    severity: str | None = None,
) -> tuple[int, dict[str, Any], list[Any]]:
    """执行 `adg check`（JSON 模式），返回 (退出码, meta, issues)。"""
    from tools.scripts.adg_cli.commands.cmd.cmd_check import cmd_check

    args = argparse.Namespace(
        path=str(target),
        lang="python",
        severity=severity,
        json=True,
        format="json",
        cache=cache,
        jobs=jobs,
        framework=None,
        sarif=False,
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmd_check(args)
    data = json.loads(buf.getvalue())
    return rc, data["meta"], data.get("issues", [])


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """含两个 Python 文件的临时项目。"""
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("y = 2\n", encoding="utf-8")
    return tmp_path


class TestAdgCheckCacheDisabledByDefault:
    def test_default_run_has_no_cache_and_no_artifact(self, project: Path) -> None:
        """默认不启用缓存：不产生 db 产物，meta 显式说明原因。"""
        rc, meta, _issues = _run_check(project)

        assert rc == 0
        assert meta["use_cache"] is False
        assert meta["cache_supported"] is True
        assert meta["cache_engine"] == "rules_engine_check_store"
        assert meta["cache_reason"] == "cache_disabled"
        assert meta["cache_hits"] is None
        assert meta["cache_misses"] is None
        assert meta["cache_hit_rate"] is None
        assert not list(project.glob(".adg/*.db"))


class TestAdgCheckCacheEnabled:
    def test_first_run_misses_then_second_run_hits(self, project: Path) -> None:
        """冷跑全 miss，热跑全 hit，且 issue 集合不变（缓存不改变结论）。"""
        rc1, meta1, issues1 = _run_check(project, cache=True)
        rc2, meta2, issues2 = _run_check(project, cache=True)

        assert rc1 == 0 and rc2 == 0
        assert meta1["cache_hits"] == 0
        assert meta1["cache_misses"] >= 1
        assert meta2["cache_hits"] >= 1
        assert meta2["cache_misses"] == 0
        assert meta2["cache_hit_rate"] == 1.0
        assert issues1 == issues2

    def test_file_change_invalidates_cache_entry(self, project: Path) -> None:
        """文件内容变化 → 该文件重新检查（miss），其余仍命中。"""
        _run_check(project, cache=True)
        (project / "a.py").write_text("x = 1\nz = 3\n", encoding="utf-8")

        _rc, meta, _issues = _run_check(project, cache=True)

        assert meta["cache_misses"] == 1
        assert meta["cache_hits"] == 1

    def test_parallel_path_reports_real_counts(self, tmp_path: Path) -> None:
        """并行路径与串行路径行为一致：冷 miss、热 hit。"""
        for index in range(6):
            (tmp_path / f"f{index}.py").write_text(f"v{index} = {index}\n", encoding="utf-8")

        _rc1, meta1, _i1 = _run_check(tmp_path, cache=True, jobs=4)
        _rc2, meta2, issues2 = _run_check(tmp_path, cache=True, jobs=4)

        assert meta1["cache_hits"] == 0
        assert meta1["cache_misses"] == 6
        assert meta2["cache_hits"] == 6
        assert meta2["cache_misses"] == 0
        assert meta2["cache_degraded"] == 0
        assert len(issues2) >= 0

    def test_cache_init_failure_reports_explicit_reason(self, project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """用户显式要求缓存但存储不可用 → 显式原因，不静默假装没有缓存。"""
        from tools.scripts.adg_cli.commands.cmd import cmd_check as cc

        def boom(*args: Any, **kwargs: Any) -> Any:
            raise OSError("read-only file system")

        monkeypatch.setattr(cc, "FileCheckCache", boom)

        _rc, meta, _issues = _run_check(project, cache=True)

        assert meta["use_cache"] is False
        assert meta["cache_supported"] is True
        assert meta["cache_reason"] == "cache_init_failed"
        assert meta["cache_hits"] is None


class TestRulesSignature:
    def test_same_rules_same_signature(self) -> None:
        from tools.scripts.adg_cli._cache import effective_rules_signature

        rules = {"anti_patterns": [{"id": "a", "pattern": "x"}]}
        assert effective_rules_signature(rules, None) == effective_rules_signature(rules, None)

    def test_rule_change_changes_signature(self) -> None:
        from tools.scripts.adg_cli._cache import effective_rules_signature

        base = {"anti_patterns": [{"id": "a", "pattern": "x"}]}
        changed = {"anti_patterns": [{"id": "a", "pattern": "y"}]}
        assert effective_rules_signature(base, None) != effective_rules_signature(changed, None)

    def test_severity_filter_changes_signature(self) -> None:
        """severity 过滤档位影响结论 → 必须进入签名，否则会复用不同过滤下的结果。"""
        from tools.scripts.adg_cli._cache import effective_rules_signature

        rules = {"anti_patterns": []}
        assert effective_rules_signature(rules, "error") != effective_rules_signature(rules, "warning")


class TestIssuePayloadRoundTrip:
    def test_payload_roundtrip_keeps_fields(self) -> None:
        from tools.scripts.adg_cli._cache import _issue_from_payload, _issue_payload
        from tools.scripts.adg_cli.core import Issue

        issue = Issue(
            rule_id="py-eval-exec",
            severity="error",
            category="security",
            file="a.py",
            line=3,
            column=5,
            message="eval used",
            fix_hint="avoid eval",
        )
        restored = _issue_from_payload(_issue_payload(issue))

        assert restored.rule_id == issue.rule_id
        assert restored.severity == issue.severity
        assert restored.category == issue.category
        assert restored.file == issue.file
        assert restored.line == issue.line
        assert restored.column == issue.column
        assert restored.message == issue.message
        assert restored.fix_hint == issue.fix_hint


class TestCheckStoreCloseFix:
    def test_close_removes_connection_from_registry(self, tmp_path: Path) -> None:
        """回归: `CheckStore.close()` 必须把连接移出注册表，否则同路径重开拿到已关闭连接。"""
        from tools.scripts.rules_engine.store import CheckStore

        db_path = tmp_path / "cache.db"
        store = CheckStore(db_path)
        store.set_cached_result(
            "a.py",
            1.0,
            10,
            {"language": "py", "passed": True, "issues": []},
            "sig",
        )
        store.close()

        reopened = CheckStore(db_path)
        try:
            cached = reopened.get_cached_result("a.py", 1.0, 10, "sig")
        finally:
            reopened.close()
        assert cached is not None
