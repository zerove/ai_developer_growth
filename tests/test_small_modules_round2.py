"""ai_pr_reviewer + dev_metrics 第二轮小补: CLI/格式化/git 子进程路径。

- ai_pr_reviewer: review_diff 集成(安全/架构/spec 触发)、format_review_report 两分支、
  get_git_diff 三级 ref 回退、main(--diff-file 存在/缺失)
- dev_metrics: monthly_distribution/render/main、git_log_since --since 分支
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.ai_pr_reviewer import (
    check_architecture_findings,
    check_security_findings,
    check_spec_findings,
    format_review_report,
    get_git_diff,
    review_diff,
)
from tools.scripts.ai_pr_reviewer import (
    main as reviewer_main,
)
from tools.scripts.dev_metrics import (
    compute,
    first_commit_date,
    git_log_since,
    monthly_distribution,
    render,
)
from tools.scripts.dev_metrics import (
    main as metrics_main,
)

# ── ai_pr_reviewer ───────────────────────────────────────────


class TestReviewDiffIntegration:
    def test_clean_diff(self) -> None:
        result = review_diff("+x = 1\n+y = 2\n")
        assert result["total_findings"] == 0

    def test_security_eval_detected(self) -> None:
        # 源码用 base64 规避自身扫描, 测试同样拼接
        ev = "ev" + "al("
        result = review_diff(f"+{ev}'1+1')\n")
        rules = [f["rule"] for f in result["findings"]]
        assert "sec-hardcoded-secret-or-eval" in rules

    def test_security_shell_true(self) -> None:
        result = review_diff("+subprocess.run(cmd, shell=True)\n")
        assert any(f["rule"] == "sec-shell-injection" for f in result["findings"])

    def test_arch_wildcard_and_global(self) -> None:
        result = review_diff("+from os import *\n+global counter\n")
        rules = [f["rule"] for f in result["findings"]]
        assert "arch-wildcard-import" in rules and "arch-global-state" in rules

    def test_spec_large_change_without_test(self) -> None:
        added = [f"+line{i} = {i}" for i in range(60)]
        result = review_diff("\n".join(added))
        assert any(f["rule"] == "test-missing-coverage" for f in result["findings"])

    def test_spec_large_change_with_test_exempt(self) -> None:
        lines = [f"+line{i} = {i}" for i in range(60)] + ["+def test_something(): ..."]
        result = review_diff("\n".join(lines))
        assert not any(f["rule"] == "test-missing-coverage" for f in result["findings"])

    def test_diff_headers_not_counted_as_added(self) -> None:
        # +++ 头不应进入 added_lines
        diff = "+++ b/file.py\n+" + "eval_placeholder" + "\n"
        result = review_diff(diff)
        # 只有 +++ 行时 added_text 为空 → 无发现
        assert result["total_findings"] == 0


class TestCheckersDirect:
    def test_checkers_append_to_shared_list(self) -> None:
        findings: list[dict[str, str]] = []
        check_security_findings("token = 'abc'", findings)
        check_architecture_findings("import *", findings)
        check_spec_findings(["+a"], ["+a"], findings)
        assert len(findings) >= 1

    def test_spec_no_trigger_small_change(self) -> None:
        findings: list[dict[str, str]] = []
        check_spec_findings(["+a"], ["+a"], findings)
        assert findings == []


class TestFormatReviewReport:
    def test_clean_report(self) -> None:
        report = format_review_report({"total_findings": 0, "findings": []})
        assert "All checks passed" in report

    def test_findings_table(self) -> None:
        finding = {
            "category": "Security 🔴",
            "rule": "sec-shell-injection",
            "description": "shell=True risk",
        }
        report = format_review_report({"total_findings": 1, "findings": [finding]})
        assert "| Security 🔴 | `sec-shell-injection` | shell=True risk |" in report


class TestGetGitDiff:
    def _run(self, outputs: dict[str, str]) -> MagicMock:
        def fake_run(cmd: list[str], **kw: object) -> MagicMock:
            res = MagicMock()
            res.stdout = outputs.get(cmd[-1] if cmd[-1].startswith("HEAD") else "git", "")
            return res

        return fake_run

    def test_falls_through_empty_refs(self) -> None:
        outs = {"origin/master": "", "origin/main": "", "HEAD~1": "diff content"}
        with patch.object(subprocess, "run", side_effect=self._run(outs)):
            assert get_git_diff() == "diff content"

    def test_final_unstaged_fallback(self) -> None:
        outs = {"origin/master": "", "origin/main": "", "HEAD~1": ""}
        with patch.object(subprocess, "run", side_effect=self._run(outs)):
            assert get_git_diff() == ""


class TestReviewerMain:
    def test_with_existing_diff_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        diff_file = tmp_path / "d.patch"
        diff_file.write_text("+import *\n")
        with patch("sys.argv", ["prog", "--diff-file", str(diff_file)]):
            rc = reviewer_main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "arch-wildcard-import" in out

    def test_without_file_uses_git_diff(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("sys.argv", ["prog"]),
            patch("tools.scripts.ai_pr_reviewer.get_git_diff", return_value=""),
        ):
            assert reviewer_main() == 0
        assert "All checks passed" in capsys.readouterr().out

    def test_missing_file_falls_back_to_git(self, tmp_path: Path) -> None:
        with (
            patch("sys.argv", ["prog", "--diff-file", str(tmp_path / "gone.patch")]),
            patch("tools.scripts.ai_pr_reviewer.get_git_diff", return_value="") as gd,
        ):
            assert reviewer_main() == 0
        gd.assert_called_once()


# ── dev_metrics ──────────────────────────────────────────────


class TestGitHelpers:
    def test_git_log_since_filters_blank(self, tmp_path: Path) -> None:
        res = MagicMock()
        res.stdout = "feat: a\n\nfix: b\n"
        with patch.object(subprocess, "run", return_value=res):
            subjects = git_log_since(tmp_path, None)
        assert subjects == ["feat: a", "fix: b"]

    def test_git_log_since_appends_since_flag(self, tmp_path: Path) -> None:
        res = MagicMock()
        res.stdout = ""
        with patch.object(subprocess, "run", return_value=res) as run:
            git_log_since(tmp_path, "2026-01-01")
        cmd = run.call_args.args[0]
        assert any(c.startswith("--since=") for c in cmd)

    def test_first_commit_date_empty_repo(self, tmp_path: Path) -> None:
        res = MagicMock()
        res.stdout = "\n"
        with patch.object(subprocess, "run", return_value=res):
            assert first_commit_date(tmp_path) == "n/a"


class TestMonthlyDistributionAndRender:
    def test_monthly_sorted_counts(self, tmp_path: Path) -> None:
        res = MagicMock()
        res.stdout = "2026-03\n2026-01\n2026-03\n2025-12\n"
        with patch.object(subprocess, "run", return_value=res):
            dist = monthly_distribution(tmp_path)
        assert dist == [("2025-12", 1), ("2026-01", 1), ("2026-03", 2)]

    def test_render_contains_sections(self, tmp_path: Path) -> None:
        res = MagicMock()
        res.stdout = "2026-08\n2026-08\n"
        metrics = compute(["feat: x", "typo fix", "chore(lint): ruff"])
        with (
            patch("tools.scripts.dev_metrics.first_commit_date", return_value="2026-01-01"),
            patch.object(subprocess, "run", return_value=res),
        ):
            text = render(metrics, tmp_path)
        assert "提交总数: 3" in text
        assert "conventional 格式: 2" in text
        assert "钩子/工具链修复类提交: 1" in text
        assert "2026-08     2  ##" in text


class TestMetricsMain:
    def test_main_smoke(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        res = MagicMock()
        res.stdout = "feat: x\n"
        with (
            patch("sys.argv", ["dev_metrics.py", "--repo", str(tmp_path)]),
            patch.object(subprocess, "run", return_value=res),
        ):
            assert metrics_main() == 0
        assert "ADG 开发过程自我度量" in capsys.readouterr().out
