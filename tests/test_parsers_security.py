"""Coverage tests for rules_engine.parsers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

from tools.scripts.rules_engine.parsers.base import BaseParser
from tools.scripts.rules_engine.parsers.contract import (
    ParserProtocol,
    validate_parser_contract,
)
from tools.scripts.rules_engine.parsers.go_parser import GoParser
from tools.scripts.rules_engine.parsers.python_parser import PythonParser
from tools.scripts.rules_engine.parsers.registry import PARSER_REGISTRY, get_parser
from tools.scripts.rules_engine.parsers.rust_parser import RustParser

# ─────────────────────────────────────────────────────────────
# parsers.base - contract validation
# ─────────────────────────────────────────────────────────────


class MockParser(BaseParser):
    def parse(self, root_node, lines):
        return [], []


def test_validate_parser_contract_valid():
    parser = MockParser()
    assert validate_parser_contract(parser) is True


def test_validate_parser_contract_invalid():
    class NoParse:
        pass

    assert validate_parser_contract(NoParse()) is False


def test_parser_protocol():
    parser = MockParser()
    assert isinstance(parser, ParserProtocol)


# ─────────────────────────────────────────────────────────────
# parsers.go_parser
# ─────────────────────────────────────────────────────────────


def test_go_parser_instantiation():
    parser = GoParser()
    assert isinstance(parser, BaseParser)


def test_go_parser_parse():
    parser = GoParser()
    # 真实实现：None 根节点安全返回空结果
    funcs, classes = parser.parse(None, [])
    assert funcs == []
    assert classes == []


# ─────────────────────────────────────────────────────────────
# parsers.rust_parser
# ─────────────────────────────────────────────────────────────


def test_rust_parser_instantiation():
    parser = RustParser()
    assert isinstance(parser, BaseParser)


def test_rust_parser_parse():
    parser = RustParser()
    # 真实实现：None 根节点安全返回空结果
    funcs, classes = parser.parse(None, [])
    assert funcs == []
    assert classes == []


# ─────────────────────────────────────────────────────────────
# parsers.python_parser
# ─────────────────────────────────────────────────────────────


def test_python_parser_instantiation():
    parser = PythonParser()
    assert isinstance(parser, BaseParser)


# ─────────────────────────────────────────────────────────────
# parsers.registry
# ─────────────────────────────────────────────────────────────


def test_parser_registry_contains_known_languages():
    assert "python" in PARSER_REGISTRY
    assert "go" in PARSER_REGISTRY
    assert "rust" in PARSER_REGISTRY
    assert isinstance(PARSER_REGISTRY["python"], BaseParser)
    assert isinstance(PARSER_REGISTRY["go"], BaseParser)
    assert isinstance(PARSER_REGISTRY["rust"], BaseParser)


def test_get_parser_known():
    parser = get_parser("python")
    assert isinstance(parser, BaseParser)


def test_get_parser_unknown_returns_python():
    parser = get_parser("unknown-lang")
    assert isinstance(parser, PythonParser)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
