"""Tests for ASTParser LRU/snapshot 行为 (Phase 33a-4).

覆盖 LRU cache 单例 + snapshot:
- get_parser() @lru_cache 单例: 多次调用返回同一实例
- get_parser.cache_clear(): 清理后重新构造
- ASTParser.reset_parser_cache(): 类级 parser 缓存清空
- ASTParser.supported_languages() 返回集合
- ASTParser.parse() 边界 (空代码/二进制/未支持语言)
- _shared_parsers() lazy 初始化 (第一次调用触发, 第二次直接返回缓存)

详见 ADR-036 Phase 33 子任务分解 + ADR-042 (本次)。
"""

from __future__ import annotations

import pytest

from tools.scripts.rules_engine.ast_parser import (
    ASTParser,
    get_parser,
)


class TestGetParserLRUCache:
    """get_parser() @lru_cache 单例行为。"""

    def test_get_parser_returns_singleton(self) -> None:
        """多次调用 get_parser() 返回同一实例 (lru_cache 单例)。"""
        get_parser.cache_clear()
        p1 = get_parser()
        p2 = get_parser()
        assert p1 is p2

    def test_get_parser_returns_astparser_instance(self) -> None:
        """get_parser() 返回 ASTParser 实例。"""
        get_parser.cache_clear()
        parser = get_parser()
        assert isinstance(parser, ASTParser)

    def test_get_parser_cache_clear_creates_new(self) -> None:
        """cache_clear() 后下次调用创建新实例。"""
        get_parser.cache_clear()
        p1 = get_parser()
        get_parser.cache_clear()
        p2 = get_parser()
        assert p1 is not p2


class TestResetParserCache:
    """ASTParser.reset_parser_cache() 类级缓存清理。"""

    def test_reset_clears_cache(self) -> None:
        """reset_parser_cache() 清空 _PARSER_CACHE 与 _PARSER_CACHE_READY。"""
        # 触发 lazy 初始化
        ASTParser._shared_parsers()
        assert ASTParser._PARSER_CACHE_READY is True
        assert len(ASTParser._PARSER_CACHE) >= 0

        ASTParser.reset_parser_cache()
        assert ASTParser._PARSER_CACHE_READY is False
        assert ASTParser._PARSER_CACHE == {}

    def test_reset_then_shared_reinitializes(self) -> None:
        """reset 后再次 _shared_parsers() 重新初始化。"""
        ASTParser._shared_parsers()
        before = dict(ASTParser._PARSER_CACHE)

        ASTParser.reset_parser_cache()
        ASTParser._shared_parsers()
        after = dict(ASTParser._PARSER_CACHE)

        # 重建后应包含相同的 keys (languages)
        assert set(before.keys()) == set(after.keys())

    def test_shared_parsers_lazy_init(self) -> None:
        """_shared_parsers() 第一次调用触发初始化, 第二次直接返回缓存。"""
        ASTParser.reset_parser_cache()
        assert ASTParser._PARSER_CACHE_READY is False

        first = ASTParser._shared_parsers()
        assert ASTParser._PARSER_CACHE_READY is True

        second = ASTParser._shared_parsers()
        assert first is second
        assert first is ASTParser._PARSER_CACHE


