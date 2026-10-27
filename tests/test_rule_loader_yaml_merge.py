"""Tests for rule_loader yaml/merge 系列 (Phase 32 子任务 2d).

覆盖:
- _load_common_rules_cached: 文件缺失/合法/YAML 错/YAML 非 dict
- _load_universal_rules_cached: universal + common 合并
- _try_load_yaml: ImportError + 文件缺失 + YAML 错 + 合并 common
- _merge_rules: 全替换 + severity_override + 嵌套 dict 合并
- _merge_anti_patterns: ID 覆盖 + severity_override + 追加新

详见 ADR-034 Phase 32 子任务 2d 设计。

设计要点:
- 测试用真实 yaml.safe_load (避免 mock yaml 库的复杂性)
- 每个 LRU cache 测试前清空缓存
- 真实 .yml 文件在 tmp_path 创建
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.scripts.rules_engine.rule_loader import (
    _load_common_rules_cached,
    _load_universal_rules_cached,
    _merge_anti_patterns,
    _merge_common_rules,
    _merge_rules,
    _try_load_yaml,
)


@pytest.fixture(autouse=True)
def _clear_lru_cache() -> None:
    """清空 _load_*_rules_cached 的 LRU cache (避免跨测试污染)。"""
    _load_common_rules_cached.cache_clear()
    _load_universal_rules_cached.cache_clear()
    yield
    _load_common_rules_cached.cache_clear()
    _load_universal_rules_cached.cache_clear()


@pytest.fixture
def framework_with_common(tmp_path: Path) -> Path:
    """创建 framework_dir 含 common/security.yml。"""
    common = tmp_path / "common"
    common.mkdir()
    (common / "security.yml").write_text(
        """
security_rules:
  - id: sec-001
    severity: error
naming: {}
""".strip()
    )
    return tmp_path


@pytest.fixture
def framework_with_universal(tmp_path: Path) -> Path:
    """创建 framework_dir 含 common/universal.yml。"""
    common = tmp_path / "common"
    common.mkdir()
    (common / "universal.yml").write_text(
        """
anti_patterns:
  - id: u-001
    severity: warning
thresholds:
  max_complexity: 10
""".strip()
    )
    return tmp_path


@pytest.fixture
def framework_with_both(tmp_path: Path) -> Path:
    """framework_dir 同时含 common/security.yml + common/universal.yml。"""
    common = tmp_path / "common"
    common.mkdir()
    (common / "security.yml").write_text("naming: {}\n")
    (common / "universal.yml").write_text(
        """
anti_patterns:
  - id: u-001
thresholds:
  max_complexity: 5
""".strip()
    )
    return tmp_path


class TestLoadCommonRulesCached:
    """_load_common_rules_cached() yaml 加载 + 兜底。"""

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """common/security.yml 不存在 → {} (兜底)。"""
        result = _load_common_rules_cached(str(tmp_path))
        assert result == {}

    def test_valid_yaml_returns_dict(self, framework_with_common: Path) -> None:
        """合法 YAML → dict。"""
        result = _load_common_rules_cached(str(framework_with_common))
        assert "security_rules" in result
        assert result["security_rules"][0]["id"] == "sec-001"

    def test_invalid_yaml_returns_empty(self, tmp_path: Path) -> None:
        """YAML 语法错 → {} (兜底, 不抛异常)。"""
        common = tmp_path / "common"
        common.mkdir()
        (common / "security.yml").write_text(": invalid : yaml [")
        result = _load_common_rules_cached(str(tmp_path))
        assert result == {}

    def test_yaml_list_returns_empty(self, tmp_path: Path) -> None:
        """YAML 顶层是 list (非 dict) → {} (类型检查兜底)。"""
        common = tmp_path / "common"
        common.mkdir()
        (common / "security.yml").write_text("- item1\n- item2\n")
        result = _load_common_rules_cached(str(tmp_path))
        assert result == {}

    def test_empty_yaml_returns_empty(self, tmp_path: Path) -> None:
        """空文件 → {} (yaml.safe_load 返回 None, isinstance(dict) 失败)。"""
        common = tmp_path / "common"
        common.mkdir()
        (common / "security.yml").write_text("")
        result = _load_common_rules_cached(str(tmp_path))
        assert result == {}


class TestLoadUniversalRulesCached:
    """_load_universal_rules_cached() universal + common 合并。"""

    def test_universal_only(self, framework_with_universal: Path) -> None:
        """只有 universal.yml → 返回 universal (默认空 dict 不存在时填充默认值会被覆盖)。"""
        result = _load_universal_rules_cached(str(framework_with_universal))
        assert result["anti_patterns"][0]["id"] == "u-001"
        assert result["thresholds"]["max_complexity"] == 10

    def test_no_universal_no_common(self, tmp_path: Path) -> None:
        """两者都不存在 → 默认空 dict 结构 (来自 result: dict[str, Any] = {...})。"""
        result = _load_universal_rules_cached(str(tmp_path))
        assert result == {
            "anti_patterns": [],
            "thresholds": {},
            "naming": {},
        }

    def test_universal_and_common_merged(self, framework_with_both: Path) -> None:
        """universal + common 都存在 → 合并 (common 在 universal 之上)。"""
        result = _load_universal_rules_cached(str(framework_with_both))
        assert "anti_patterns" in result
        # universal.yml 的 thresholds 保留
        assert result["thresholds"]["max_complexity"] == 5
        # _merge_rules 只合并 anti_patterns/naming/thresholds,
        # common.security_rules 顶层 key 不会出现在 result 中
        # (因为 _load_universal_rules_cached 不合并 security_rules)

    def test_universal_invalid_yaml_ignored(self, tmp_path: Path) -> None:
        """universal.yml 语法错 → 忽略, 用默认结构。"""
        common = tmp_path / "common"
        common.mkdir()
        (common / "universal.yml").write_text(": bad [")
        result = _load_universal_rules_cached(str(tmp_path))
        assert result == {
            "anti_patterns": [],
            "thresholds": {},
            "naming": {},
        }


class TestTryLoadYaml:
    """_try_load_yaml() 多分支 + common 合并。"""

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        """文件不存在 → None (调用方会走 fallback)。"""
        result = _try_load_yaml(
            tmp_path / "rules.yml",
            framework_dir=tmp_path,
        )
        assert result is None

    def test_valid_yaml_loaded_with_common_merged(self, framework_with_common: Path) -> None:
        """YAML 存在 + common 存在 → 两者合并。"""
        rule_path = framework_with_common / "rules.yml"
        rule_path.write_text(
            """
