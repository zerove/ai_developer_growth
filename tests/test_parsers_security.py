"""Coverage tests for rules_engine.parsers (currently 0%) and security_patterns (0%)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

from tools.scripts.rules_engine.parsers.base import BaseParser
from tools.scripts.rules_engine.parsers.contract import ParserProtocol, validate_parser_contract
from tools.scripts.rules_engine.parsers.go_parser import GoParser
from tools.scripts.rules_engine.parsers.python_parser import PythonParser
from tools.scripts.rules_engine.parsers.python_parser_v3 import PythonParser as PythonParserV3
from tools.scripts.rules_engine.parsers.registry import PARSER_REGISTRY, get_parser
from tools.scripts.rules_engine.parsers.rust_parser import RustParser
from tools.scripts.rules_engine.security_patterns import (
    ERROR_PATTERNS,
    SECURITY_PATTERNS,
    TYPE_PATTERNS,
    get_security_rules,
)

# ─────────────────────────────────────────────────────────────
# security_patterns
# ─────────────────────────────────────────────────────────────

def test_security_patterns_not_empty():
    assert len(SECURITY_PATTERNS) > 0
    for p in SECURITY_PATTERNS:
        assert "id" in p
        assert "name" in p
        assert "severity" in p
        assert "category" in p
        assert "pattern" in p
        assert "message" in p
        assert "fix_hint" in p
        assert p["severity"] in ("error", "warning", "info")


def test_type_patterns_not_empty():
    assert len(TYPE_PATTERNS) > 0
    for p in TYPE_PATTERNS:
        assert p["category"] == "type-safety"


def test_error_patterns_not_empty():
    assert len(ERROR_PATTERNS) > 0
    for p in ERROR_PATTERNS:
        assert p["category"] == "error-handling"


def test_get_security_rules_returns_dict():
    rules = get_security_rules("python")
    assert "anti_patterns" in rules
    assert len(rules["anti_patterns"]) == len(SECURITY_PATTERNS) + len(TYPE_PATTERNS) + len(ERROR_PATTERNS)


def test_security_patterns_exclude_files():
    # eval/exec pattern has exclude_files
    eval_pattern = next(p for p in SECURITY_PATTERNS if p["id"] == "security-eval-exec")
    assert "exclude_files" in eval_pattern
    assert "auto_fix.py" in eval_pattern["exclude_files"]


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
    # Go parser returns empty lists (placeholder implementation)
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
# parsers.python_parser_v3
# ─────────────────────────────────────────────────────────────

class MockTreeNode:
    def __init__(self, node_type, start=(0, 0), end=(0, 0), children=None):
        self.type = node_type
        self.start_point = start
        self.end_point = end
        self.children = children or []


def test_python_parser_v3_instantiation():
    parser = PythonParserV3()
    assert isinstance(parser, BaseParser)


def test_python_parser_v3_parse_function():
    parser = PythonParserV3()
    node = MockTreeNode("function_definition", (1, 0), (3, 0))
    funcs, classes = parser.parse(node, ["def foo():", "    pass", ""])
    assert len(funcs) == 1
    f = funcs[0]
    assert f.name == "extracted_func"
    assert f.line == 1
    assert f.end_line == 3
    assert f.is_async is False
    assert classes == []


def test_python_parser_v3_parse_async_function():
    parser = PythonParserV3()
    node = MockTreeNode("async_function_definition", (1, 0), (3, 0))
    funcs, classes = parser.parse(node, ["async def foo():", "    pass", ""])
    assert len(funcs) == 1
    assert funcs[0].is_async is True


def test_python_parser_v3_parse_class():
    parser = PythonParserV3()
    node = MockTreeNode("class_definition", (1, 0), (5, 0))
    funcs, classes = parser.parse(node, ["class Foo:", "    pass", "", "", "", ""])
    assert len(classes) == 1
    c = classes[0]
    assert c.name == "extracted_class"
    assert c.line == 1
    assert c.end_line == 5
    assert funcs == []


def test_python_parser_v3_walk_children():
    parser = PythonParserV3()
    # Nested: class with method
    class_node = MockTreeNode("class_definition", (1, 0), (6, 0))
    method_node = MockTreeNode("function_definition", (2, 4), (4, 4))
    class_node.children = [method_node]
    funcs, classes = parser.parse(class_node, [
        "class Foo:",
        "    def method():",
        "        pass",
        "", "", "",
    ])
    assert len(classes) == 1
    assert len(funcs) == 1
    assert funcs[0].is_async is False


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
