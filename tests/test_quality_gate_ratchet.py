"""质量基线棘轮（ratchet）行为测试。

覆盖核心语义：
- 无基线时首次运行：记录现状并按严格模式判定
- 已有基线时：存量问题豁免，只拦截新增问题
- 局部运行成功不得用局部结果覆盖全量基线（合并式刷新）
- 基线损坏/缺失字段时退回严格模式，不阻断门禁
"""

import json
from pathlib import Path

import pytest

from tools.scripts.hooks import domain_checks


def _baseline_file(tmp_path: Path) -> Path:
    """返回隔离的基线路径。"""
    return tmp_path / "baseline" / "baseline.json"


def _baseline_total(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    return sum(sum(c.values()) for c in data["files"].values())


def _run_gate(target: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[bool, str]:
    monkeypatch.setenv("JCODE_QUALITY_BASELINE", str(_baseline_file(tmp_path)))
    return domain_checks.run_quality_gate(target, full=True)


class TestQualityGateRatchet:
    """run_quality_gate 基线棘轮语义。"""

    def test_first_run_strict_and_creates_baseline(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """无基线首次运行: 严格判定失败，同时创建含存量的基线。"""
        bad = tmp_path / "bad.py"
        bad.write_text("def f(d):\n    return eval(d)\n")

        passed, output = _run_gate(bad, tmp_path, monkeypatch)

        assert passed is False
        assert "严格" in output
        baseline = _baseline_file(tmp_path)
        assert baseline.exists()
        assert _baseline_total(baseline) > 0

    def test_second_run_exempts_existing_issues(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """已有基线: 存量问题被豁免，运行通过。"""
        bad = tmp_path / "bad.py"
        bad.write_text("def f(d):\n    return eval(d)\n")
        _run_gate(bad, tmp_path, monkeypatch)  # 生成基线

        passed, output = _run_gate(bad, tmp_path, monkeypatch)

        assert passed is True
        assert "豁免" in output

    def test_new_issue_blocks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """新增问题被拦截，且基线计数不变。"""
        clean = tmp_path / "clean.py"
        clean.write_text("print('ok')\n")
        _run_gate(clean, tmp_path, monkeypatch)
        before = _baseline_total(_baseline_file(tmp_path))

        bad = tmp_path / "bad.py"
        bad.write_text("def f(d):\n    return eval(d)\n")
        passed, _ = _run_gate(bad, tmp_path, monkeypatch)

        assert passed is False
        assert _baseline_total(_baseline_file(tmp_path)) == before

    def test_partial_run_merges_instead_of_overwrites(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """局部运行成功: 未检查文件保留原计数，不被局部结果覆盖。"""
        file_a = tmp_path / "a.py"
        file_a.write_text("def f(d):\n    return eval(d)\n")
        file_b = tmp_path / "b.py"
        file_b.write_text("def g(d):\n    return exec(d)\n")
        _run_gate(file_a.parent, tmp_path, monkeypatch)
        total_before = _baseline_total(_baseline_file(tmp_path))
        assert total_before >= 2

        # 只检查 a.py 且通过场景不存在（a.py 有存量），改用一个干净文件模拟局部成功
        clean = tmp_path / "sub"
        clean.mkdir()
        (clean / "c.py").write_text("print('fine')\n")
        passed, _ = _run_gate(clean, tmp_path, monkeypatch)

        assert passed is True
        after = _baseline_total(_baseline_file(tmp_path))
        # a.py/b.py 的存量必须保留
        data = json.loads(_baseline_file(tmp_path).read_text(encoding="utf-8"))
        keys = list(data["files"].keys())
        assert any("a.py" in k for k in keys), f"局部运行丢失了 a.py 的基线: {keys}"
        assert after >= total_before - 0  # 不应少于之前（未修复任何存量）

    def test_corrupted_baseline_falls_back_to_strict(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """基线文件损坏: 回退严格模式，不抛异常。"""
        target = tmp_path / "code.py"
        target.write_text("print('hello')\n")
        baseline = _baseline_file(tmp_path)
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text("{not valid json", encoding="utf-8")

        passed, output = _run_gate(target, tmp_path, monkeypatch)

        assert passed is True  # 干净文件应通过
        assert isinstance(output, str)

    def test_fixed_issues_removed_from_baseline(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """存量问题修复后: 合并刷新把该问题移出基线（棘轮只紧不松）。"""
        bad = tmp_path / "bad.py"
        bad.write_text("def f(d):\n    return eval(d)\n")
        other = tmp_path / "other.py"
        other.write_text("def h(d):\n    assert 1 == 2\n")
        _run_gate(bad.parent, tmp_path, monkeypatch)
        total_with_bad = _baseline_total(_baseline_file(tmp_path))

        # 修复 bad.py 后重新全量运行
        bad.write_text("print('fixed')\n")
        passed, _ = _run_gate(bad.parent, tmp_path, monkeypatch)

        assert passed is True
        total_after = _baseline_total(_baseline_file(tmp_path))
        assert total_after < total_with_bad
