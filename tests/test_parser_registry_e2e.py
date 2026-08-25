"""解析器注册表与各语言解析器的端到端测试。

验证 PARSER_REGISTRY 五种语言的完整支持：
python / go / rust / java / typescript。
"""

from __future__ import annotations

import pytest
from tree_sitter import Language, Parser

from tools.scripts.rules_engine.parsers.base import BaseParser
from tools.scripts.rules_engine.parsers.registry import PARSER_REGISTRY, get_parser


def _parse_code(language: str, code: bytes):
    """用对应 tree-sitter 语言解析源码并返回根节点。"""
    import tree_sitter_go
    import tree_sitter_java
    import tree_sitter_python
    import tree_sitter_rust
    import tree_sitter_typescript

    modules = {
        "python": (tree_sitter_python, None),
        "go": (tree_sitter_go, None),
        "rust": (tree_sitter_rust, None),
        "java": (tree_sitter_java, None),
        "typescript": (tree_sitter_typescript, "language_typescript"),
    }
    mod, ts_fn = modules[language]
    lang_obj = Language(getattr(mod, ts_fn)()) if ts_fn else Language(mod.language())
    root = Parser(lang_obj).parse(code).root_node
    return PARSER_REGISTRY[language].parse(root, [])


class TestParserRegistry:
    def test_registry_contains_five_languages(self) -> None:
        assert set(PARSER_REGISTRY.keys()) == {"python", "go", "rust", "java", "typescript"}

    def test_all_parsers_satisfy_base(self) -> None:
        for lang, parser in PARSER_REGISTRY.items():
            assert isinstance(parser, BaseParser), f"{lang} 解析器不满足 BaseParser 契约"

    def test_get_parser_fallback(self) -> None:
        assert get_parser("cobol") is PARSER_REGISTRY["python"]


class TestJavaParser:
    def test_extracts_class_with_bases(self) -> None:
        code = b"public class UserService extends Base implements Repo {}\n"
        _, classes = _parse_code("java", code)
        assert len(classes) == 1
        assert classes[0].name == "UserService"
        assert set(classes[0].bases) == {"Base", "Repo"}

    def test_extracts_methods_with_class_name(self) -> None:
        code = b'public class Svc {\n    public String getName(int id) { return "x"; }\n}\n'
        functions, classes = _parse_code("java", code)
        assert len(functions) == 1
        assert functions[0].name == "getName"
        assert functions[0].is_method
        assert functions[0].class_name == "Svc"
        assert len(classes) == 1

    def test_no_duplicate_method_extraction(self) -> None:
        code = (
            b"public class Svc {\n"
            b'    public String getName(int id) { return "x"; }\n'
            b"    public void save(String s) { }\n"
            b"}\n"
        )
        functions, _ = _parse_code("java", code)
        names = [f.name for f in functions]
        assert len(names) == len(set(names)), f"方法重复提取: {names}"
        assert set(names) == {"getName", "save"}

    def test_interface_declaration(self) -> None:
        code = b"interface Repo { void save(); }\n"
        _, classes = _parse_code("java", code)
        assert any(c.name == "Repo" for c in classes)


class TestTypeScriptParser:
    def test_extracts_class_with_heritage_order(self) -> None:
        code = b"class UserService extends Base implements Repo {}\n"
        _, classes = _parse_code("typescript", code)
        assert classes[0].name == "UserService"
        assert classes[0].bases == ["Base", "Repo"]

    def test_extracts_async_method(self) -> None:
        code = b'class Svc {\n  public async getName(id: number): Promise<string> { return "x"; }\n}\n'
        functions, _ = _parse_code("typescript", code)
        assert len(functions) == 1
        assert functions[0].name == "getName"
        assert functions[0].is_async
        assert functions[0].class_name == "Svc"

    def test_extracts_function_and_arrow(self) -> None:
        code = b"function helper(a: string): void {}\nconst lambda = (x: number) => x * 2;\n"
        functions, _ = _parse_code("typescript", code)
        names = {f.name for f in functions}
        assert "helper" in names
        assert "lambda" in names


class TestGoRustParsersRealExtraction:
    def test_go_method_and_function(self) -> None:
        code = (
            b"package svc\n"
            b"type UserService struct { Base }\n"
            b'func (s *UserService) GetName(id int) string { return "x" }\n'
            b"func Helper(a string) {}\n"
        )
        functions, classes = _parse_code("go", code)
        names = {f.name for f in functions}
        assert "UserService.GetName" in names
        assert "Helper" in names
        assert any(c.name == "UserService" for c in classes)

    def test_rust_impl_method_not_duplicated(self) -> None:
        code = (
            b"pub struct UserService;\n"
            b"impl UserService {\n"
            b'    pub async fn get_name(&self, id: u64) -> String { "x".into() }\n'
            b"}\n"
            b"pub fn helper(a: &str) {}\n"
        )
        functions, classes = _parse_code("rust", code)
        fn_names = [f.name for f in functions]
        assert fn_names.count("get_name") == 1, f"impl 方法重复提取: {fn_names}"
        assert "helper" in fn_names
        method = next(f for f in functions if f.name == "get_name")
        assert method.class_name == "UserService"
        assert method.is_async
        assert any(c.name == "UserService" for c in classes)

    def test_rust_trait_and_enum(self) -> None:
        code = b"pub trait Repo {}\npub enum State { A, B }\n"
        _, classes = _parse_code("rust", code)
        names = {c.name for c in classes}
        assert "Repo" in names
        assert "State" in names


class TestAllLanguagesEndToEnd:
    @pytest.mark.parametrize(
        "language",
        ["python", "go", "rust", "java", "typescript"],
    )
    def test_each_language_produces_functions_or_classes(self, language: str) -> None:
        samples = {
            "python": b"class Svc:\n    def get(self): pass\n",
            "go": b"package s\nfunc Do() {}\n",
            "rust": b"pub fn do_it() {}\n",
            "java": b"class Svc { void run() {} }\n",
            "typescript": b"function go(): void {}\n",
        }
        functions, classes = _parse_code(language, samples[language])
        assert functions or classes, f"{language} 未提取到任何符号"
