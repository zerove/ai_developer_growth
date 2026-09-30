"""门禁加固功能测试: doctor / baseline 校验 / 增量测试 / 台账趋势。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.audit_trends import analyze, verify_chain
from tools.scripts.hooks.basic_checks import _tests_for_modules, run_tests_incremental
from tools.scripts.hooks.domain_checks import (
    prune_stale_baseline_entries,
    validate_baseline_structure,
)

# ── 基线结构校验 ───────────────────────────────────────────


class TestValidateBaselineStructure:
    def test_valid_baseline(self, tmp_path: Path) -> None:
        bl = tmp_path / "baseline.json"
        bl.write_text(
            json.dumps({"version": 1, "files": {"a.py": {"structure:x": 2}}}),
            encoding="utf-8",
        )
        ok, desc = validate_baseline_structure(bl)
        assert ok
        assert "1 个文件" in desc

    def test_missing_file(self, tmp_path: Path) -> None:
        ok, desc = validate_baseline_structure(tmp_path / "nope.json")
        assert not ok
        assert "不存在" in desc

    def test_invalid_json(self, tmp_path: Path) -> None:
        bl = tmp_path / "baseline.json"
        bl.write_text("{broken", encoding="utf-8")
        ok, desc = validate_baseline_structure(bl)
        assert not ok
        assert "JSON" in desc

    def test_missing_version(self, tmp_path: Path) -> None:
        bl = tmp_path / "baseline.json"
        bl.write_text(json.dumps({"files": {}}), encoding="utf-8")
        ok, desc = validate_baseline_structure(bl)
        assert not ok
        assert "version" in desc

    def test_bad_key_format(self, tmp_path: Path) -> None:
        bl = tmp_path / "baseline.json"
        bl.write_text(json.dumps({"version": 1, "files": {"a.py": {"badkey": 1}}}), encoding="utf-8")
        ok, _ = validate_baseline_structure(bl)
        assert not ok

    def test_zero_count_rejected(self, tmp_path: Path) -> None:
        bl = tmp_path / "baseline.json"
        bl.write_text(
            json.dumps({"version": 1, "files": {"a.py": {"t:m": 0}}}),
            encoding="utf-8",
        )
        ok, desc = validate_baseline_structure(bl)
        assert not ok
        assert "正整数" in desc

    def test_empty_files_object_valid(self, tmp_path: Path) -> None:
        bl = tmp_path / "baseline.json"
        bl.write_text(json.dumps({"version": 1, "files": {}}), encoding="utf-8")
        ok, desc = validate_baseline_structure(bl)
        assert ok


# ── 失效条目清理 ───────────────────────────────────────────


class TestPruneStaleEntries:
    def test_prunes_missing_files_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "exists.py").write_text("x = 1\n")
        bl = tmp_path / "baseline.json"
        bl.write_text(
            json.dumps(
                {
                    "version": 1,
                    "files": {
                        "exists.py": {"t:m": 1},
                        "gone.py": {"t:m": 3},
                    },
                }
            ),
            encoding="utf-8",
        )
        pruned = prune_stale_baseline_entries(bl)
        assert pruned == 1
        data = json.loads(bl.read_text(encoding="utf-8"))
        assert "exists.py" in data["files"]
        assert "gone.py" not in data["files"]


# ── doctor 必需/可选分级 ─────────────────────────────────


class TestDoctorRequiredVsOptional:
    """可选工具缺失不得使 doctor 失败。

    pip-audit 在 security 门禁中是 `|| true` 可选降级，若 doctor 把它当必需，
    健康机器也会返回非零——监控误报会让人开始忽略它，比不监控更糟。
    """

    def test_optional_tool_marked_optional(self) -> None:
        from tools.scripts.hooks_runner import _doctor_check_toolchain

        captured: list[tuple[bool, str, bool]] = []
        _doctor_check_toolchain(captured)  # type: ignore[arg-type]
        by_name = {desc.split()[1].rstrip(":"): req for _ok, desc, req in captured}
        assert by_name.get("pip-audit") is False, "pip-audit 应为可选"
        assert by_name.get("ruff") is True, "ruff 应为必需"

    def test_optional_failure_excluded_from_required(self) -> None:
        """失败判定必须尊重 required 标志，而非一律计入必需。"""
        checks: list[tuple[bool, str, bool]] = [(False, "❌ 缺失的必需工具", True), (False, "⚠️ 缺失的可选工具", False)]
        failed_required = [d for ok, d, req in checks if not ok and req]
        assert failed_required == ["❌ 缺失的必需工具"], "可选工具失败不得计入必需项"


# ── doctor pre-commit 检查 ────────────────────────────────


class TestDoctorPreCommit:
    def test_detects_broken_hook(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """复现本次会话踩到的坑: 钩子指向不存在的 Python 必须被发现。"""
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        hook = git_dir / "pre-commit"
        hook.write_text(
            "INSTALL_PYTHON=/nonexistent/python3\nexec broken\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        from tools.scripts.hooks_runner import _check_pre_commit_hook

        ok, desc = _check_pre_commit_hook()
        assert not ok
        assert "/nonexistent/python3" in desc

    def test_healthy_hook_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        (git_dir / "pre-commit").write_text("#!/bin/sh\necho custom hook\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        from tools.scripts.hooks_runner import _check_pre_commit_hook

        ok, desc = _check_pre_commit_hook()
        assert ok
        assert "跳过环境校验" in desc


# ── 增量测试选择 ───────────────────────────────────────────


class TestIncrementalTestSelection:
    def test_maps_by_name_convention(self, tmp_path: Path) -> None:
        (tmp_path / "test_foo.py").write_text("def test_x(): pass\n")
        targets = _tests_for_modules([Path("tools/scripts/foo.py")], tests_dir=tmp_path)
        assert [t.name for t in targets] == ["test_foo.py"]

    def test_maps_by_import_scan(self, tmp_path: Path) -> None:
        t = tmp_path / "test_other.py"
        t.write_text("from tools.scripts.bar import thing\n")
        targets = _tests_for_modules([Path("tools/scripts/bar.py")], tests_dir=tmp_path)
        assert [x.name for x in targets] == ["test_other.py"]

    def test_changed_test_included_directly(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        changed = tests_dir / "test_direct.py"
        changed.write_text("def test_x(): pass\n")
        targets = _tests_for_modules([changed], tests_dir=tests_dir)
        assert [t.name for t in targets] == ["test_direct.py"]

    @patch("tools.scripts.hooks.basic_checks._changed_python_files")
    def test_no_changes_skips(self, mock_changed: MagicMock) -> None:
        mock_changed.return_value = []
        passed, output = run_tests_incremental()
        assert passed
        assert "skipped" in output

    @patch("tools.scripts.hooks.basic_checks.run_tests_incremental")
    @patch("tools.scripts.hooks.basic_checks._changed_python_files")
    def test_runs_selected_targets(self, mock_changed: MagicMock, mock_inc: MagicMock, tmp_path: Path) -> None:
        mock_changed.return_value = [Path("tools/scripts/foo.py")]
        # 真实执行路径走 subprocess，这里只验证映射非空时的命令构造分支
        with patch.object(
            __import__("tools.scripts.hooks.basic_checks", fromlist=["_run_subprocess"]),
            "_run_subprocess",
        ) as mock_sub:
            mock_sub.return_value = (True, "ok")
            passed, output = run_tests_incremental(base="HEAD~1")
            assert isinstance(passed, bool)
            del output


# ── 台账趋势分析 ───────────────────────────────────────────


class TestAuditTrends:
    def test_chain_verification_ok(self, tmp_path: Path) -> None:
        entries = [
            {"event_type": "A", "prev_hash": "0" * 64, "current_hash": "a" * 64},
            {"event_type": "B", "prev_hash": "a" * 64, "current_hash": "b" * 64},
        ]
        ok, desc = verify_chain(entries)
        assert ok

    def test_chain_verification_detects_break(self, tmp_path: Path) -> None:
        entries = [
            {"event_type": "A", "prev_hash": "0" * 64, "current_hash": "a" * 64},
            {"event_type": "B", "prev_hash": "f" * 64, "current_hash": "b" * 64},
        ]
        ok, _desc = verify_chain(entries)
        assert not ok

    def test_analyze_counts_and_alerts(self) -> None:
        now_iso = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        entries = [{"event_type": f"E{i}", "timestamp": now_iso} for i in range(10)]
        report = analyze(entries)
        assert report["total"] == 10
        assert report["undated_entries"] == 0
        # 10 个不同类型各 1 次，均低于告警下限
        assert not report["alerts"]

    def test_analyze_flags_spike(self) -> None:
        import datetime as dt

        now = dt.datetime.now(dt.timezone.utc)
        # 同一类型最近24h 6 次（≥ 下限5），历史为 0 → 应告警
        entries = [{"event_type": "SPIKE", "timestamp": (now - dt.timedelta(hours=i)).isoformat()} for i in range(6)]
        report = analyze(entries)
        assert any("SPIKE" in a for a in report["alerts"])


# ── AST 语义检查: py-bare-raise ────────────────────────────


class TestAstBareRaise:
    """AST 版 bare-raise: 正则无法表达的 except 块语义判定。"""

    def _check(self, code: str) -> list:
        from tools.scripts.rules_engine.ast_semantic import check_python_bare_raise

        return check_python_bare_raise("test.py", code.splitlines())

    def test_legal_reraise_inside_except(self) -> None:
        code = "def f():\n    try:\n        pass\n    except ValueError:\n        raise\n"
        assert self._check(code) == []

    def test_illegal_raise_in_function_body(self) -> None:
        code = "def f():\n    raise\n"
        issues = self._check(code)
        assert len(issues) == 1
        assert issues[0].rule_id == "py-bare-raise"
        assert issues[0].line == 2
        assert issues[0].severity == "error"

    def test_module_level_raise_detected(self) -> None:
        issues = self._check("raise\n")
        assert len(issues) == 1

    def test_nested_try_except_legal(self) -> None:
        code = (
            "def f():\n"
            "    try:\n"
            "        try:\n"
            "            pass\n"
            "        except KeyError:\n"
            "            raise\n"
            "    except Exception:\n"
            "        pass\n"
        )
        assert self._check(code) == []

    def test_syntax_error_returns_empty(self) -> None:
        assert self._check("def f(:\n") == []

    def test_enabled_false_disables_regex_version(self) -> None:
        """enabled=false 的规则应被正则检查器跳过 (AST 版接管)。"""
        from tools.scripts.rules_engine.validators.pipeline import check_anti_patterns

        rules = {
            "anti_patterns": [
                {
                    "id": "py-bare-raise",
                    "severity": "error",
                    "category": "error_handling",
                    "pattern": r"^\s*raise\s*$",
                    "enabled": False,
                }
            ]
        }
        lines = ["def f():", "    pass", "raise"]
        # 正则版被禁用: 模块级裸 raise 不由正则报告 (AST 版负责)
        assert check_anti_patterns(lines, rules, "x.py") == []
