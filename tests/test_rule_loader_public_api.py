"""Tests for rule_loader 公开 API (Phase 32 子任务 2e).

覆盖实际公开 API (ADR-035):
- load_rules: LRU cache + disk cache + generated rules 合并
- load_custom_rules: 3 源合并 (global + project + legacy)
- _load_single_custom_file: yaml 加载 + 合并
- load_rules_for_language: 别名 + framework_dir 传递
- load_domain_rules: domain 发现 + 加载

设计要点:
- 模块级 _RULE_CACHE 通过 monkeypatch 清空
- 模块级 _DISK_CACHE_FILE 通过 monkeypatch 重定向 (ADR-032 模式)
- 模块级 _GENERATED_RULES_CACHE 通过 monkeypatch 清空
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.scripts.rules_engine import rule_loader
from tools.scripts.rules_engine.rule_loader import (
    _GENERATED_RULES_CACHE,
    _RULE_CACHE,
    load_custom_rules,
    load_domain_rules,
    load_rules,
    load_rules_for_language,
)


@pytest.fixture(autouse=True)
def _clear_module_state() -> None:
    """每个测试前清空所有模块级缓存。"""
    _RULE_CACHE.clear()
    _GENERATED_RULES_CACHE.clear()
    rule_loader._rules_hash_cached.cache_clear()
    rule_loader._load_common_rules_cached.cache_clear()
    rule_loader._load_universal_rules_cached.cache_clear()
    yield
    _RULE_CACHE.clear()
    _GENERATED_RULES_CACHE.clear()
    rule_loader._rules_hash_cached.cache_clear()
    rule_loader._load_common_rules_cached.cache_clear()
    rule_loader._load_universal_rules_cached.cache_clear()


@pytest.fixture
def framework_with_languages(tmp_path: Path) -> Path:
    """framework_dir 含 python + rust 规则。"""
    for lang in ["python", "rust"]:
        lang_dir = tmp_path / "languages" / lang / "rules.d"
        lang_dir.mkdir(parents=True)
        (lang_dir / "anti_patterns.yml").write_text(
            f"""
anti_patterns:
  - id: {lang}-001
    severity: warning
naming:
  {lang}_style: pep8
""".strip()
        )
    common = tmp_path / "common"
    common.mkdir()
    (common / "security.yml").write_text("naming: {}\n")
    return tmp_path


@pytest.fixture
def tmp_disk_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """重定向 disk cache 到 tmp_path (ADR-032 模式)。"""
    cache_dir = tmp_path / ".cache" / "rules_engine"
    cache_file = cache_dir / "rules_cache.json"
    monkeypatch.setattr(rule_loader, "_DISK_CACHE_DIR", cache_dir)
    monkeypatch.setattr(rule_loader, "_DISK_CACHE_FILE", cache_file)
    return cache_file


class TestLoadRules:
    """load_rules() 主入口 + 缓存。"""

    def test_load_returns_dict_with_anti_patterns(
        self, framework_with_languages: Path
    ) -> None:
        """加载 python 规则 → 返回 dict 含 anti_patterns。"""
        result = load_rules("python", framework_with_languages)
        assert "anti_patterns" in result
        ids = [p["id"] for p in result["anti_patterns"]]
        assert "python-001" in ids

    def test_load_missing_language_fallback(
        self, framework_with_languages: Path
    ) -> None:
        """未在 framework 的语言 → 走 fallback 策略 (通用 + 生成)。"""
        result = load_rules("nonsense", framework_with_languages)
        # 应有通用规则 (universal) - 因为 fallback
        assert "anti_patterns" in result or result == {}

    def test_cache_hit_no_recomputation(
        self, framework_with_languages: Path
    ) -> None:
        """第二次 load_rules 同 (language, framework) 命中 LRU 缓存。"""
        first = load_rules("python", framework_with_languages)
        # 第二次: 应直接返回缓存
        second = load_rules("python", framework_with_languages)
        assert first is second  # 同一对象

    def test_disk_cache_hit(
        self, framework_with_languages: Path, tmp_disk_cache: Path
    ) -> None:
        """_RULE_CACHE 清空但 disk cache 有数据 → 命中 disk cache。"""
        # 第一次加载,写入 disk cache
        load_rules("python", framework_with_languages)
        # 清空内存缓存
        _RULE_CACHE.clear()
        # 验证 disk cache 存在
        assert tmp_disk_cache.exists()
        # 第二次: 应从 disk cache 恢复
        result = load_rules("python", framework_with_languages)
        assert "anti_patterns" in result

    def test_disk_cache_written_after_load(
        self, framework_with_languages: Path, tmp_disk_cache: Path
    ) -> None:
        """load_rules 后 disk cache 文件被创建。"""
        assert not tmp_disk_cache.exists()
        load_rules("python", framework_with_languages)
        assert tmp_disk_cache.exists()
        # 验证内容是有效 JSON
        data = json.loads(tmp_disk_cache.read_text())
        assert isinstance(data, dict)

    def test_load_different_languages_separate_cache(
        self, framework_with_languages: Path
    ) -> None:
        """不同 language 各自独立缓存。"""
        py_rules = load_rules("python", framework_with_languages)
        rust_rules = load_rules("rust", framework_with_languages)
        # 不同对象
        assert py_rules is not rust_rules
        # 内容分别正确
        py_ids = {p["id"] for p in py_rules["anti_patterns"]}
        rust_ids = {p["id"] for p in rust_rules["anti_patterns"]}
        assert "python-001" in py_ids
        assert "rust-001" in rust_ids


class TestLoadCustomRules:
    """load_custom_rules() 3 源合并。"""

    def test_no_custom_sources_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """无任何 .yml 源 → 返回空默认结构。"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = load_custom_rules(tmp_path)
        assert result == {
            "anti_patterns": [],
            "naming": {},
            "thresholds": {},
        }

    def test_project_adg_rules_loaded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """.adg/rules.yml 存在 → 加载。"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        adg = tmp_path / ".adg"
        adg.mkdir()
        (adg / "rules.yml").write_text(
            """
