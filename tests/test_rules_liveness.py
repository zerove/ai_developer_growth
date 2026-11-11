"""自定义规则加载活体测试 (liveness tests).

防止 .adg/rules.yml 自定义规则再次静默失效 (历史事故: 解析器只认
anti_patterns key + `- id:` 开头, 导致 custom_rules 段 8 条 sec 规则
从未生效). 覆盖:
- load_project_config 两条解析路径 (PyYAML / 无 PyYAML fallback)
- fallback 解析器与 PyYAML 的字段一致性
- legacy 双 key 合并 (custom_rules canonical + anti_patterns alias)
- rule_loader / rules_loader / pipeline 三个读取方
- sec-001 收窄模式: 命中动态代码执行, 不命中普通函数调用
- severity_overrides off/ignore/disabled 真禁用 (enabled=False)
- language 过滤: javascript 规则不作用于 python 扫描
- installed_packs 标量列表不污染规则段
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.scripts.adg_cli.check import check_file
from tools.scripts.adg_cli.commands.cmd.cmd_check import _load_and_merge_rules
from tools.scripts.adg_cli.core import load_project_config
from tools.scripts.adg_cli.detect import _simple_yaml_parse
from tools.scripts.rules_engine.rule_loader import load_custom_rules as engine_load_custom_rules
from tools.scripts.rules_engine.validators.pipeline import load_custom_rules as pipeline_load_custom_rules
from tools.scripts.rules_loader.loader import load_custom_rules as legacy_load_custom_rules

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_RULES = REPO_ROOT / ".adg" / "rules.yml"

SEC_IDS = ["sec-001", "sec-002", "sec-003", "sec-004", "sec-005", "sec-101", "sec-102", "sec-103"]


def _isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "no-such-home")


def _make_project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    (proj / ".adg").mkdir(parents=True)
    shutil.copy(REAL_RULES, proj / ".adg" / "rules.yml")
    return proj


def _rule_ids(config: dict[str, Any]) -> list[str]:
    return [r["id"] for r in config.get("custom_rules", [])]


class TestLoadProjectConfigLiveness:
    def test_with_pyyaml_loads_sec_rules(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _isolate_home(tmp_path, monkeypatch)
        proj = _make_project(tmp_path)
        config = load_project_config(proj)
        assert _rule_ids(config) == SEC_IDS
        assert all(r.get("pattern") for r in config["custom_rules"])
        assert all(r.get("language") == "python" or r.get("language") == "javascript" for r in config["custom_rules"])

    def test_without_pyyaml_loads_sec_rules(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _isolate_home(tmp_path, monkeypatch)
        proj = _make_project(tmp_path)
        with_pyyaml = load_project_config(proj)

        monkeypatch.setitem(sys.modules, "yaml", None)
        without_pyyaml = load_project_config(proj)

        assert _rule_ids(without_pyyaml) == SEC_IDS
        for a, b in zip(with_pyyaml["custom_rules"], without_pyyaml["custom_rules"]):
            assert a["id"] == b["id"]
            assert a["pattern"] == b["pattern"]
            assert a["severity"] == b["severity"]
            assert a.get("language") == b.get("language")

    def test_dual_key_merge_not_clobbered(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _isolate_home(tmp_path, monkeypatch)
        proj = tmp_path / "proj"
        (proj / ".adg").mkdir(parents=True)
        (proj / ".adg" / "rules.yml").write_text(
            "custom_rules:\n"
            "- id: from-canonical\n"
            "  severity: error\n"
            "  pattern: aaa\n"
            "  message: m\n"
            "anti_patterns:\n"
            "- id: from-legacy\n"
            "  severity: warning\n"
            "  pattern: bbb\n"
            "  message: m\n",
            encoding="utf-8",
        )
        config = load_project_config(proj)
        assert _rule_ids(config) == ["from-canonical", "from-legacy"]

    def test_legacy_only_key_still_works(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _isolate_home(tmp_path, monkeypatch)
        proj = tmp_path / "proj"
        (proj / ".adg").mkdir(parents=True)
        (proj / ".adg" / "rules.yml").write_text(
            "anti_patterns:\n- id: legacy-only\n  severity: error\n  pattern: x\n  message: m\n",
            encoding="utf-8",
        )
        config = load_project_config(proj)
        assert _rule_ids(config) == ["legacy-only"]


class TestFallbackParserParity:
    def test_fallback_matches_pyyaml_on_real_file(self) -> None:
        fb = _simple_yaml_parse(REAL_RULES)
        ref = yaml.safe_load(REAL_RULES.read_text(encoding="utf-8"))
        assert _rule_ids(fb) == _rule_ids(ref) == SEC_IDS
        for a, b in zip(fb["custom_rules"], ref["custom_rules"]):
            assert a["pattern"] == b["pattern"]
            assert a["severity"] == b["severity"]
            assert a["language"] == b["language"]
            assert a["category"] == b["category"]
        assert fb.get("installed_packs") == ref.get("installed_packs")
        assert set(fb.get("severity_overrides", {})) == set(ref.get("severity_overrides", {}))

    def test_installed_packs_not_captured_as_rules(self) -> None:
        text = (
            "custom_rules:\n"
            "- category: security\n"
            "  id: t-001\n"
            "  pattern: foo\n"
            "  severity: error\n"
            "  message: m\n"
            "installed_packs:\n"
            "- security-essentials\n"
            "severity_overrides:\n"
            "  py-x: info\n"
        )
        p = Path("/tmp/adg_liveness_no_pyyaml.yml")
        p.write_text(text, encoding="utf-8")
        try:
            fb = _simple_yaml_parse(p)
        finally:
            p.unlink(missing_ok=True)
        ref = yaml.safe_load(text)
        assert fb["custom_rules"] == ref["custom_rules"]
        assert fb["installed_packs"] == ["security-essentials"]
        assert fb["severity_overrides"] == {"py-x": "info"}

    def test_empty_file_contract(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yml"
        p.write_text("", encoding="utf-8")
        assert _simple_yaml_parse(p) == {"anti_patterns": []}


class TestSec001Pattern:
    def test_matches_dynamic_code_only(self) -> None:
        import re

        sec001 = re.compile(r"(?<![\w.\"'])(?:eval|exec|__import__)\s*\(")
        assert sec001.search("x = eval('1+1')")
        assert sec001.search("exec(code)")
        assert sec001.search("__import__('os')")
        assert not sec001.search("foo(123)")
        assert not sec001.search("re.compile(r'x')")
        assert not sec001.search("print('hello')")
        assert not sec001.search("my_eval(x)")
        assert not sec001.search("obj.eval(x)")
        assert not sec001.search('s = "eval(x)"')

    def test_e2e_check_file_only_flags_eval(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _isolate_home(tmp_path, monkeypatch)
        proj = _make_project(tmp_path)
        config = load_project_config(proj)
        rules = _load_and_merge_rules("python", None, config)
        f = tmp_path / "sample.py"
        f.write_text("import re\nx = eval('1+1')\nfoo(123)\nre.compile('a')\n", encoding="utf-8")
        issues = [i for i in check_file(f, rules) if i.rule_id == "sec-001"]
        assert len(issues) == 1
        assert issues[0].line == 2


class TestLanguageFilter:
    def test_js_rules_not_applied_to_python(self, monkeypatch: pytest.MonkeyPatch) -> None:
        config = {
            "custom_rules": [
                {"id": "t-py", "language": "python", "severity": "error", "pattern": "aaa", "message": "m"},
                {"id": "t-js", "language": "javascript", "severity": "error", "pattern": "bbb", "message": "m"},
                {"id": "t-any", "severity": "error", "pattern": "ccc", "message": "m"},
            ],
            "severity_overrides": {},
        }
        rules = _load_and_merge_rules("python", None, config)
        ids = {r.get("id") for r in rules["anti_patterns"]}
        assert "t-py" in ids
        assert "t-any" in ids
        assert "t-js" not in ids

        rules_js = _load_and_merge_rules("javascript", None, config)
        ids_js = {r.get("id") for r in rules_js["anti_patterns"]}
        assert "t-js" in ids_js
        assert "t-py" not in ids_js

    def test_real_js_sec_rules_filtered_on_python(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _isolate_home(tmp_path, monkeypatch)
        proj = _make_project(tmp_path)
        config = load_project_config(proj)
        rules = _load_and_merge_rules("python", None, config)
        ids = {r.get("id") for r in rules["anti_patterns"]}
        assert "sec-001" in ids
        assert "sec-101" not in ids
        assert "sec-102" not in ids
        assert "sec-103" not in ids

    def test_dangerous_custom_rule_patterns_are_filtered(self) -> None:
        config = {
            "custom_rules": [
                {"id": "bad-redos", "pattern": "(a+)+$", "message": "x", "severity": "error"},
                {"id": "ok-rule", "pattern": r"TODO", "message": "todo", "severity": "warning"},
                {
                    "id": "bad-exclude",
                    "pattern": r"FIXME",
                    "exclude_pattern": "(a|aa)+$",
                    "message": "fixme",
                    "severity": "warning",
                },
            ],
            "severity_overrides": {},
        }
        rules = _load_and_merge_rules("python", None, config)
        ids = {r.get("id") for r in rules["anti_patterns"]}
        assert "bad-redos" not in ids
        assert "ok-rule" in ids
        assert "bad-exclude" in ids
        bad_exclude = next(r for r in rules["anti_patterns"] if r.get("id") == "bad-exclude")
        assert "exclude_pattern" not in bad_exclude


class TestOffDisablesRule:
    def _os_system_config(self, overrides: dict[str, str]) -> dict[str, Any]:
        return {
            "custom_rules": [
                {
                    "id": "t-os-system",
                    "severity": "error",
                    "category": "security",
                    "pattern": r"\bos\.system\s*\(",
                    "message": "os.system",
                    "language": "python",
                }
            ],
            "severity_overrides": overrides,
        }

    def test_off_sets_enabled_false(self) -> None:
        rules = _load_and_merge_rules("python", None, self._os_system_config({"t-os-system": "off"}))
        rule = next(r for r in rules["anti_patterns"] if r.get("id") == "t-os-system")
        assert rule.get("enabled") is False

    def test_off_case_insensitive_and_aliases(self) -> None:
        for value in ("OFF", "Ignore", "disabled"):
            rules = _load_and_merge_rules("python", None, self._os_system_config({"t-os-system": value}))
            rule = next(r for r in rules["anti_patterns"] if r.get("id") == "t-os-system")
            assert rule.get("enabled") is False, value

    def test_normal_severity_override_still_applies(self) -> None:
        rules = _load_and_merge_rules("python", None, self._os_system_config({"t-os-system": "warning"}))
        rule = next(r for r in rules["anti_patterns"] if r.get("id") == "t-os-system")
        assert rule["severity"] == "warning"
        assert rule.get("enabled") is not False

    def test_disabled_rule_produces_no_issues(self, tmp_path: Path) -> None:
        f = tmp_path / "danger.py"
        f.write_text("import os\nos.system('ls')\n", encoding="utf-8")

        rules_on = _load_and_merge_rules("python", None, self._os_system_config({}))
        assert any(i.rule_id == "t-os-system" for i in check_file(f, rules_on))

        rules_off = _load_and_merge_rules("python", None, self._os_system_config({"t-os-system": "off"}))
        assert not any(i.rule_id == "t-os-system" for i in check_file(f, rules_off))

    def test_real_rules_disable_py_missing_all_and_print(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _isolate_home(tmp_path, monkeypatch)
        proj = _make_project(tmp_path)
        config = load_project_config(proj)
        rules = _load_and_merge_rules("python", None, config)
        by_id = {r.get("id"): r for r in rules["anti_patterns"]}
        assert by_id["py-missing-all"].get("enabled") is False
        assert by_id["py-print-statement"].get("enabled") is False


class TestAllRuleReadersAcceptCustomRulesKey:
    def test_engine_rule_loader(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _isolate_home(tmp_path, monkeypatch)
        proj = tmp_path / "proj"
        (proj / ".adg").mkdir(parents=True)
        (proj / ".adg" / "rules.yml").write_text(
            "custom_rules:\n- id: t-eng\n  severity: error\n  pattern: xyzabc\n  message: m\n",
            encoding="utf-8",
        )
        custom = engine_load_custom_rules(proj)
        assert "t-eng" in [r.get("id") for r in custom["anti_patterns"]]

    def test_legacy_rules_loader(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        (proj / ".ai-rules").mkdir(parents=True)
        (proj / ".ai-rules" / "extra.yml").write_text(
            "custom_rules:\n- id: t-leg\n  severity: warning\n  pattern: qqq\n  message: m\n",
            encoding="utf-8",
        )
        merged = legacy_load_custom_rules(proj)
        assert "t-leg" in [r.get("id") for r in merged.get("anti_patterns", [])]

    def test_pipeline_rule_loader(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        (proj / ".ai-rules").mkdir(parents=True)
        (proj / ".ai-rules" / "extra.yml").write_text(
            "custom_rules:\n- id: t-pipe\n  severity: warning\n  pattern: www\n  message: m\n",
            encoding="utf-8",
        )
        custom = pipeline_load_custom_rules(proj)
        assert "t-pipe" in [r.get("id") for r in custom["anti_patterns"]]
