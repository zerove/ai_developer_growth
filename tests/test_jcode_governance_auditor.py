"""测试 .jcode/scripts/governance-auditor.py（审计主入口，此前仅 24% 覆盖）。

该文件承载 UNSAFE_PATTERNS 安全模式与文档绝对化声明审计，由
quality-gates.yml 的 governance-audit 调用。

本轮在补测试时发现并修复的真实缺陷（见 test_no_pattern_is_dead_rule）：
yaml.load 那条规则的 exclude_pattern 与 pattern 完全相同，而
_check_unsafe_patterns 先判 exclude 再判 pattern，导致排除永远先命中并
continue —— 该规则从建立起就从未触发过。

隔离要求：涉及文件系统的函数必须把 get_project_root 指向 tmp_path，
禁止写真实 docs/efficiency/。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = ROOT / ".jcode" / "scripts"


@pytest.fixture(scope="module")
def ga():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("jcode_gov_auditor", _SCRIPTS / "governance-auditor.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pattern_of(ga, needle: str):
    return next(p for p in ga.UNSAFE_PATTERNS if needle in p.pattern)


# ── 死规则防护（本轮修复的核心） ────────────────────────────────────


class TestNoDeadRule:
    def test_no_pattern_is_dead(self, ga) -> None:
        """exclude_pattern 与 pattern 相同时，该规则永不触发。

        _check_unsafe_patterns 先判 exclude 再判 pattern，两者相同 ⇒
        排除必然先命中并 continue ⇒ 命中判定执行不到。
        """
        dead = [p.desc for p in ga.UNSAFE_PATTERNS if p.exclude_pattern is not None and p.exclude_pattern == p.pattern]
        assert not dead, f"这些安全规则永远不会触发: {dead}"

    def test_every_rule_can_actually_fire(self, ga) -> None:
        """每条规则都必须能被一个最小样本触发，否则等于没有这道门禁。"""
        samples = {
            "eval": "eval(x)",
            "exec": "exec(x)",
            "os.system": "os.system(x)",
            "pickle": "pickle.loads(x)",
            "yaml.load": "yaml.load(f)",
        }
        for pat in ga.UNSAFE_PATTERNS:
            needle = next((k for k in samples if k.split(".")[0] in pat.pattern), None)
            assert needle, f"未找到 {pat.pattern} 的样本，无法验证其可触发"
            fired = ga._check_unsafe_patterns(samples[needle], [pat], "candidate.py")
            assert fired == [pat.desc], f"{pat.pattern} 对 {samples[needle]!r} 未触发（死规则？）"

    def test_yaml_load_now_detected(self, ga) -> None:
        pat = _pattern_of(ga, "yaml")
        assert ga._check_unsafe_patterns("yaml.load(f)", [pat], "a.py") == [pat.desc]

    @pytest.mark.parametrize(
        "code",
        ["yaml.safe_load(f)", "yaml.load(f, Loader=yaml.SafeLoader)", "x = 'yaml.load'"],
    )
    def test_yaml_load_safe_forms_not_flagged(self, ga, code: str) -> None:
        pat = _pattern_of(ga, "yaml")
        assert ga._check_unsafe_patterns(code, [pat], "a.py") == []

    def test_yaml_load_literal_files_excluded(self, ga) -> None:
        """规则定义文件里描述该模式的字符串字面量不应误报。"""
        pat = _pattern_of(ga, "yaml")
        for fname in ("auto_fix.py", "hallucination_detector.py"):
            code = '"message": "yaml.load() without Loader is unsafe"'
            assert ga._check_unsafe_patterns(code, [pat], fname) == [], f"{fname} 被误报"


class TestCheckUnsafePatterns:
    def test_detects_plain_match(self, ga) -> None:
        pat = _pattern_of(ga, "eval")
        assert ga._check_unsafe_patterns("eval(x)", [pat], "safe.py") == [pat.desc]

    def test_exclude_files_suppresses(self, ga) -> None:
        pat = _pattern_of(ga, "eval")
        assert ga._check_unsafe_patterns("eval(x)", [pat], "auto_fix.py") == []

    def test_exclude_files_matches_basename_only(self, ga) -> None:
        """排除按文件名生效，目录前缀不应影响判定。"""
        pat = _pattern_of(ga, "eval")
        assert ga._check_unsafe_patterns("eval(x)", [pat], "deep/nested/auto_fix.py") == []

    def test_empty_filepath_still_detects(self, ga) -> None:
        pat = _pattern_of(ga, "eval")
        assert ga._check_unsafe_patterns("eval(x)", [pat], "") == [pat.desc]

    def test_exclude_pattern_suppresses_whole_file(self, ga) -> None:
        pat = ga.UnsafePattern(pattern=r"TODO", desc="d", exclude_files=[], exclude_pattern=r"# noqa")
        assert ga._check_unsafe_patterns("# noqa\nTODO: x", [pat], "a.py") == []
        assert ga._check_unsafe_patterns("TODO: x", [pat], "a.py") == ["d"]

    def test_multiple_patterns_all_reported(self, ga) -> None:
        risks = ga._check_unsafe_patterns("eval(x)\nos.system(y)", ga.UNSAFE_PATTERNS, "a.py")
        assert len(risks) == 2

    def test_clean_content_returns_empty(self, ga) -> None:
        assert ga._check_unsafe_patterns("print('hi')", ga.UNSAFE_PATTERNS, "a.py") == []


# ── 文档绝对化声明 ──────────────────────────────────────────────────


class TestDocSkippableLine:
    @pytest.mark.parametrize("line", ["# 标题", "## 二级", "```python", "```", "| a | b |", "← 回退", "   # 缩进标题"])
    def test_skipped(self, ga, line: str) -> None:
        assert ga._is_doc_skippable_line(line) is True

    @pytest.mark.parametrize("line", ["这是永远 100% 的声明", "普通正文", "- 列表项"])
    def test_not_skipped(self, ga, line: str) -> None:
        assert ga._is_doc_skippable_line(line) is False


class TestMatchDocAbsoluteClaims:
    PATTERNS = [
        (r"永远\s*100%", "永远100%"),
        (r"绝对(?!化)", "绝对"),
        (r"从不", "从不"),
    ]

    def test_detects(self, ga) -> None:
        assert ga._match_doc_absolute_claims("这个方案永远 100% 有效", self.PATTERNS) == ["永远100%"]

    @pytest.mark.parametrize("hedge", ["例外情况另行说明", "除非失败否则可用"])
    def test_hedged_claims_excluded(self, ga, hedge: str) -> None:
        """含"例外/除非"的行属合理限定，不应报告。"""
        assert ga._match_doc_absolute_claims(f"它绝对可靠，{hedge}", self.PATTERNS) == []

    def test_huafahua_not_matched(self, ga) -> None:
        """'绝对化' 是术语而非绝对化声明，负向断言须生效。"""
        assert ga._match_doc_absolute_claims("需要绝对化处理", self.PATTERNS) == []

    def test_multiple_hits_same_line(self, ga) -> None:
        got = ga._match_doc_absolute_claims("它绝对且从不失败", self.PATTERNS)
        assert set(got) == {"绝对", "从不"}


# ── 语言解析 ────────────────────────────────────────────────────────


class TestParseLanguages:
    def test_single(self, ga) -> None:
        assert len(ga._parse_languages("python")) == 1

    def test_multiple_and_whitespace(self, ga) -> None:
        assert len(ga._parse_languages(" python , rust ,  go ")) == 3

    def test_empty_yields_empty(self, ga) -> None:
        assert ga._parse_languages("") == []
        assert ga._parse_languages("  ,  ") == []

    def test_unknown_is_skipped_not_fatal(self, ga) -> None:
        """未知语言必须跳过而不是抛错——否则一个笔误会中断审计。"""
        assert len(ga._parse_languages("python, notalanguage")) == 1


# ── 文件系统路径（隔离到 tmp_path） ────────────────────────────────


class TestDocScanIsolated:
    def test_scan_reads_only_under_root(self, ga, tmp_path: Path) -> None:
        d = tmp_path / "docs" / "efficiency"
        d.mkdir(parents=True)
        (d / "a.md").write_text("它永远 100% 可靠\n", encoding="utf-8")
        (d / "b.md").write_text("# 它永远 100% 可靠\n", encoding="utf-8")
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            risks = ga._scan_doc_absolute_claims()
        assert risks, "正文中的绝对化声明应被检出"
        assert all("b.md" not in r for r in risks), f"标题行应被跳过: {risks}"
        assert any("a.md" in r for r in risks)

    def test_one_line_can_match_several_patterns(self, ga, tmp_path: Path) -> None:
        """'永远 100%' 同时命中 '永远\\s*100%' 与 '永远'，两个都要报。"""
        d = tmp_path / "docs" / "efficiency"
        d.mkdir(parents=True)
        (d / "a.md").write_text("它永远 100% 可靠\n", encoding="utf-8")
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            risks = ga._scan_doc_absolute_claims()
        assert len(risks) == 2, f"同一行应按命中 pattern 数分别报告: {risks}"

    def test_missing_dir_returns_empty(self, ga, tmp_path: Path) -> None:
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            assert ga._scan_doc_absolute_claims() == []


class TestAiQualityGateNonBlocking:
    def test_missing_script_is_non_blocking(self, ga, tmp_path: Path) -> None:
        """缺脚本时返回 True（显式非阻断），不是静默通过。"""
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            assert ga.ai_quality_gate() is True


# ── 审计驱动函数（隔离 + 打桩） ────────────────────────────────────


class TestValidateGovernanceDocs:
    def test_delegates_to_validator_script(self, ga) -> None:
        with patch.object(ga, "run_command", return_value=(0, "ok")) as rc:
            assert ga.validate_governance_docs() is True
        cmd = rc.call_args[0][0]
        assert any("governance-docs-validator" in str(a) for a in cmd)
        assert "validate" in cmd

    def test_nonzero_exit_is_failure(self, ga) -> None:
        with patch.object(ga, "run_command", return_value=(1, "缺少字段")):
            assert ga.validate_governance_docs() is False

    def test_output_is_surfaced(self, ga, capsys) -> None:
        with patch.object(ga, "run_command", return_value=(1, "问题明细")):
            ga.validate_governance_docs()
        assert "问题明细" in capsys.readouterr().out


class TestCheckAiSdlcCompliance:
    def _mk(self, tmp_path: Path, ci: str | None, pyproject: str | None, precommit: bool = False) -> None:
        if ci is not None:
            p = tmp_path / ".github" / "workflows"
            p.mkdir(parents=True, exist_ok=True)
            (p / "ci.yml").write_text(ci, encoding="utf-8")
        if pyproject is not None:
            (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        if precommit:
            (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

    def test_missing_ci_is_reported(self, ga, tmp_path: Path) -> None:
        self._mk(tmp_path, None, "[tool.pytest]\n")
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            with patch.object(ga, "run_command", return_value=(0, "")):
                assert ga.check_ai_sdlc_compliance() is False

    def test_incomplete_ci_lists_jobs(self, ga, tmp_path: Path) -> None:
        self._mk(tmp_path, "jobs:\n  lint:\n", "[tool.pytest]\n", precommit=True)
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            with patch.object(ga, "run_command", return_value=(0, "")):
                assert ga.check_ai_sdlc_compliance() is False

    def test_missing_precommit_config_fails(self, ga, tmp_path: Path) -> None:
        """CI 与 pytest 齐备但缺 .pre-commit-config.yaml 仍须判不合规。"""
        self._mk(tmp_path, "pre-commit lint type-check test\n", "[tool.pytest]\n")
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            with patch.object(ga, "run_command", return_value=(0, "")):
                assert ga.check_ai_sdlc_compliance() is False

    def test_complete_config_passes(self, ga, tmp_path: Path) -> None:
        self._mk(tmp_path, "pre-commit lint type-check test\n", "[tool.pytest]\n", precommit=True)
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            with patch.object(ga, "run_command", return_value=(0, "")):
                assert ga.check_ai_sdlc_compliance() is True

    def test_pyproject_without_pytest_fails(self, ga, tmp_path: Path) -> None:
        self._mk(tmp_path, "pre-commit lint type-check test\n", "[project]\nname='x'\n", precommit=True)
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            with patch.object(ga, "run_command", return_value=(0, "")):
                assert ga.check_ai_sdlc_compliance() is False


class TestUnsafeCodeScan:
    def test_empty_project_has_no_risks(self, ga, tmp_path: Path) -> None:
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            with patch.object(ga, "_EXCLUDE_FROM_UNSAFE_AUDIT", set()):
                assert ga._scan_unsafe_code_risks() == []

    def test_detects_real_unsafe_call(self, ga, tmp_path: Path) -> None:
        # _scan_unsafe_code_risks 只遍历 tools/scripts，不扫任意目录
        d = tmp_path / "tools" / "scripts"
        d.mkdir(parents=True)
        (d / "bad.py").write_text("eval(x)\n", encoding="utf-8")
        with patch.object(ga, "get_project_root", return_value=tmp_path):
            with patch.object(ga, "_EXCLUDE_FROM_UNSAFE_AUDIT", set()):
                risks = ga._scan_unsafe_code_risks()
        assert any("bad.py" in r for r in risks), f"应检出 bad.py，实际: {risks}"
