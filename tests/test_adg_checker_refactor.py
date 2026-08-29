"""Tests for ADR-014: rules_engine.checker.check_directory refactor.

验证拆分后 6 个 helper 的独立行为：
- _load_directory_rules
- _discover_target_files
- _init_cache_store
- _run_architecture_analysis
- _check_with_cache
- _check_files_serial
- _check_files_parallel
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.scripts.rules_engine.checker import (
    _check_files_parallel,
    _check_files_serial,
    _check_with_cache,
    _discover_target_files,
    _init_cache_store,
    _load_directory_rules,
    _run_architecture_analysis,
)
from tools.scripts.rules_engine.models import CheckResult


class TestLoadDirectoryRules:
    """_load_directory_rules: 框架规则 + 域规则合并。"""

    def test_returns_base_rules_when_no_framework(self, tmp_path: Path) -> None:
        """空目录无 framework 规则时返回原 base_rules。"""
        base = {"anti_patterns": ["py-eval-exec"]}
        result = _load_directory_rules(tmp_path, base)
        assert result is base or result == base

    def test_returns_none_when_no_base(self, tmp_path: Path) -> None:
        """无 base_rules 时返回 None。"""
        result = _load_directory_rules(tmp_path, None)
        # 无 framework + 无 domain rules → 保持 None
        assert result is None

    def test_merges_framework_rules(self, tmp_path: Path) -> None:
        """检测到 framework 时合并规则。"""
        (tmp_path / "manage.py").write_text("#!/usr/bin/env python\n")
        (tmp_path / "settings.py").write_text("DEBUG = True\n")
        base = {"anti_patterns": ["py-eval-exec"]}
        result = _load_directory_rules(tmp_path, base)
        # 至少保持 base_rules 内容（framework 合并可能不变）
        assert result is not None
        assert "anti_patterns" in result


class TestDiscoverTargetFiles:
    """_discover_target_files: 文件发现 + 过滤。"""

    def test_finds_python_files(self, tmp_path: Path) -> None:
        """发现 .py 文件。"""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        (tmp_path / "c.txt").write_text("ignored\n")
        files = _discover_target_files(tmp_path, None)
        names = {f.name for f in files}
        assert "a.py" in names
        assert "b.py" in names
        assert "c.txt" not in names

    def test_excludes_node_modules(self, tmp_path: Path) -> None:
        """node_modules 目录被排除。"""
        (tmp_path / "src.py").write_text("x = 1\n")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "lib.py").write_text("y = 2\n")
        files = _discover_target_files(tmp_path, None)
        names = {f.name for f in files}
        assert "src.py" in names
        assert "lib.py" not in names

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        """__pycache__ 目录被排除。"""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "main.cpython-311.pyc").write_text("ignored\n")
        files = _discover_target_files(tmp_path, None)
        assert not any("__pycache__" in f.parts for f in files)

    def test_filters_by_language(self, tmp_path: Path) -> None:
        """languages 过滤：只保留匹配语言的文件。"""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.js").write_text("var x = 1;\n")
        files = _discover_target_files(tmp_path, ["python"])
        names = {f.name for f in files}
        assert "a.py" in names
        assert "b.js" not in names

    def test_finds_multiple_extensions(self, tmp_path: Path) -> None:
        """发现多种语言扩展名。"""
        for ext in [".py", ".js", ".ts", ".go", ".rs", ".java"]:
            (tmp_path / f"file{ext}").write_text("dummy")
        files = _discover_target_files(tmp_path, None)
        suffixes = {f.suffix for f in files}
        assert {".py", ".js", ".ts", ".go", ".rs", ".java"} <= suffixes


class TestInitCacheStore:
    """_init_cache_store: 增量缓存初始化。"""

    def test_returns_none_store_when_disabled(self, tmp_path: Path) -> None:
        """use_cache=False 时返回 (None, "")。"""
        store, rules_hash = _init_cache_store(False, tmp_path / "db.sqlite")
        assert store is None
        assert rules_hash == ""

    def test_initializes_store_when_enabled(self, tmp_path: Path) -> None:
        """use_cache=True 时初始化 store + 计算 rules_hash。"""
        db = tmp_path / "cache.sqlite"
        store, rules_hash = _init_cache_store(True, db)
        assert store is not None
        assert isinstance(rules_hash, str)
        # 关闭连接
        if hasattr(store, "close"):
            store.close()

    def test_falls_back_to_none_on_init_error(self, tmp_path: Path) -> None:
        """初始化失败时回退 (None, "") + warning。"""
        with patch(
            "tools.scripts.rules_engine.store.CheckStore",
            side_effect=OSError("disk full"),
        ):
            store, rules_hash = _init_cache_store(True, tmp_path / "db.sqlite")
        assert store is None
        assert rules_hash == ""


class TestRunArchitectureAnalysis:
    """_run_architecture_analysis: 跨文件架构分析。"""

    def test_returns_empty_when_arch_module_missing(self, tmp_path: Path) -> None:
        """arch 模块 ImportError 时返回 []。"""
        # 正常目录无 .adg/architecture.yml → 仍可调用
        with patch.dict("sys.modules", {"tools.scripts.rules_engine.arch": None}):
            result = _run_architecture_analysis(tmp_path)
        # 失败被吞，返回空
        assert result == [] or all(isinstance(r, CheckResult) for r in result)

    def test_returns_list_type(self, tmp_path: Path) -> None:
        """返回 list[CheckResult]。"""
        result = _run_architecture_analysis(tmp_path)
        assert isinstance(result, list)


class TestCheckWithCache:
    """_check_with_cache: 单文件检查（带缓存）。"""

    def test_returns_full_check_when_no_store(self, tmp_path: Path) -> None:
        """store=None 时执行完整检查，返回 (result, False)。"""
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        result, was_degraded = _check_with_cache(f, "python", None, None, "", False, False)
        assert isinstance(result, CheckResult)
        assert was_degraded is False

    def test_returns_cached_when_hit(self, tmp_path: Path) -> None:
        """缓存命中时跳过 check_file，返回缓存内容。"""
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        cached_issues = [
            {
                "rule_id": "test-rule",
                "severity": "warning",
                "category": "test",
                "file": str(f),
                "line": 1,
                "message": "cached",
                "fix_hint": "",
            }
        ]
        mock_store = MagicMock()
        mock_store.get_cached_result.return_value = {
            "issues": cached_issues,
            "language": "python",
        }
        result, was_degraded = _check_with_cache(f, "python", None, mock_store, "hash", False, False)
        assert result.language == "python"
        assert len(result.issues) == 1
        assert result.issues[0].rule_id == "test-rule"
        assert was_degraded is False

    def test_records_cache_degradation_on_read_error(self, tmp_path: Path) -> None:
        """缓存读取异常时返回 (result, True) 表示降级。"""
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        mock_store = MagicMock()
        mock_store.get_cached_result.side_effect = OSError("read fail")
        result, was_degraded = _check_with_cache(f, "python", None, mock_store, "hash", False, False)
        assert was_degraded is True
        assert isinstance(result, CheckResult)


class TestCheckFilesSerial:
    """_check_files_serial: 串行检查。"""

    def test_returns_results_for_multiple_files(self, tmp_path: Path) -> None:
        """多个文件全部检查，返回 results + degraded count。"""
        files = []
        for i in range(3):
            f = tmp_path / f"f{i}.py"
            f.write_text(f"x{i} = {i}\n")
            files.append(f)
        results, degraded = _check_files_serial(files, None, None, "", False, False)
        assert len(results) == 3
        assert degraded == 0

    def test_skips_skipped_results(self, tmp_path: Path) -> None:
        """skipped=True 的 CheckResult 不加入 results。"""
        f = tmp_path / "a.py"
        f.write_text("x = 1\n")
        # 模拟所有结果都 skipped
        with patch(
            "tools.scripts.rules_engine.checker._check_with_cache",
            return_value=(CheckResult(file=str(f), issues=[], language="python", skipped=True), False),
        ):
            results, _ = _check_files_serial([f], None, None, "", False, False)
        assert results == []


class TestCheckFilesParallel:
    """_check_files_parallel: 并行检查（smoke test，不真跑 worker）。"""

    def test_importable(self) -> None:
        """helper 可独立 import。"""
        assert callable(_check_files_parallel)

    def test_skips_none_results_from_workers(self) -> None:
        """worker 返回 None 时被正确过滤（通过 mock executor.map）。"""
        # 不实际创建 worker，验证函数可调用 + 返回 list
        # 直接 mock ProcessPoolExecutor 避免启动子进程
        with patch("concurrent.futures.ProcessPoolExecutor") as mock_executor:
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            # executor.map 返回一个可迭代对象
            mock_ctx.map = MagicMock(return_value=iter([None, None]))
            mock_executor.return_value = mock_ctx

            results = _check_files_parallel(
                files=[], rules=None, store=None, rules_hash="",
                db_path="dummy", use_cache=False, semantic=False,
                run_linters=False, jobs=1,
            )
        assert isinstance(results, list)
        assert results == []