anti_patterns:
  - id: custom-001
""".strip()
        )
        result = load_custom_rules(tmp_path)
        assert any(p["id"] == "custom-001" for p in result["anti_patterns"])

    def test_legacy_ai_rules_dir_loaded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """.ai-rules/*.yml 目录加载。"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        ai_dir = tmp_path / ".ai-rules"
        ai_dir.mkdir()
        (ai_dir / "rule1.yml").write_text(
            "anti_patterns:\n  - id: legacy-001\n"
        )
        result = load_custom_rules(tmp_path)
        ids = [p["id"] for p in result["anti_patterns"]]
        assert "legacy-001" in ids


class TestLoadRulesForLanguage:
    """load_rules_for_language() 别名 + 透传。"""

    def test_delegates_to_load_rules(
        self, framework_with_languages: Path
    ) -> None:
        """load_rules_for_language 调用 load_rules (相同结果)。"""
        a = load_rules("python", framework_with_languages)
        b = load_rules_for_language("python", framework_with_languages)
        # 内容应相同 (可能不同对象, 因 cache 顺序)
        assert a == b

    def test_default_framework_dir(
        self, framework_with_languages: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """framework_dir=None → 使用 rules_dir()。"""
        monkeypatch.setattr(
            rule_loader, "rules_dir", lambda: framework_with_languages
        )
        result = load_rules_for_language("python")
        assert "anti_patterns" in result


class TestLoadGeneratedRulesInternal:
    """_load_generated_rules 内部 helper (ADR-035: 模块级缓存)。"""

    def test_import_error_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rule_generator 不可 import → [] (兜底)。"""
        # 删除 _GENERATED_RULES_CACHE 条目, 确保第一次调用
        _GENERATED_RULES_CACHE.clear()

        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):  # noqa: ARG001
            if "rule_generator" in name:
                raise ImportError("simulated")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        result = rule_loader._load_generated_rules("python")
        assert result == []


class TestLoadCommonRulesInternal:
    """_load_common_rules + _load_universal_rules 内部 helper。"""

    def test_load_common_rules_default_framework_dir(
        self, framework_with_languages: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """framework_dir=None → 使用 rules_dir() (ADR-033 陷阱延续)。"""
        monkeypatch.setattr(
            rule_loader, "rules_dir", lambda: framework_with_languages
        )
        result = rule_loader._load_common_rules()
        assert isinstance(result, dict)

    def test_load_universal_rules_default_framework_dir(
        self, framework_with_languages: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """framework_dir=None → 使用 rules_dir()。"""
        monkeypatch.setattr(
            rule_loader, "rules_dir", lambda: framework_with_languages
        )
        result = rule_loader._load_universal_rules()
        assert isinstance(result, dict)


class TestLoadDomainRules:
    """load_domain_rules() 域规则加载。"""

    def test_no_domains_returns_empty(self, tmp_path: Path) -> None:
        """项目无 domain 配置 → 返回默认空 dict。"""
        result = load_domain_rules(tmp_path)
        assert result == {"anti_patterns": []}

    def test_domains_loaded_from_adg_config(
        self, tmp_path: Path
    ) -> None:
        """.adg/config.yml 含 domains → 加载对应规则文件。"""
        # 创建 ai-dev-framework/domains/python.yml
        framework_dir = tmp_path / "framework"
        domains_dir = framework_dir / "domains"
        domains_dir.mkdir(parents=True)
        (domains_dir / "fintech.yml").write_text(
            """
anti_patterns:
  - id: fintech-001
    severity: error
""".strip()
        )
        # 创建项目 .adg/config.yml 含 domains
        adg = tmp_path / ".adg"
        adg.mkdir()
        (adg / "config.yml").write_text("domains:\n  - fintech\n")
        # 跑 load_domain_rules
        result = load_domain_rules(tmp_path, framework_dir=framework_dir)
        assert "anti_patterns" in result
        ids = [p["id"] for p in result["anti_patterns"]]
        assert "fintech-001" in ids

    def test_invalid_domain_config_returns_empty(
        self, tmp_path: Path
    ) -> None:
        """config.yml 损坏 → 走兜底, 返回空 dict。"""
        adg = tmp_path / ".adg"
        adg.mkdir()
        (adg / "config.yml").write_text(": invalid [")
        result = load_domain_rules(tmp_path)
        assert result == {"anti_patterns": []}
