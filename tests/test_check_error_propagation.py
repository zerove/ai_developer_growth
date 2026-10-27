"""并行/串行检查路径的等价性契约测试 (ADR-078)。

## 要锁住的缺陷

`adg_cli/check.py::_check_files_parallel` 曾对 worker 异常只
`print` 一条警告, 于是**崩溃的文件从结果里彻底消失**。调用方拿到的
issue 列表与"该文件干净"无法区分, `adg check` 对一个**实际根本没检查**
的文件返回退出码 0 —— 即 fail-open。

探针实测（修复前, `tests/test_zzz_probe_parallel_swallows.py`）::

    并行(jobs=2) 返回 issue 数=1   并行退出码 = 1
    串行(jobs=1) 返回 issue 数=0   串行直接抛出 RuntimeError

即并行与串行对**同一输入**给出**不同结果**, 且两者都不正确:
串行整体崩溃, 并行静默放行。

## 契约要点

1. worker 抛异常时, 该文件必须产生一条 `check-error` **error** 级 Issue;
2. 因此 `jobs>1` 与 `jobs=1` 对同一输入必须给出**相同的退出码**;
3. 崩溃文件必须**出现在输出里**（可追溯）, 不能只写进 stderr。

第 3 条是 ADR-074/076 的同类教训: 只 `print` 不留结构等于没记录。

## 探针机制说明

Linux 默认 start method 为 ``fork``, 子进程继承父进程内存, 因此在
父进程 patch 模块级 ``check_file`` 对 worker 同样生效 —— 这是本组用例
能在不真正制造 I/O 故障的前提下稳定触发 worker 内异常的原因。
"""

from pathlib import Path

import pytest

from tools.scripts.adg_cli import check as chk
from tools.scripts.adg_cli.commands.cmd import cmd_check as cc
from tools.scripts.rules_engine.models import Issue

BOOM_NAME = "boom.py"
CLEAN_NAME = "clean.py"


def _issue_for_clean_file(filepath: Path, rules: dict, severity_filter: str | None = None) -> list[Issue]:
    """正常文件返回一个 error, 以便对比"崩溃文件"是否被静默剔除。"""
    return [
        Issue(
            rule_id="probe",
            severity="error",
            category="probe",
            file=str(filepath),
            line=1,
            column=1,
            message="probe issue",
        )
    ]


def _issue_except_boom(filepath: Path, rules: dict, severity_filter: str | None = None) -> list[Issue]:
    """boom.py 抛异常, 模拟 worker 内真实崩溃。"""
    if Path(filepath).name == BOOM_NAME:
        raise RuntimeError("simulated worker crash")
    return _issue_for_clean_file(filepath, rules, severity_filter)


@pytest.fixture
def tree(tmp_path: Path) -> list[Path]:
    """两个文件: 一个正常, 一个会让 worker 崩溃。"""
    clean = tmp_path / CLEAN_NAME
    clean.write_text("x = 1\n", encoding="utf-8")
    boom = tmp_path / BOOM_NAME
    boom.write_text("y = 2\n", encoding="utf-8")
    return [clean, boom]


@pytest.fixture
def patched(monkeypatch: pytest.MonkeyPatch) -> None:
    """patch 模块级 check_file（fork 使其在 worker 内同样生效）。"""
    monkeypatch.setattr(chk, "check_file", _issue_except_boom)
    monkeypatch.setattr(cc, "check_file", _issue_except_boom)


def _check_error_issues(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.rule_id == "check-error"]


class TestCheckErrorIssueContract:
    """崩溃必须留痕, 且必须升格为 error。"""

    def test_parallel_records_check_error_issue(self, tree: list[Path], patched: None) -> None:
        issues = chk._run_checks(tree, {}, "error", 2)

        errors = _check_error_issues(issues)
        assert len(errors) == 1, f"崩溃文件未留痕: {issues}"
        assert errors[0].file.endswith(BOOM_NAME)
        assert errors[0].severity == "error", "崩溃必须是 error 级, 否则退出码仍可能为 0"
        assert "simulated worker crash" in errors[0].message

    def test_serial_records_check_error_issue(self, tree: list[Path], patched: None) -> None:
        issues = chk._run_checks(tree, {}, "error", 1)

        errors = _check_error_issues(issues)
        assert len(errors) == 1, f"串行路径同样必须留痕: {issues}"
        assert errors[0].file.endswith(BOOM_NAME)

    def test_serial_no_longer_raises(self, tree: list[Path], patched: None) -> None:
        """串行路径曾整体抛出, 导致整个 check 崩掉而非报告问题。"""
        issues = chk._run_checks(tree, {}, "error", 1)
        assert len(issues) == 2, "串行应返回 正常文件的 issue + 崩溃留痕"


