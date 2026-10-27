# 拆分自 tests/test_validate_language_rules.py

"""validate_language_rules 核心校验用例。

覆盖 Issue/ValidationResult/规则加载/anti-pattern/命名/阈值/嵌套/AST/
圈复杂度/语言检测/文件与目录校验/JSON 输出。

各语言 anti-pattern 规则用例见 test_language_rules_languages.py。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tools.scripts.validate_language_rules import (
    _extract_function_lines,
    detect_language_from_file,
    load_rules,
    validate_directory,
    validate_file,
)


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def python_rules():
    """Load Python rules."""
    return load_rules("python")


@pytest.fixture
def ts_rules():
    """Load TypeScript rules."""
    return load_rules("typescript")


@pytest.fixture
def rust_rules():
    """Load Rust rules."""
    return load_rules("rust")


@pytest.fixture
def go_rules():
    """Load Go rules."""
    return load_rules("go")


class TestLanguageDetection:
    def test_python_detection(self):
        assert detect_language_from_file(Path("main.py")) == "python"
        assert detect_language_from_file(Path("utils.pyi")) == "python"

    def test_typescript_detection(self):
        assert detect_language_from_file(Path("app.ts")) == "typescript"
        assert detect_language_from_file(Path("page.tsx")) == "typescript"

    def test_rust_detection(self):
        assert detect_language_from_file(Path("main.rs")) == "rust"

    def test_go_detection(self):
        assert detect_language_from_file(Path("main.go")) == "go"

    def test_unknown_extension(self):
        assert detect_language_from_file(Path("data.xyz")) is None


class TestFileValidation:
    def test_validate_clean_python_file(self, tmp_dir):
        filepath = tmp_dir / "clean.py"
        filepath.write_text(
            '"""Clean module."""\n'
            "\n"
            "import logging\n"
            "\n"
            "logger = logging.getLogger(__name__)\n"
            "\n"
            "\n"
            "def add(a: int, b: int) -> int:\n"
            '    """Add two numbers."""\n'
            "    return a + b\n"
            "\n"
            "\n"
            "def process(items: list[int]) -> list[int]:\n"
            '    """Process items."""\n'
            "    return [x * 2 for x in items]\n"
        )
        result = validate_file(filepath, "python")
        # Should have no errors
        assert result.error_count == 0
        assert result.language == "python"

    def test_validate_dirty_python_file(self, tmp_dir):
        filepath = tmp_dir / "dirty.py"
        filepath.write_text(
            "import os\n"
            "from os import *\n"
            "\n"
            "def MyFunction(data: any):\n"
            "    try:\n"
            "        eval(data)\n"
            "    except:\n"
            "        pass\n"
            "\n"
            'password = "secret123"\n'
        )
        result = validate_file(filepath, "python")
        assert result.error_count > 0
        ids = [i.rule_id for i in result.issues]
        assert "py-star-import" in ids
        assert "py-eval-exec" in ids
        assert "py-bare-except" in ids

    def test_validate_clean_typescript(self, tmp_dir):
        filepath = tmp_dir / "clean.ts"
        filepath.write_text(
            "interface User {\n"
            "    name: string;\n"
            "    age: number;\n"
            "}\n"
            "\n"
            "export function greet(user: User): string {\n"
            "    return `Hello, ${user.name}`;\n"
            "}\n"
        )
        result = validate_file(filepath, "typescript")
        assert result.error_count == 0

    def test_validate_dirty_typescript(self, tmp_dir):
        filepath = tmp_dir / "dirty.ts"
        filepath.write_text(
            "var data: any = {};\n"
            "\n"
            "function process(input: any): any {\n"
            "    try {\n"
            "        return eval(input);\n"
            "    } catch (error) {}\n"
            "}\n"
        )
        result = validate_file(filepath, "typescript")
        assert result.error_count > 0
        ids = [i.rule_id for i in result.issues]
        assert "ts-any-type" in ids
        assert "ts-empty-catch" in ids

    def test_validate_clean_rust(self, tmp_dir):
        filepath = tmp_dir / "clean.rs"
        filepath.write_text(
            "use std::error::Error;\n"
            "\n"
            "pub fn process(data: &[u8]) -> Result<Vec<u8>, Box<dyn Error>> {\n"
            "    let result = data.iter().map(|b| b.wrapping_add(1)).collect();\n"
            "    Ok(result)\n"
            "}\n"
        )
        result = validate_file(filepath, "rust")
        assert result.error_count == 0

    def test_validate_dirty_rust(self, tmp_dir):
        filepath = tmp_dir / "dirty.rs"
        filepath.write_text(
            "fn process(data: &[u8]) -> Vec<u8> {\n"
            "    let x = data[0].unwrap();\n"
            "    let y = vec![1, 2, 3];\n"
            '    println!("{:?}", y);\n'
            '    panic!("oops");\n'
            "}\n"
        )
        result = validate_file(filepath, "rust")
        assert result.error_count > 0

    def test_validate_clean_go(self, tmp_dir):
        filepath = tmp_dir / "clean.go"
        filepath.write_text(
            "package main\n"
            "\n"
            'import "fmt"\n'
            "\n"
            "func process(data []byte) ([]byte, error) {\n"
            "    if len(data) == 0 {\n"
            '        return nil, fmt.Errorf("empty data")\n'
            "    }\n"
            "    result := make([]byte, len(data))\n"
            "    copy(result, data)\n"
            "    return result, nil\n"
            "}\n"
        )
        result = validate_file(filepath, "go")
        assert result.error_count == 0

    def test_validate_dirty_go(self, tmp_dir):
        filepath = tmp_dir / "dirty.go"
        filepath.write_text(
            "package main\n"
            "\n"
            'import "fmt"\n'
            "\n"
            "func process(data []byte) []byte {\n"
            "    result, _ := doSomething()\n"
            '    panic("not implemented")\n'
            "    fmt.Println(result)\n"
            "    return nil\n"
            "}\n"
        )
        result = validate_file(filepath, "go")
        assert result.error_count > 0

    def test_unreadable_file(self, tmp_dir):
        filepath = tmp_dir / "nonexistent.py"
        result = validate_file(filepath, "python")
        assert result.error_count > 0


class TestDirectoryValidation:
    def test_validate_directory(self, tmp_dir):
        # Create test files
        (tmp_dir / "clean.py").write_text("def f() -> int:\n    return 1\n")
        (tmp_dir / "dirty.py").write_text("except:\n    pass\n")

        results = validate_directory(tmp_dir, language="python")
        assert len(results) == 2

        clean = [r for r in results if "clean" in r.file]
        dirty = [r for r in results if "dirty" in r.file]
        assert clean[0].error_count == 0
        assert dirty[0].error_count > 0

    def test_validate_directory_auto_detect(self, tmp_dir):
        (tmp_dir / "app.py").write_text("x = 1\n")
        (tmp_dir / "lib.rs").write_text("fn main() {}\n")

        results = validate_directory(tmp_dir)
        assert len(results) == 2
        languages = {r.language for r in results}
        assert "python" in languages
        assert "rust" in languages

    def test_exclude_directories(self, tmp_dir):
        node_modules = tmp_dir / "node_modules"
        node_modules.mkdir()
        (node_modules / "dep.js").write_text("var x = any;")

        (tmp_dir / "app.py").write_text("x = 1\n")

        results = validate_directory(tmp_dir)
        assert len(results) == 1
        assert "app.py" in results[0].file


class TestFunctionExtraction:
    def test_extract_python_functions(self):
        lines = [
            "def f1():",
            "    pass",
            "",
            "def f2():",
            "    x = 1",
            "    return x",
        ]
        funcs = _extract_function_lines(lines, "python")
        names = [f[0] for f in funcs]
        assert "f1" in names
        assert "f2" in names

    def test_extract_rust_functions(self):
        lines = [
            "pub fn my_function() {",
            "    let x = 1;",
            "}",
        ]
        funcs = _extract_function_lines(lines, "rust")
        names = [f[0] for f in funcs]
        assert "my_function" in names

    def test_extract_go_functions(self):
        lines = [
            "func MyFunction() {",
            "    x := 1",
            "    _ = x",
            "}",
        ]
        funcs = _extract_function_lines(lines, "go")
        names = [f[0] for f in funcs]
        assert "MyFunction" in names


class TestJsonOutput:
    def test_result_to_json(self, tmp_dir):
        filepath = tmp_dir / "test.py"
        filepath.write_text("except:\n    pass\n")
        result = validate_file(filepath, "python")
        d = result.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert "py-bare-except" in json_str
