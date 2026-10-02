"""测试 .jcode/scripts/ 下两个此前 0% 覆盖的 skill 入口：
community-catalyst.py 与 workflow-optimizer.py。

两者都是 action_map 分派 + 文件系统统计的组合，此前一行未被执行过。

隔离要求：
- get_project_root -> tmp_path：两者都只读文件系统，但统一重定向更安全
- run_command -> 打桩：community-catalyst 会真实拉起 validate_case_study 等脚本
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / ".jcode" / "scripts"


def _load(name: str, alias: str):
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(alias, _SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cc():
    return _load("community-catalyst", "jcode_cc")


@pytest.fixture(scope="module")
def wo():
    return _load("workflow-optimizer", "jcode_wo")


@pytest.fixture
def cc_iso(cc, tmp_path: Path):
    with patch.object(cc, "get_project_root", return_value=tmp_path):
        yield cc, tmp_path


@pytest.fixture
def wo_iso(wo, tmp_path: Path):
    with patch.object(wo, "get_project_root", return_value=tmp_path):
        yield wo, tmp_path


def _cases(root: Path, files: dict[str, str]) -> Path:
    d = root / "docs" / "case-studies"
    d.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")
    return d


# ── community-catalyst: _pr_ref（回归防护） ──────────────────────────


class TestPrRef:
    """回归防护：`generate-adr --pr 123` 曾把 `--pr` 当成 PR 号传给下游。"""

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            ([], "HEAD"),
            (["--pr", "123"], "123"),
            (["123"], "123"),
            (["--pr"], "HEAD"),
            (["--pr", "--verbose"], "HEAD"),
            (["--pr", "abc", "extra"], "abc"),
        ],
    )
    def test_parses_documented_forms(self, cc, args: list[str], expected: str) -> None:
        with patch.object(sys, "argv", ["prog", "generate-adr", *args]):
            assert cc._pr_ref() == expected

    def test_documented_flag_form_does_not_leak_flag(self, cc) -> None:
        with patch.object(sys, "argv", ["prog", "generate-adr", "--pr", "42"]):
            ref = cc._pr_ref()
        assert ref == "42"
        assert not ref.startswith("-")


class TestGenerateAdr:
    def test_builds_command_with_ref(self, cc_iso) -> None:
        """ADR-060：adr_generator 非交互必须有 --title，故此处须一并下发。"""
        cc, _ = cc_iso
        captured: dict = {}
        with (
            patch.object(cc, "run_command", side_effect=lambda cmd: (captured.update(cmd=cmd), (0, "ok"))[1]),
            patch.object(cc, "_resolve_title", return_value="T"),
            patch.object(sys, "argv", ["prog", "generate-adr", "--pr", "7"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            assert cc.generate_adr() == 0
        cmd = captured["cmd"][2:]
        assert "--pr" in cmd and "7" in cmd
        assert "--title" in cmd, "非交互下游必须有 --title"
        assert "--title" in cmd and cmd[cmd.index("--title") + 1] == "T"

    def test_defaults_to_head(self, cc_iso) -> None:
        cc, _ = cc_iso
        captured: dict = {}
        with (
            patch.object(cc, "run_command", side_effect=lambda cmd: (captured.update(cmd=cmd), (0, "ok"))[1]),
            patch.object(cc, "_resolve_title", return_value="T"),
            patch.object(sys, "argv", ["prog", "generate-adr"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cc.generate_adr()
        cmd = captured["cmd"][2:]
        assert cmd[cmd.index("--pr") + 1] == "HEAD"

    def test_failure_propagates(self, cc_iso) -> None:
        cc, _ = cc_iso
        with (
            patch.object(cc, "run_command", return_value=(1, "boom")),
            patch.object(sys, "argv", ["prog", "generate-adr"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            assert cc.generate_adr() == 1


class TestCommunityCatalystActions:
    def test_triage_lists_labels(self, cc_iso, capsys) -> None:
        cc, _ = cc_iso
        assert cc.triage() == 0
        assert "good first issue" in capsys.readouterr().out

    def test_validate_invokes_case_validator(self, cc_iso) -> None:
        cc, _ = cc_iso
        captured: dict = {}
        with (
            patch.object(cc, "run_command", side_effect=lambda cmd: (captured.update(cmd=cmd), (0, ""))[1]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            assert cc.validate() == 0
        assert "validate_case_study.py" in " ".join(captured["cmd"])
        assert "--all" in captured["cmd"]

    def test_leaderboard_invokes_dashboard(self, cc_iso) -> None:
        cc, _ = cc_iso
        captured: dict = {}
        with (
            patch.object(cc, "run_command", side_effect=lambda cmd: (captured.update(cmd=cmd), (0, ""))[1]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            assert cc.leaderboard() == 0
        assert "contributor_dashboard.py" in " ".join(captured["cmd"])
        assert "--leaderboard" in captured["cmd"]

    def test_stats_missing_dir_returns_one(self, cc_iso, capsys) -> None:
        cc, root = cc_iso
        assert cc.stats() == 1
        assert "未找到案例目录" in capsys.readouterr().out

    def test_stats_counts_and_classifies(self, cc_iso, capsys) -> None:
        cc, root = cc_iso
        _cases(
            root,
            {
                "a.md": "来源: 社区贡献\n效率提升 3x",
                "b.md": "来源: community\n",
                "c.md": "普通内部案例",
                "d.md": "另一个内部案例",
            },
        )
        assert cc.stats() == 0
        out = capsys.readouterr().out
        assert "案例总数: 4" in out
        assert "社区案例: 2" in out
        assert "内部案例: 2" in out

    def test_stats_on_empty_dir(self, cc_iso, capsys) -> None:
        cc, root = cc_iso
        _cases(root, {})
        assert cc.stats() == 0
        assert "案例总数: 0" in capsys.readouterr().out

    @pytest.mark.parametrize("action", ["triage", "validate", "stats", "generate-adr", "leaderboard"])
    def test_action_dispatch(self, cc, action: str) -> None:
        """打桩目标函数验证分派，避免真实拉起子脚本。"""
        target = {"generate-adr": "generate_adr"}.get(action, action)
        with (
            patch.object(cc, target, return_value=0) as stub,
            patch.object(sys, "argv", ["prog", action]),
            pytest.raises(SystemExit) as exc,
        ):
            cc.main()
        assert exc.value.code == 0
        stub.assert_called_once_with()

    def test_unknown_action_exits_nonzero(self, cc, capsys) -> None:
        with patch.object(sys, "argv", ["prog", "nope"]):
            with pytest.raises(SystemExit) as exc:
                cc.main()
        assert exc.value.code == 1
        assert "nope" in capsys.readouterr().out

    def test_no_action_exits_nonzero(self, cc) -> None:
        with patch.object(sys, "argv", ["prog"]):
            with pytest.raises(SystemExit) as exc:
                cc.main()
        assert exc.value.code == 1


# ── workflow-optimizer ──────────────────────────────────────────────


class TestAnalyze:
    def test_missing_dir_returns_one(self, wo_iso, capsys) -> None:
        wo, _ = wo_iso
        assert wo.analyze() == 1
        assert "未找到案例目录" in capsys.readouterr().out

    def test_counts_cases(self, wo_iso, capsys) -> None:
        wo, root = wo_iso
        _cases(root, {"a.md": "无数据", "b.md": "无数据"})
        assert wo.analyze() == 0
        assert "案例总数: 2" in capsys.readouterr().out

    def test_detects_efficiency_lines(self, wo_iso, capsys) -> None:
        wo, root = wo_iso
        _cases(
            root,
            {
                "a.md": "效率提升: 3x\n",
                "b.md": "效率提升 12X\n",
                "c.md": "提到效率提升但无倍数\n",
            },
        )
        assert wo.analyze() == 0
        assert "有效率数据的案例: 2" in capsys.readouterr().out

    def test_case_without_efficiency_keyword_ignored(self, wo_iso, capsys) -> None:
        wo, root = wo_iso
        _cases(root, {"a.md": "3x speedup\n"})
        assert wo.analyze() == 0
        assert "有效率数据的案例: 0" in capsys.readouterr().out

    def test_caps_display_at_five(self, wo_iso, capsys) -> None:
        wo, root = wo_iso
        _cases(root, {f"c{i}.md": f"效率提升 {i}x\n" for i in range(8)})
        assert wo.analyze() == 0
        out = capsys.readouterr().out
        assert "有效率数据的案例: 8" in out
        assert "还有 3 个" in out


class TestRecommend:
    def test_missing_matrix_returns_one(self, wo_iso, capsys) -> None:
        wo, _ = wo_iso
        assert wo.recommend() == 1
        assert "未找到工具矩阵文档" in capsys.readouterr().out

    def test_filters_table_rows(self, wo_iso, capsys) -> None:
        wo, root = wo_iso
        d = root / "docs" / "tools"
        d.mkdir(parents=True, exist_ok=True)
        (d / "ai-tool-matrix.md").write_text(
            "\n".join(
                [
                    "| 工具 | 场景 |",
                    "| --- | --- |",
                    "| 模型 | 推理 |",
                    "| Cursor | 编码 |",
                    "非表格行",
                ]
            ),
            encoding="utf-8",
        )
        assert wo.recommend() == 0
        out = capsys.readouterr().out
        assert "| Cursor |" in out
        assert "非表格行" not in out
        assert "| 模型 |" not in out
        assert "| --- |" not in out


class TestReport:
    def test_counts_with_full_tree(self, wo_iso, capsys) -> None:
        wo, root = wo_iso
        _cases(root, {"a.md": "x", "b.md": "y"})
        (root / "docs" / "adr").mkdir(parents=True, exist_ok=True)
        (root / "docs" / "adr" / "ADR-001.md").write_text("z", encoding="utf-8")
        for name in ("ex1", "ex2"):
            (root / "examples" / name).mkdir(parents=True, exist_ok=True)
        (root / "examples" / "loose.txt").write_text("f", encoding="utf-8")
        assert wo.report() == 0
        out = capsys.readouterr().out
        assert "案例数量: 2" in out
        assert "文档数量: 3" in out
        assert "代码示例: 2" in out

    def test_missing_dirs_count_zero(self, wo_iso, capsys) -> None:
        wo, _ = wo_iso
        assert wo.report() == 0
        out = capsys.readouterr().out
        assert "案例数量: 0" in out
        assert "文档数量: 0" in out
        assert "代码示例: 0" in out

    def test_file_in_examples_not_counted(self, wo_iso, capsys) -> None:
        """examples 下只统计目录，不统计散落文件。"""
        wo, root = wo_iso
        (root / "examples").mkdir(parents=True, exist_ok=True)
        (root / "examples" / "README.md").write_text("x", encoding="utf-8")
        assert wo.report() == 0
        assert "代码示例: 0" in capsys.readouterr().out


class TestWorkflowOptimizerCli:
    @pytest.mark.parametrize("action", ["analyze", "recommend", "report"])
    def test_action_dispatch(self, wo, tmp_path: Path, action: str) -> None:
        with (
            patch.object(wo, "get_project_root", return_value=tmp_path),
            patch.object(wo, action, return_value=0) as stub,
            patch.object(sys, "argv", ["prog", action]),
            pytest.raises(SystemExit) as exc,
        ):
            wo.main()
        assert exc.value.code == 0
        stub.assert_called_once_with()

    def test_unknown_action_exits_nonzero(self, wo, capsys) -> None:
        with patch.object(sys, "argv", ["prog", "nope"]):
            with pytest.raises(SystemExit) as exc:
                wo.main()
        assert exc.value.code == 1
        assert "nope" in capsys.readouterr().out

    def test_no_action_exits_nonzero(self, wo) -> None:
        with patch.object(sys, "argv", ["prog"]):
            with pytest.raises(SystemExit) as exc:
                wo.main()
        assert exc.value.code == 1


# ── 与真实文档的一致性 ──────────────────────────────────────────────


class TestRealDocsConsistency:
    """skill 文档声明的 action 必须被脚本真实支持。"""

    def test_usage_actions_are_supported(self, cc) -> None:
        usage = (_SCRIPTS.parent / "USAGE.md").read_text(encoding="utf-8")
        assert "community-catalyst.py" in usage

    def test_skill_doc_actions_match_script(self, cc, wo) -> None:
        for skill_doc, module in (
            ("community-catalyst.md", cc),
            ("workflow-optimizer.md", wo),
        ):
            text = (_SCRIPTS.parent / "skills" / skill_doc).read_text(encoding="utf-8")
            for action in _declared_actions(text):
                assert action in _known_actions(module), f"{skill_doc} 声明了脚本不支持的 action: {action}"

    def test_skill_doc_documents_every_action(self, cc, wo) -> None:
        """反向：脚本支持的 action 必须都在 skill 文档里出现（防文档遗漏）。"""
        for skill_doc, module in (
            ("community-catalyst.md", cc),
            ("workflow-optimizer.md", wo),
        ):
            text = (_SCRIPTS.parent / "skills" / skill_doc).read_text(encoding="utf-8")
            missing = _known_actions(module) - set(_declared_actions(text))
            assert not missing, f"{skill_doc} 未记录脚本已支持的 action: {sorted(missing)}"


def _declared_actions(md: str) -> list[str]:
    """取文档 "- `action [args]`" 列表里的 action 名（去掉参数占位符）。"""
    import re

    return [m.group(1).split()[0] for m in re.finditer(r"^- `([^`]+)`", md, re.M)]


def _known_actions(module) -> set[str]:
    """从 main() 源码取出 action_map 的键。"""
    import ast

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "action_map":
            return {k.value for k in node.value.keys}
    return set()
