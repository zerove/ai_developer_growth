"""_checker_workers 回归测试。

重点锁定两个已发生过的真实缺陷:
1. skipped 文件被 worker 丢成 None, 导致并行路径报告比串行路径少文件
   (串行按 ADR-053 保留 skipped 并输出 notApplicable, 并行曾整条丢弃)。
2. 缓存异常时静默退化 —— 必须表现为"结果正确但走了完整检查", 而不是少结果。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.rules_engine import _checker_workers as cw
from tools.scripts.rules_engine.checker import check_directory
from tools.scripts.rules_engine.models import CheckResult


@pytest.fixture(autouse=True)
def _reset_worker_globals():
    cw._WORKER_RULES = {}
    cw._WORKER_STORE = None
    yield
    cw._WORKER_RULES = {}
    cw._WORKER_STORE = None


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestWorkerInit:
    def test_injects_shared_rules(self) -> None:
        rules = {"anti_patterns": []}
        cw._worker_init(rules)
        assert cw._WORKER_RULES is rules
        assert cw._WORKER_STORE is None

    def test_none_rules_becomes_empty_dict(self) -> None:
        cw._worker_init(None)
        assert cw._WORKER_RULES == {}

    def test_cache_db_opens_store(self, tmp_path: Path) -> None:
        cw._worker_init({}, str(tmp_path / "cache.db"))
        assert cw._WORKER_STORE is not None

    def test_unopenable_cache_db_degrades_to_none(self, tmp_path: Path) -> None:
        """缓存打不开必须退化为无缓存, 而不是抛异常中断整批检查。"""
        blocker = tmp_path / "blocked"
        blocker.mkdir()
        blocker.chmod(0o500)
        try:
            cw._worker_init({}, str(blocker / "nested" / "cache.db"))
        finally:
            blocker.chmod(0o700)
        assert cw._WORKER_STORE is None


class TestWorkerSkippedHandling:
    """skipped 结果必须原样回传 —— 返回 None 会让该文件从报告中消失。"""

    def test_skipped_file_returns_result_not_none(self, tmp_path: Path) -> None:
        empty = _write(tmp_path / "empty.py", "")
        result, _degraded, cache_hit = cw._worker_check((empty, "python"), do_linters=False)
        assert result is not None, "skipped 文件被丢成 None, 会导致并行报告少文件"
        assert isinstance(result, CheckResult)
        assert cache_hit is None  # 未启用缓存

    def test_returned_skipped_result_is_not_cached(self, tmp_path: Path) -> None:
        """skipped 走提前 return, 不写缓存 —— 避免把"跳过"固化进增量缓存。"""
        empty = _write(tmp_path / "empty.py", "")
        db = tmp_path / "cache.db"
        cw._worker_init({}, str(db))
        cw._worker_check((empty, "python"), do_linters=False, cache_db=str(db), rules_hash="h")
        assert cw._WORKER_STORE is not None
        # 用真实存在的 API 取回缓存清单。此前这里调的是 CheckStore 并不提供的
        # get_all_results, 又用 hasattr 兜成 None, 于是 assert not rows 恒真 ——
        # 测试无论实现对错都通过, 属于假阳性防护。
        cached = {e["file_path"] for e in cw._WORKER_STORE.get_cached_files()}
        assert str(empty) not in cached

    def test_non_skipped_file_returns_issues(self, tmp_path: Path) -> None:
        src = _write(tmp_path / "s.py", "import os\nos.system('ls')\n")
        result, _degraded, cache_hit = cw._worker_check((src, "python"), do_linters=False)
        assert result is not None
        assert result.language == "python"
        assert cache_hit is None


class TestSerialParallelParity:
    """串行与并行必须产出同一份文件集合 —— 否则 -j 开关会改变报告内容。"""

    def test_same_file_set(self, tmp_path: Path) -> None:
        # 必须造 >4 个文件: check_directory 在 len(files) <= 4 时会退回串行,
        # 文件太少则 jobs=4 根本走不到并行路径, 断言会变成空跑。
        _write(tmp_path / "pkg" / "__init__.py", "")
        for i in range(5):
            _write(tmp_path / f"mod{i}.py", "import os\nos.system('ls')\n")

        serial = {r.file for r in check_directory(tmp_path, jobs=1, run_linters=False, use_cache=False)}
        parallel = {r.file for r in check_directory(tmp_path, jobs=4, run_linters=False, use_cache=False)}
        assert serial == parallel, f"串并行文件集合不一致: 仅串行={serial - parallel} 仅并行={parallel - serial}"

    def test_same_issue_count(self, tmp_path: Path) -> None:
        for i in range(5):
            _write(tmp_path / f"m{i}.py", "import os\nos.system('ls')\n" if i % 2 else "eval('1+1')\n")

        serial = sum(len(r.issues) for r in check_directory(tmp_path, jobs=1, run_linters=False, use_cache=False))
        parallel = sum(len(r.issues) for r in check_directory(tmp_path, jobs=4, run_linters=False, use_cache=False))
        assert serial == parallel

    def test_empty_file_is_reported_in_both_paths(self, tmp_path: Path) -> None:
        """回归点: 0 字节文件会被标记 skipped, 曾只在并行路径被丢弃。"""
        empty = _write(tmp_path / "empty1.py", "")
        _write(tmp_path / "empty2.py", "")
        for i in range(5):
            _write(tmp_path / f"m{i}.py", "x = 1\n")

        serial = {r.file for r in check_directory(tmp_path, jobs=1, run_linters=False, use_cache=False)}
        parallel = {r.file for r in check_directory(tmp_path, jobs=4, run_linters=False, use_cache=False)}
        assert str(empty) in serial
        assert str(empty) in parallel, "空文件(0 字节 → skipped)在并行路径被丢弃"
        assert serial == parallel