class TestParallelSerialEquivalence:
    """并行与串行对同一输入必须给出相同结果 —— 这是用户可见的退出码。"""

    def test_same_issue_count(self, tree: list[Path], patched: None) -> None:
        parallel = chk._run_checks(tree, {}, "error", 2)
        serial = chk._run_checks(tree, {}, "error", 1)

        assert len(parallel) == len(serial), f"并行 {len(parallel)} != 串行 {len(serial)}"

    def test_same_exit_code(self, tree: list[Path], patched: None) -> None:
        """退出码是 CI 实际依赖的东西, 直接断言它。"""
        parallel = chk._run_checks(tree, {}, "error", 2)
        serial = chk._run_checks(tree, {}, "error", 1)

        parallel_code = 1 if any(i.severity == "error" for i in parallel) else 0
        serial_code = 1 if any(i.severity == "error" for i in serial) else 0

        assert parallel_code == serial_code == 1

    def test_crash_alone_forces_nonzero_exit(self, tmp_path: Path, patched: None) -> None:
        """**只有崩溃文件**时退出码也必须非零。

        这一条比 `test_same_exit_code` 更强：它排除了其他 error 来源的
        干扰, 因此能抓住 `check-error` 被降级为 warning 的变异
        (clean 文件本身返回 error 会把降级后的失败信号淹没)。
        """
        boom = tmp_path / BOOM_NAME
        boom.write_text("y = 2\n", encoding="utf-8")

        for jobs in (1, 2, 4):
            issues = chk._run_checks([boom], {}, "error", jobs)
            code = 1 if any(i.severity == "error" for i in issues) else 0
            assert code == 1, f"jobs={jobs} 崩溃未传递到退出码, 属于 fail-open"

    def test_failed_file_is_not_silently_dropped(self, tree: list[Path], patched: None) -> None:
        """核心回归: 崩溃文件绝不能从结果里消失。"""
        issues = chk._run_checks(tree, {}, "error", 2)

        touched = {i.file for i in issues}
        assert any(f.endswith(BOOM_NAME) for f in touched), "崩溃文件被静默剔除 (fail-open)"


class TestCmdCheckRunChecks:
    """cmd_check 有自己的 _run_checks, 必须同样不留静默。"""

    def test_cmd_check_parallel_records_error(self, tree: list[Path], patched: None) -> None:
        issues = cc._run_checks(tree, {}, "error", 2)
        assert len(_check_error_issues(issues)) == 1

    def test_cmd_check_serial_records_error(self, tree: list[Path], patched: None) -> None:
        issues = cc._run_checks(tree, {}, "error", 1)
        assert len(_check_error_issues(issues)) == 1

    def test_cmd_check_paths_agree(self, tree: list[Path], patched: None) -> None:
        parallel = cc._run_checks(tree, {}, "error", 2)
        serial = cc._run_checks(tree, {}, "error", 1)
        assert len(parallel) == len(serial)


class TestNoFalsePositive:
    """修复不能反过来制造误报: 全部正常时不得凭空出现 check-error。"""

    def test_clean_files_produce_no_check_error(self, tmp_path: Path, patched: None) -> None:
        files = []
        for name in ("a.py", "b.py", "c.py"):
            fp = tmp_path / name
            fp.write_text("x = 1\n", encoding="utf-8")
            files.append(fp)

        for jobs in (1, 2):
            issues = chk._run_checks(files, {}, "error", jobs)
            assert _check_error_issues(issues) == [], f"jobs={jobs} 误报 check-error"

    def test_single_file_never_goes_parallel(self, tmp_path: Path, patched: None) -> None:
        """len(files)<=1 时走串行分支, 单文件崩溃也要留痕。"""
        boom = tmp_path / BOOM_NAME
        boom.write_text("y = 2\n", encoding="utf-8")

        issues = chk._run_checks([boom], {}, "error", 8)
        assert len(_check_error_issues(issues)) == 1