anti_patterns:
  - id: lang-001
    severity: warning
""".strip()
        )
        result = _try_load_yaml(rule_path, framework_dir=framework_with_common)
        assert result is not None
        assert "anti_patterns" in result
        # 合并后应有 lang-001 (来自规则文件) + security_rules (来自 common)
        ids = {p["id"] for p in result["anti_patterns"]}
        # 注意: _merge_rules 处理 anti_patterns 而非 security_rules
        # security_rules 是顶层 key, _merge_anti_patterns 只合并 anti_patterns
        assert "lang-001" in ids

    def test_yaml_non_dict_returns_default(self, framework_with_common: Path) -> None:
        """YAML 是 list (非 dict) → {} (类型兜底), 然后 _merge_rules 加入 anti_patterns: []。

        实际行为: _try_load_yaml line 210 `result = data if isinstance(data, dict) else {}`,
        然后 _merge_rules 调用 _merge_anti_patterns (空 + 空 = 空 list)。
        最终返回 {'anti_patterns': []} (不是 {})。
        """
        rule_path = framework_with_common / "rules.yml"
        rule_path.write_text("- only\n- items\n")
        result = _try_load_yaml(rule_path, framework_dir=framework_with_common)
        assert result == {"anti_patterns": []}


class TestMergeRules:
    """_merge_rules() 全替换 + severity_override + 嵌套合并。"""

    def test_empty_custom_returns_base(self) -> None:
        """custom 是 {} → 返回 base 副本。"""
        base = {"anti_patterns": [{"id": "a"}], "thresholds": {"x": 1}}
        result = _merge_rules(base, {})
        assert result["anti_patterns"] == [{"id": "a"}]
        assert result["thresholds"] == {"x": 1}

    def test_full_replacement(self) -> None:
        """custom anti_patterns 同 id 全替换 base。"""
        base = {"anti_patterns": [{"id": "a", "severity": "warning"}]}
        custom = {"anti_patterns": [{"id": "a", "severity": "error"}]}
        result = _merge_rules(base, custom)
        assert len(result["anti_patterns"]) == 1
        assert result["anti_patterns"][0]["severity"] == "error"

    def test_severity_override_keeps_other_fields(self) -> None:
        """severity_override 模式: 保留 base 其他字段, 只改 severity。"""
        base = {
            "anti_patterns": [
                {
                    "id": "a",
                    "severity": "warning",
                    "message": "原 message",
                    "extra_field": "保留",
                }
            ]
        }
        custom = {"anti_patterns": [{"id": "a", "severity_override": "error"}]}
        result = _merge_rules(base, custom)
        p = result["anti_patterns"][0]
        assert p["severity"] == "error"
        assert p["message"] == "原 message"  # 保留
        assert p["extra_field"] == "保留"  # 保留

    def test_naming_dict_merged(self) -> None:
        """custom.naming dict 合并到 base.naming (深合并, setdefault)。"""
        base: dict[str, Any] = {"naming": {"existing_key": "base_value"}}
        custom: dict[str, Any] = {"naming": {"new_key": "custom_value"}}
        result = _merge_rules(base, custom)
        # 合并后两个 key 都在
        assert "existing_key" in result["naming"]
        assert "new_key" in result["naming"]

    def test_thresholds_dict_merged(self) -> None:
        """custom.thresholds dict 合并到 base.thresholds。"""
        base: dict[str, Any] = {"thresholds": {"a": 1, "b": 2}}
        custom: dict[str, Any] = {"thresholds": {"b": 99, "c": 3}}
        result = _merge_rules(base, custom)
        assert result["thresholds"]["a"] == 1  # 保留
        assert result["thresholds"]["b"] == 99  # 覆盖
        assert result["thresholds"]["c"] == 3  # 新增

    def test_base_unchanged(self) -> None:
        """merge 不修改原 base dict (返回新 dict)。"""
        base = {"anti_patterns": [{"id": "a"}]}
        original = {"anti_patterns": [{"id": "a"}]}
        _merge_rules(base, {"anti_patterns": [{"id": "a", "severity": "error"}]})
        assert base == original  # base 不变


class TestMergeAntiPatterns:
    """_merge_anti_patterns() ID 覆盖 + severity_override + 追加新。"""

    def test_empty_custom_returns_base_copy(self) -> None:
        """custom 是 [] → 返回 base 的副本 (不共享引用)。

        Phase 33 refactor (ADR-034): 修复前 `_merge_anti_patterns(base, [])`
        返回 base 本身 (共享引用, 修改 result 影响 base)。
        修复后返回 base 副本。
        """
        base = [{"id": "a"}]
        result = _merge_anti_patterns(base, [])
        assert result == [{"id": "a"}]
        # 验证是副本 (新 list, 不共享引用)
        assert result is not base
        # 验证修改 result 不影响 base
        result.append({"id": "z"})
        assert base == [{"id": "a"}]

    def test_override_existing_id_full_replacement(self) -> None:
        """custom 含 base 已有的 id → 全替换。"""
        base = [{"id": "a", "severity": "warning"}]
        custom = [{"id": "a", "severity": "error", "extra": "x"}]
        result = _merge_anti_patterns(base, custom)
        assert len(result) == 1
        assert result[0]["severity"] == "error"
        assert result[0]["extra"] == "x"

    def test_severity_override_keeps_other_fields(self) -> None:
        """severity_override 模式: 保留 base 字段, 仅改 severity。"""
        base = [{"id": "a", "severity": "warning", "msg": "保留"}]
        custom = [{"id": "a", "severity_override": "error"}]
        result = _merge_anti_patterns(base, custom)
        assert result[0]["severity"] == "error"
        assert result[0]["msg"] == "保留"

    def test_merge_common_rules_drops_superseded(self) -> None:
        """语言规则声明 supersedes 时，common 中的同 ID 规则被跳过。"""
        base = {"anti_patterns": [{"id": "lang-eval", "supersedes": ["common-eval"]}]}
        common = {"anti_patterns": [{"id": "common-eval"}, {"id": "common-other"}]}
        result = _merge_common_rules(base, common)
        assert [p["id"] for p in result["anti_patterns"]] == ["lang-eval", "common-other"]

    def test_supersedes_does_not_drop_custom_rule(self) -> None:
        """supersedes 只作用于 common 合并，用户自定义规则仍可覆盖。"""
        base = [{"id": "lang-eval", "supersedes": ["common-eval"]}]
        custom = [{"id": "common-eval", "severity": "warning"}]
        result = _merge_anti_patterns(base, custom)
        assert [p["id"] for p in result] == ["lang-eval", "common-eval"]

    def test_new_patterns_appended(self) -> None:
        """custom 新 id (base 无) → 追加到末尾。"""
        base = [{"id": "a"}]
        custom = [{"id": "b"}, {"id": "c"}]
        result = _merge_anti_patterns(base, custom)
        assert len(result) == 3
        assert [p["id"] for p in result] == ["a", "b", "c"]

    def test_mixed_override_and_append(self) -> None:
        """混合: 覆盖已有 + 追加新。"""
        base = [{"id": "a"}, {"id": "b"}]
        custom = [{"id": "a", "severity_override": "error"}, {"id": "c"}]
        result = _merge_anti_patterns(base, custom)
        ids = [p["id"] for p in result]
        assert ids == ["a", "b", "c"]
        assert result[0]["severity"] == "error"
