"""测试 .jcode/scripts/jcode-init.py。

该脚本此前零测试覆盖。它是所有新项目的配置生成入口，生成的文件会被
hooks_runner / governance-auditor 直接消费，因此输出必须是**合法 YAML**
且结构正确。

测试重点：
1. dict_to_yaml 是手写 YAML 发射器 —— 用 PyYAML 做往返属性测试，
   而非只比对字符串字面量（字面量比对无法发现"看起来对但解析不出来"）
2. _write_config 的覆盖保护（不带 --force 不得覆盖已有文件）
3. _build_parser 的 choices 与默认值
4. generate_config 对全部预设语言/模板都能产出可解析配置
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

_SCRIPTS = Path(__file__).resolve().parent.parent / ".jcode" / "scripts"


def _load(alias: str):
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    path = _SCRIPTS / "jcode-init.py"
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PRESETS = _load("jcode_jinit_presets")


@pytest.fixture(scope="module")
def ji():
    return _load("jcode_jinit")


def _ns(**kw: Any) -> argparse.Namespace:
    base: dict[str, Any] = {
        "lang": None,
        "secondary": None,
        "lang_version": None,
        "template": None,
        "name": None,
        "description": None,
        "version": None,
        "repository": None,
        "license": None,
        "src": None,
        "tests": None,
        "docs": None,
        "ci": None,
        "output": Path(".jcode/project.yaml"),
        "force": False,
    }
    base.update(kw)
    return argparse.Namespace(**base)


# ── dict_to_yaml（手写发射器，往返属性测试） ─────────────────────────


class TestDictToYaml:
    def test_flat_scalars_roundtrip(self, ji) -> None:
        data = {"name": "demo", "version": "0.1.0", "count": 3}
        assert yaml.safe_load(ji.dict_to_yaml(data)) == data

    def test_nested_dict_roundtrip(self, ji) -> None:
        data = {"a": {"b": {"c": "deep"}}, "top": "x"}
        assert yaml.safe_load(ji.dict_to_yaml(data)) == data

    def test_bool_lowercase_roundtrip(self, ji) -> None:
        """布尔必须小写，否则 PyYAML 解析成字符串 'True'。"""
        data = {"enabled": True, "disabled": False}
        parsed = yaml.safe_load(ji.dict_to_yaml(data))
        assert parsed == data
        assert isinstance(parsed["enabled"], bool)

    def test_none_roundtrip(self, ji) -> None:
        assert yaml.safe_load(ji.dict_to_yaml({"k": None})) == {"k": None}

    def test_number_roundtrip(self, ji) -> None:
        parsed = yaml.safe_load(ji.dict_to_yaml({"i": 5, "f": 1.5}))
        assert parsed == {"i": 5, "f": 1.5}

    def test_list_of_scalars_roundtrip(self, ji) -> None:
        parsed = yaml.safe_load(ji.dict_to_yaml({"tags": ["a", "b"]}))
        assert parsed == {"tags": ["a", "b"]}

    def test_list_of_dicts_roundtrip(self, ji) -> None:
        data = {"items": [{"n": "one"}, {"n": "two"}]}
        parsed = yaml.safe_load(ji.dict_to_yaml(data))
        assert parsed == data, f"解析结果不符: {parsed}"

    def test_string_with_colon_is_quoted(self, ji) -> None:
        """未加引号的 'a: b' 会被 YAML 解析成嵌套映射。"""
        raw = ji.dict_to_yaml({"desc": "ratio: 3:1"})
        assert yaml.safe_load(raw) == {"desc": "ratio: 3:1"}

    @pytest.mark.parametrize("value", ["${PROJECT_ROOT}/src", "#not-a-comment", "has: colon", "trailing: "])
    def test_ambiguous_strings_roundtrip(self, ji, value: str) -> None:
        assert yaml.safe_load(ji.dict_to_yaml({"k": value})) == {"k": value}

    def test_plain_string_not_quoted(self, ji) -> None:
        assert ji.dict_to_yaml({"k": "plain"}) == "k: plain"

    def test_indent_argument_is_respected(self, ji) -> None:
        assert ji.dict_to_yaml({"k": "v"}, indent=2) == "    k: v"

    def test_empty_dict_returns_empty_string(self, ji) -> None:
        assert ji.dict_to_yaml({}) == ""


# ── generate_config ─────────────────────────────────────────────────


class TestGenerateConfig:
    @pytest.mark.parametrize("lang", sorted(_PRESETS.LANGUAGE_TEMPLATES))
    def test_every_preset_language_produces_valid_yaml(self, ji, lang: str) -> None:
        out = ji.generate_config(_ns(lang=lang))
        parsed = yaml.safe_load(out)
        assert isinstance(parsed, dict), f"{lang} 生成结果不是合法 YAML 映射"
        assert parsed.get("language", {}).get("primary") == lang

    @pytest.mark.parametrize("tpl", list(_PRESETS.PROJECT_TEMPLATES))
    def test_every_preset_template_produces_valid_yaml(self, ji, tpl: str) -> None:
        out = ji.generate_config(_ns(template=tpl))
        parsed = yaml.safe_load(out)
        assert isinstance(parsed, dict), f"模板 {tpl} 生成结果不是合法 YAML 映射"

    def test_defaults_without_lang_or_template(self, ji) -> None:
        parsed = yaml.safe_load(ji.generate_config(_ns()))
        assert isinstance(parsed, dict)
        assert parsed.get("language", {}).get("primary") == "python"

    def test_project_name_is_reflected(self, ji) -> None:
        parsed = yaml.safe_load(ji.generate_config(_ns(lang="python", name="my-app")))
        assert parsed["project"]["name"] == "my-app"

    def test_custom_paths_override_template(self, ji) -> None:
        parsed = yaml.safe_load(ji.generate_config(_ns(lang="python", src="lib", tests="spec")))
        assert parsed["paths"]["src"] == "lib"
        assert parsed["paths"]["tests"] == "spec"
        assert parsed["paths"]["docs"] == "docs", "未覆盖的键应保留模板默认值"

    def test_secondary_languages_recorded(self, ji) -> None:
        parsed = yaml.safe_load(ji.generate_config(_ns(lang="python", secondary=["rust", "go"])))
        sec = parsed["language"].get("secondary")
        assert sec is not None and len(sec) == 2

    def test_language_version_override(self, ji) -> None:
        parsed = yaml.safe_load(ji.generate_config(_ns(lang="python", lang_version=">=3.12")))
        assert "3.12" in str(parsed["language"].get("version"))

    def test_output_is_deterministic_apart_from_timestamp(self, ji) -> None:
        """两次生成的差异只能是 _metadata 中的时间戳。"""
        a = yaml.safe_load(ji.generate_config(_ns(lang="python")))
        b = yaml.safe_load(ji.generate_config(_ns(lang="python")))
        a.pop("_metadata", None)
        b.pop("_metadata", None)
        assert a == b

    def test_generated_config_has_no_python_repr_leakage(self, ji) -> None:
        """不得出现 Python 特有的 None/True/False/单引号列表。"""
        out = ji.generate_config(_ns(lang="python"))
        for bad in ("None", ": True", ": False", "{'"):
            assert bad not in out, f"输出含 Python 字面量 {bad!r}:\n{out}"


# ── _write_config ───────────────────────────────────────────────────


class TestWriteConfig:
    def test_writes_file_and_creates_parents(self, ji, tmp_path: Path, capsys) -> None:
        out = tmp_path / "nested" / "deep" / "project.yaml"
        args = _ns(output=out, lang="python", name="demo")
        assert ji._write_config(out, "k: v\n", args) == 0
        assert out.read_text(encoding="utf-8") == "k: v\n"
        assert "配置已生成" in capsys.readouterr().out

    def test_refuses_to_overwrite_without_force(self, ji, tmp_path: Path) -> None:
        out = tmp_path / "project.yaml"
        out.write_text("original: true\n", encoding="utf-8")
        args = _ns(output=out, lang="python")
        assert ji._write_config(out, "k: v\n", args) == 1
        assert out.read_text(encoding="utf-8") == "original: true\n", "已有文件被覆盖了"

    def test_force_overwrites(self, ji, tmp_path: Path) -> None:
        out = tmp_path / "project.yaml"
        out.write_text("original: true\n", encoding="utf-8")
        args = _ns(output=out, lang="python", force=True)
        assert ji._write_config(out, "k: v\n", args) == 0
        assert out.read_text(encoding="utf-8") == "k: v\n"

    def test_reports_project_and_language(self, ji, tmp_path: Path, capsys) -> None:
        out = tmp_path / "p.yaml"
        ji._write_config(out, "k: v\n", _ns(output=out, lang="rust", name="svc"))
        text = capsys.readouterr().out
        assert "svc" in text and "rust" in text


# ── _build_parser ───────────────────────────────────────────────────


class TestParser:
    def test_default_output_path(self, ji) -> None:
        assert ji._build_parser().parse_args([]).output == Path(".jcode/project.yaml")

    def test_force_defaults_false(self, ji) -> None:
        assert ji._build_parser().parse_args([]).force is False

    def test_rejects_unknown_lang(self, ji) -> None:
        with pytest.raises(SystemExit):
            ji._build_parser().parse_args(["--lang", "cobol"])

    def test_rejects_unknown_template(self, ji) -> None:
        with pytest.raises(SystemExit):
            ji._build_parser().parse_args(["--template", "desktop"])

    def test_accepts_documented_langs(self, ji) -> None:
        for lang in _PRESETS.LANGUAGE_TEMPLATES:
            assert ji._build_parser().parse_args(["--lang", lang]).lang == lang

    def test_accepts_documented_templates(self, ji) -> None:
        for tpl in _PRESETS.PROJECT_TEMPLATES:
            assert ji._build_parser().parse_args(["--template", tpl]).template == tpl

    def test_secondary_is_multi_value(self, ji) -> None:
        assert ji._build_parser().parse_args(["--secondary", "a", "b"]).secondary == ["a", "b"]


# ── main（端到端，经真实 CLI） ───────────────────────────────────────


class TestMainEndToEnd:
    def _cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(_SCRIPTS / "jcode-init.py"), *args],
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_generated_file_is_parseable_yaml(self, tmp_path: Path) -> None:
        out = tmp_path / "project.yaml"
        r = self._cli("--lang", "python", "--output", str(out))
        assert r.returncode == 0, r.stdout + r.stderr
        parsed = yaml.safe_load(out.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict) and parsed

    def test_cli_refuses_overwrite_then_succeeds_with_force(self, tmp_path: Path) -> None:
        out = tmp_path / "project.yaml"
        assert self._cli("--lang", "python", "-o", str(out)).returncode == 0
        before = out.read_text(encoding="utf-8")
        assert self._cli("--lang", "go", "-o", str(out)).returncode == 1
        assert out.read_text(encoding="utf-8") == before
        assert self._cli("--lang", "go", "-o", str(out), "--force").returncode == 0

    def test_help_exits_zero(self) -> None:
        assert self._cli("--help").returncode == 0

    def test_every_preset_language_generates_parseable_file_via_cli(self, tmp_path: Path) -> None:
        """所有预设语言都必须能真正落盘并被解析，不能只在单元层面看起来对。"""
        for lang in _PRESETS.LANGUAGE_TEMPLATES:
            out = tmp_path / f"{lang}.yaml"
            r = self._cli("--lang", lang, "-o", str(out))
            assert r.returncode == 0, f"{lang} 退出码非零: {r.stdout}{r.stderr}"
            assert isinstance(yaml.safe_load(out.read_text(encoding="utf-8")), dict), lang
