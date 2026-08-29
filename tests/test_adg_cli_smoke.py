"""V3: ADG CLI 子命令 smoke 测试（真实进程端到端）。

用 subprocess 跑 ``python -m tools.scripts.adg_cli <cmd>``，
验证各只读子命令在真实解释器下可执行、退出码符合预期。
覆盖：list-rules / detect / rule validate / marketplace list /
check（含 --exclude-tests 新参数）/ report / trend / recommend / html-report。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run_cli(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[bytes]:
    """以仓库根为 cwd 运行 CLI，返回 CompletedProcess。"""
    return subprocess.run(
        [PY, "-m", "tools.scripts.adg_cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=timeout,
    )


class TestCliSmoke:
    def test_help_ok(self) -> None:
        r = _run_cli("--help")
        assert r.returncode == 0
        assert b"check" in r.stdout

    def test_list_rules_python(self) -> None:
        r = _run_cli("list-rules", "--lang", "python")
        assert r.returncode == 0, r.stderr.decode()[:300]
        # 输出应包含已知规则 id
        assert "py-bare-except" in r.stdout.decode()

    def test_list_rules_ruby(self) -> None:
        """V2 新语言规则清单可列出。"""
        r = _run_cli("list-rules", "--lang", "ruby")
        assert r.returncode == 0, r.stderr.decode()[:300]

    def test_list_rules_php(self) -> None:
        """V2 新语言规则清单可列出。"""
        r = _run_cli("list-rules", "--lang", "php")
        assert r.returncode == 0, r.stderr.decode()[:300]

    def test_detect_on_repo(self) -> None:
        r = _run_cli("detect")
        assert r.returncode == 0, r.stderr.decode()[:300]
        assert "python" in r.stdout.decode().lower()

    def test_rule_validate_builtin(self) -> None:
        """rule validate 校验内置规则文件通过。"""
        rules_file = REPO_ROOT / "ai-dev-framework" / "languages" / "python" / "rules.d" / "anti_patterns.yml"
        r = _run_cli("rule", "validate", str(rules_file))
        assert r.returncode == 0, r.stderr.decode()[:500]

    def test_marketplace_list(self) -> None:
        r = _run_cli("marketplace", "list")
        assert r.returncode == 0, r.stderr.decode()[:300]

    def test_check_sample_exit_code(self, tmp_path: Path) -> None:
        """含真实裸 except 的文件 → error → exit 1。"""
        sample = tmp_path / "bad.py"
        sample.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")
        r = _run_cli("check", str(sample))
        assert r.returncode == 1
        output = (r.stdout + r.stderr).decode()
        assert "py-bare-except" in output

    def test_check_exclude_tests_flag(self, tmp_path: Path) -> None:
        """--exclude-tests 排除测试目录后 exit 0。"""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_bad.py").write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")
        src = tmp_path / "good.py"
        src.write_text("x = 1\n", encoding="utf-8")

        r_no_flag = _run_cli("check", str(tmp_path), "--lang", "python")
        assert r_no_flag.returncode == 1  # 测试目录中的裸 except 被检出

        r_flag = _run_cli("check", str(tmp_path), "--lang", "python", "--exclude-tests")
        assert r_flag.returncode == 0, (r_flag.stdout + r_flag.stderr).decode()[:300]

    def test_check_exclude_glob(self, tmp_path: Path) -> None:
        """--exclude glob 可排除指定路径。"""
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "bad.py").write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")
        r = _run_cli("check", str(tmp_path), "--lang", "python", "--exclude", "vendor/*")
        assert r.returncode == 0, (r.stdout + r.stderr).decode()[:300]

    def test_check_json_output_schema(self, tmp_path: Path) -> None:
        """--json 输出包含 summary 与 issues 结构。"""
        import json as jsonlib

        src = tmp_path / "m.py"
        src.write_text("x = 1\n", encoding="utf-8")
        r = _run_cli("check", str(src), "--lang", "python", "--json")
        data = jsonlib.loads(r.stdout)
        assert "summary" in data
        assert set(data["summary"].keys()) >= {"error", "warning", "info"}
        assert isinstance(data.get("issues", []), list)

    def test_report_generates_markdown(self, tmp_path: Path) -> None:
        """report 命令生成报告文件。"""
        r = _run_cli("report", str(tmp_path))
        # 报告命令对空项目也应正常退出(0 或 1 均可接受, 但不能崩溃回 traceback)
        assert r.returncode in (0, 1)
        assert "Traceback" not in r.stderr.decode()

    def test_html_report_smoke(self, tmp_path: Path) -> None:
        """html-report 命令不崩溃。"""
        r = _run_cli("html-report", str(tmp_path), "-o", str(tmp_path / "r.html"))
        assert r.returncode in (0, 1)
        assert "Traceback" not in r.stderr.decode()

    def test_trend_smoke_empty_history(self) -> None:
        """trend 对无历史数据不崩溃。"""
        r = _run_cli("trend")
        assert r.returncode in (0, 1)
        assert "Traceback" not in r.stderr.decode()

    def test_recommend_smoke(self, tmp_path: Path) -> None:
        """recommend 对小型样本不崩溃。"""
        src = tmp_path / "s.py"
        src.write_text("def f():\n    return 1\n", encoding="utf-8")
        r = _run_cli("recommend", str(src))
        assert r.returncode in (0, 1)
        assert "Traceback" not in r.stderr.decode()


@pytest.mark.parametrize(
    "args",
    [
        ["list-rules", "--lang", "python"],
        ["detect"],
    ],
)
class TestCliSmokeFast:
    def test_commands_complete_quickly(self, args: list[str]) -> None:
        """只读命令应在超时内完成（防卡死回归）。"""
        r = _run_cli(*args, timeout=60)
        assert r.returncode == 0, r.stderr.decode()[:300]


@pytest.mark.parametrize(
    "cmd",
    [
        "bench",
        "cicd",
        "dashboard",
        "fix",
        "html-report",
        "install-hooks",
        "list-rules",
        "lsp",
        "monorepo",
        "notify",
        "pattern-learner",
    ],
)
def test_uncovered_cmd_help_ok(cmd: str) -> None:
    """全 23 cmd 的 --help 不崩溃 (V2.15 补全 11 个 smoke 缺失 cmd)。

    目的: 防止子命令注册/import 错误导致 argparse 阶段崩溃。
    真实业务逻辑在各自 test_<cmd>.py 单测覆盖, 这里只做\"可执行性\"验证。
    """
    r = _run_cli(cmd, "--help", timeout=30)
    assert r.returncode == 0, f"{cmd} --help 失败: {r.stderr.decode()[:300]}"
    # --help 应输出 Usage 之类文本
    out = r.stdout.decode()
    assert "Usage" in out or "usage" in out or "options" in out or "Commands" in out
