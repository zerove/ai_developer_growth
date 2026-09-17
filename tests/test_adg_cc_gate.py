"""Phase 36a: adg check --complexity cc 门禁测试（子进程端到端）。

验证 ``adg check --complexity`` 对 Python 文件执行圈复杂度门禁：
- cc >= 阈值（默认 10）的函数以 error 报出（rule_id py-ast-complexity）
- 不带 --complexity 时 cc 不检查
- 非 Python 文件跳过
- --max-cc 可调整阈值
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

HIGH_CC = """\
def high_cc(x):
    if x == 0:
        r = 0
    elif x == 1:
        r = 1
    elif x == 2:
        r = 2
    elif x == 3:
        r = 3
    elif x == 4:
        r = 4
    elif x == 5:
        r = 5
    elif x == 6:
        r = 6
    elif x == 7:
        r = 7
    elif x == 8:
        r = 8
    else:
        r = 9
    return r
"""

LOW_CC = "def low_cc(x):\n    return x + 1\n"


def _run_cli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[bytes]:
    """以仓库根为 cwd 运行 CLI，返回 CompletedProcess。"""
    return subprocess.run(
        [PY, "-m", "tools.scripts.adg_cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=timeout,
    )


class TestCheckComplexityGate:
    """adg check --complexity cc 门禁端到端测试。"""

    def test_high_complexity_reports_error(self, tmp_path: Path) -> None:
        """cc=10 函数 → --complexity 时报 error 且 exit 1。"""
        sample = tmp_path / "high_cc.py"
        sample.write_text(HIGH_CC, encoding="utf-8")
        r = _run_cli("check", str(sample), "--complexity")
        assert r.returncode == 1
        output = (r.stdout + r.stderr).decode()
        assert "py-ast-complexity" in output
        assert "high_cc" in output

    def test_no_flag_skips_cc(self, tmp_path: Path) -> None:
        """不带 --complexity → 高复杂度文件不报 cc，exit 0。"""
        sample = tmp_path / "high_cc.py"
        sample.write_text(HIGH_CC, encoding="utf-8")
        r = _run_cli("check", str(sample))
        assert r.returncode == 0, (r.stdout + r.stderr).decode()[:300]
        output = (r.stdout + r.stderr).decode()
        assert "py-ast-complexity" not in output

    def test_low_complexity_passes(self, tmp_path: Path) -> None:
        """cc=1 函数 + --complexity → 无报错，exit 0。"""
        sample = tmp_path / "low_cc.py"
        sample.write_text(LOW_CC, encoding="utf-8")
        r = _run_cli("check", str(sample), "--complexity")
        assert r.returncode == 0, (r.stdout + r.stderr).decode()[:300]
        output = (r.stdout + r.stderr).decode()
        assert "py-ast-complexity" not in output

    def test_custom_max_cc_threshold(self, tmp_path: Path) -> None:
        """--max-cc 11 → cc=10 函数放行，exit 0。"""
        sample = tmp_path / "high_cc.py"
        sample.write_text(HIGH_CC, encoding="utf-8")
        r = _run_cli("check", str(sample), "--complexity", "--max-cc", "11")
        assert r.returncode == 0, (r.stdout + r.stderr).decode()[:300]
        output = (r.stdout + r.stderr).decode()
        assert "py-ast-complexity" not in output

    def test_non_python_file_skipped(self, tmp_path: Path) -> None:
        """非 Python 文件 + --complexity → 跳过 cc，exit 0。"""
        sample = tmp_path / "app.js"
        sample.write_text("function f(x) { if (x) return 1; return 0; }\n", encoding="utf-8")
        r = _run_cli("check", str(sample), "--complexity", "--lang", "javascript")
        assert r.returncode == 0, (r.stdout + r.stderr).decode()[:300]
        output = (r.stdout + r.stderr).decode()
        assert "py-ast-complexity" not in output

    def test_directory_scan_reports_cc_error(self, tmp_path: Path) -> None:
        """对含 cc=10 函数的目录跑 --complexity → 报出 py-ast-complexity。"""
        sample_dir = tmp_path / "proj"
        sample_dir.mkdir()
        (sample_dir / "high_cc.py").write_text(HIGH_CC, encoding="utf-8")
        r = _run_cli("check", str(sample_dir), "--complexity")
        output = (r.stdout + r.stderr).decode()
        assert "py-ast-complexity" in output
        assert "high_cc" in output