class TestSupportedLanguages:
    """ASTParser.supported_languages() 返回支持的语言集合。"""

    def test_returns_set(self) -> None:
        """supported_languages() 返回 set 类型。"""
        parser = ASTParser()
        langs = parser.supported_languages()
        assert isinstance(langs, set)

    def test_contains_expected_languages_when_available(self) -> None:
        """若 tree-sitter 可用, 至少 python 包含。"""
        parser = ASTParser()
        if parser.available:
            langs = parser.supported_languages()
            assert "python" in langs

    def test_empty_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HAS_TREE_SITTER=False → supported_languages() 为空。"""
        parser = ASTParser()
        # mock HAS_TREE_SITTER 行为: 直接覆盖 _available
        monkeypatch.setattr(parser, "_available", False)
        monkeypatch.setattr(parser, "_parsers", {})
        assert parser.supported_languages() == set()


class TestParseMethodEdgeCases:
    """ASTParser.parse() 边界情况。"""

    def test_parse_returns_none_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """parser 不可用 → parse() 返回 None 不抛。"""
        parser = ASTParser()
        monkeypatch.setattr(parser, "_available", False)
        result = parser.parse("x = 1", "python")
        assert result is None

    def test_parse_returns_none_for_unsupported_language(self) -> None:
        """不支持的语言 → parse() 返回 None。"""
        parser = ASTParser()
        if parser.available:
            result = parser.parse("x = 1", "cobol")
            assert result is None

    def test_parse_bytes_input(self) -> None:
        """bytes 输入 → 正常解析 (不抛)。"""
        parser = ASTParser()
        if parser.available:
            code = b"def foo():\n    return 1\n"
            result = parser.parse(code, "python")
            # tree-sitter Tree 或 None, 不抛
            assert result is None or hasattr(result, "root_node")

    def test_parse_empty_string(self) -> None:
        """空字符串 → 解析为 tree-sitter Tree (空代码)。"""
        parser = ASTParser()
        if parser.available:
            result = parser.parse("", "python")
            # tree-sitter 接受空字符串, 返回 root_node
            assert result is not None


class TestSharedParsersSingleton:
    """_shared_parsers() 类级单例验证。"""

    def test_shared_parsers_class_attribute(self) -> None:
        """_PARSER_CACHE 是 class-level 共享缓存。"""
        assert hasattr(ASTParser, "_PARSER_CACHE")
        assert hasattr(ASTParser, "_PARSER_CACHE_READY")
        assert isinstance(ASTParser._PARSER_CACHE, dict)

    def test_shared_parsers_idempotent(self) -> None:
        """_shared_parsers() 多次调用幂等 (READY=True 后短路)。"""
        ASTParser.reset_parser_cache()
        ASTParser._shared_parsers()
        assert ASTParser._PARSER_CACHE_READY is True
        # 第二次直接返回 _PARSER_CACHE (不会重新初始化)
        cache_ref = ASTParser._PARSER_CACHE
        ASTParser._shared_parsers()
        assert ASTParser._PARSER_CACHE is cache_ref  # 同一对象


class TestParserModuleSnapshot:
    """ast_parser 模块级 snapshot/常量。"""

    def test_class_has_supported_languages(self) -> None:
        """ASTParser 类有 SUPPORTED_LANGUAGES 常量。"""
        assert hasattr(ASTParser, "SUPPORTED_LANGUAGES")
        assert isinstance(ASTParser.SUPPORTED_LANGUAGES, set)

    def test_supported_languages_contains_python(self) -> None:
        """ASTParser.SUPPORTED_LANGUAGES 至少包含 python。"""
        assert "python" in ASTParser.SUPPORTED_LANGUAGES

    def test_supported_languages_multiple_langs(self) -> None:
        """ASTParser.SUPPORTED_LANGUAGES 包含多种主流语言。"""
        # 至少包含 python + javascript (最常用)
        assert "python" in ASTParser.SUPPORTED_LANGUAGES
        assert "javascript" in ASTParser.SUPPORTED_LANGUAGES


class TestParseFileMethod:
    """ASTParser.parse_file() 文件解析。"""

    def test_parse_file_nonexistent_returns_none(self) -> None:
        """不存在文件 → parse_file() 返回 None 不抛。"""
        from pathlib import Path

        parser = ASTParser()
        result = parser.parse_file(Path("/nonexistent/file.py"))
        assert result is None

    def test_parse_file_python_returns_fileast(self, tmp_path) -> None:
        """Python 文件 → 返回 FileAST。"""

        parser = ASTParser()
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    return 1\n")
        if parser.available:
            result = parser.parse_file(f)
            assert result is not None
            assert result.language == "python"


class TestParserLanguagesProperty:
    """ASTParser.supported_languages() (snapshot of available)。"""

    def test_supported_languages_matches_parsers(self) -> None:
        """supported_languages() 返回 _parsers 的 keys。"""
        parser = ASTParser()
        langs = parser.supported_languages()
        assert isinstance(langs, set)
        assert langs == set(parser._parsers.keys())


class TestParserInitWithCustomConfig:
    """ASTParser.__init__() 配置注入。"""

    def test_init_uses_shared_parsers(self) -> None:
        """新实例复用同一 _parsers dict (类级共享)。"""
        ASTParser.reset_parser_cache()
        p1 = ASTParser()
        p2 = ASTParser()
        assert p1._parsers is p2._parsers

    def test_init_sets_available(self) -> None:
        """__init__ 设置 _available 属性。"""
        ASTParser.reset_parser_cache()
        parser = ASTParser()
        # _available 是 bool (HAS_TREE_SITTER 值)
        assert isinstance(parser._available, bool)
