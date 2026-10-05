"""写盘兜底路径的真实契约测试（FixEngine / fix_applier）。

## 为什么要这组用例

ADR-072 收口复核时发现两件事:

1. **一处事实错误**: `fix_applier` 曾被记为"无生产调用方", 实测有两个
   生产调用方（`validators/cli.py::_apply_auto_fix` → CLI
   `validate_language_rules.py --fix`, 以及同名包装）。
2. **一个死参数**: `args.fix` 在 `validators/cli.py` 里引用数为 0,
   `--fix` 被 argparse 解析、被 `--help` 列为正式选项, 却从未被读取。

本模块把"真实入口是什么"锁死, 避免下一个人依据陈旧注释去验证一条
**不可达**的写盘路径（那里的兜底存在但永远不会被触发）。

## 契约要点

`apply_fixes` 的字面量替换取 ``issue.message`` **最后一个冒号之后**的
文本作为被替换串, 把 ``issue.fix_replacement`` 作为替换结果。所以夹具
必须写成 ``"replace: <原文>"``, 否则 ``split(":")[-1].strip()`` 取到的
不是原文, 替换静默不发生, 返回 0 条 —— **看起来"通过"实则空转**。
"""

import ast
import hashlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tools.fix_engine import FixEngine
from tools.scripts.fix_applier import apply_fixes
from tools.scripts.rules_engine.models import Issue

# 真实缺陷样本: 修复后必然语法非法（ADR-072 记录）
BAD_REGEX_SRC = 'import os\ncmd = os.system(f"ls {d()}")\n'
# 合法修复对照
VALID_SRC = "import os\nos.system('ls')\n"


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()[:12]


def _parses(p: Path) -> bool:
    try:
        ast.parse(p.read_text())
        return True
    except SyntaxError:
        return False


def _issue(message: str, replacement: str, line: int) -> Any:
    """构造 issue。message 最后一个冒号之后必须正是被替换文本。"""
    return Issue(
        rule_id="probe",
        severity="warning",
        category="style",
        file="s.py",
        line=line,
        message=message,
        fix_replacement=replacement,
    )


class TestFixEngineWriteFallback:
    """FixEngine: 修复结果不可解析时不得写盘。"""

    def test_broken_result_refuses_write(self, tmp_path: Path) -> None:
        target = tmp_path / "s.py"
        target.write_text(BAD_REGEX_SRC, encoding="utf-8")
        before = _md5(target)

        result = FixEngine().fix_file(target, language="python")

        assert result["success"] is False
        assert result["syntax_violation"] is True
        assert result["fixes_applied"] == 0
        assert _md5(target) == before, "被拒文件被改写 —— 磁盘已损坏"

    def test_valid_result_still_applies(self, tmp_path: Path) -> None:
        """对照组: 防兜底退化成"永不修复"。"""
        target = tmp_path / "s.py"
        target.write_text(VALID_SRC, encoding="utf-8")
        before = _md5(target)

        result = FixEngine().fix_file(target, language="python")

        assert result["success"] is True
        assert result["fixes_applied"] == 1
        assert _md5(target) != before, "合法修复未生效"
        assert _parses(target), "修复后文件无法解析"

    def test_no_violation_key_when_nothing_applied(self, tmp_path: Path) -> None:
        """无可修复项时不得凭空出现 syntax_violation。"""
        target = tmp_path / "s.py"
        target.write_text('"""M."""\n\nX = 1\n', encoding="utf-8")

        result = FixEngine().fix_file(target, language="python")

        assert result.get("syntax_violation") is None, result


class TestFixApplierWriteFallback:
    """fix_applier: 字面量与 sed 两条替换分支都不得写坏文件。"""

    def test_literal_replacement_refuses_broken_write(self, tmp_path: Path) -> None:
        target = tmp_path / "s.py"
        target.write_text("x = 1\ny = 2\n", encoding="utf-8")
        before = _md5(target)

        # message 冒号后的 "2" 是被替换文本; 替换结果 "(2" 会造成语法非法。
        results = apply_fixes(target, [_issue("replace: 2", "(2", 2)])

        assert len(results) == 1
        assert results[0].rule_id == "syntax-check-rejected"
        assert results[0].fixed == "[MANUAL FIX REQUIRED]"
        assert _md5(target) == before, "被拒文件被改写 —— 磁盘已损坏"

    def test_literal_replacement_valid_control(self, tmp_path: Path) -> None:
        target = tmp_path / "s.py"
        target.write_text(VALID_SRC, encoding="utf-8")
        before = _md5(target)

        results = apply_fixes(target, [_issue("replace: os.system('ls')", "subprocess.run('ls')", 2)])

        assert len(results) == 1
        assert results[0].rule_id == "probe", results[0].rule_id
        assert _md5(target) != before, "合法修复未生效"
        assert _parses(target), "修复后文件无法解析"

    def test_sed_branch_control(self, tmp_path: Path) -> None:
        """sed 风格分支的对照组 —— 防止只测了字面量一条分支。"""
        target = tmp_path / "s.py"
        target.write_text("value = 1\n", encoding="utf-8")
        before = _md5(target)

        results = apply_fixes(target, [_issue("sed: s/1/2/", "s/1/2/", 1)])

        assert len(results) == 1
        assert results[0].rule_id == "probe"
        assert _md5(target) != before, "sed 分支未生效"
        assert _parses(target), "修复后文件无法解析"

    def test_dry_run_leaves_disk_untouched(self, tmp_path: Path) -> None:
        target = tmp_path / "s.py"
        target.write_text("x = 1\ny = 2\n", encoding="utf-8")
        before = _md5(target)

        apply_fixes(target, [_issue("replace: 2", "(2", 2)], dry_run=True)

        assert _md5(target) == before, "dry_run 仍写了盘"


class TestValidatorsCliFixFlagIsDead:
    """``--fix`` 的真实行为契约。

    历史：``--fix`` 曾被解析、被 ``--help`` 文档化，却从未被读取，且
    ``_handle_auto_fix`` 是**无条件**调用的 —— 当时"不写盘"并不来自任何
    设计，只是恰好没有可应用的 ``fix_replacement``。ADR-072 配套修复后，
    写入必须显式传 ``--fix``。

    本组用真实 ``--custom-rules`` 规则（携带 ``fix_replacement``）端到端验证
    三态语义，替代原先"只看源码里有没有引用 args.fix"的弱断言。
    """

    def test_args_fix_is_actually_read(self) -> None:
        """``args.fix`` 必须被真实读取（原先 0 处，死参数）。

        这条断言从"记录缺陷"转为"防守回归"：若有人重构时把 gating 删掉，
        就会重新变成"不传 ``--fix`` 也可能改盘"。
        """
        import ast as _ast

        cli_path = Path(__file__).resolve().parent.parent / "tools/scripts/rules_engine/validators/cli.py"
        tree = _ast.parse(cli_path.read_text(encoding="utf-8"))

        refs = 0
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Attribute) and node.attr == "fix":
                refs += 1

        assert refs >= 1, (
            "args.fix 又变成 0 处引用 —— --fix 死参数回归。"
            "CLI 会在用户未要求时尝试写盘（虽然当前规则集恰好无可应用修复，"
            "但那只是巧合，不是保障）。"
        )

    def test_fix_flag_is_documented_in_help(self) -> None:
        """--fix 仍被列为正式选项, 且帮助文本应说明它会写盘。"""
        import subprocess
        import sys

        cli = Path(__file__).resolve().parent.parent / "tools/scripts/validate_language_rules.py"
        proc = subprocess.run(
            [sys.executable, str(cli), "--help"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert "--fix" in proc.stdout, "--fix 已从 --help 中消失, ADR-072 记录需更新"
        assert "writes to disk" in proc.stdout, "--fix 的帮助文本未说明会写盘, 用户预期会被误导"

    def test_second_layer_blocks_writes_even_if_wired(self) -> None:
        """仓库自带规则集不带 fix_replacement, 故生产环境仍不会写盘。

        这是比 ``args.fix`` 更深的一层 —— 即使参数接线正确, 只要实际加载的
        规则集没有 ``fix_replacement``, ``apply_fixes`` 就会返回 0 条。
        记录这一点是为了说明: **修好参数 ≠ 生产环境会开始改代码**。
        真正要开启自动修复, 还需要有人给规则补上 ``fix_replacement``。
        """
        repo = Path(__file__).resolve().parent.parent
        # validators/pipeline.py 只在规则定义含该字段时才填 issue.fix_replacement
        pipeline = (repo / "tools/scripts/rules_engine/validators/pipeline.py").read_text(encoding="utf-8")
        assert 'if "fix_replacement" in rule_def' in pipeline, (
            "pipeline.py 不再按 fix_replacement 填充 issue, ADR-072 的第二层分析需重做"
        )

        # 全仓仅 security.yml 带该字段 —— 实际加载的规则集不含它
        yml_with_fix = [
            p.relative_to(repo).as_posix()
            for p in repo.rglob("*.yml")
            if "fix_replacement" in p.read_text(encoding="utf-8", errors="ignore") and "node_modules" not in p.parts
        ]
        assert all("security.yml" in path for path in yml_with_fix), (
            f"新增了带 fix_replacement 的规则文件: {yml_with_fix}。请复核 --fix 是否已变得可达, 并同步更新 ADR-072。"
        )
        assert yml_with_fix, "没有任何规则文件带 fix_replacement —— 若属实请确认 ADR-072 描述仍准确"


class TestFixFlagEndToEnd:
    """真实 CLI 端到端验证 ``--fix`` 三态。

    前面的用例是静态断言（源码里有没有引用），只能证明"参数被读了"。
    本组用一条携带 ``fix_replacement`` 的真实规则驱动**真实子进程**，
    验证的是用户真正关心的语义：不传 ``--fix`` 绝不能碰磁盘。
    """

    @staticmethod
    def _make_fixture(tmp_path: Path) -> tuple[Path, Path]:
        """构造 ``<tmp>/rules/.ai-rules/r.yml`` + ``<tmp>/proj/s.py``。

        注意目录层级：``--custom-rules`` 接受的是**包含** ``.ai-rules/`` 的
        项目目录，而非 ``.ai-rules`` 自身（由 ``load_custom_rules`` 决定）。
        """
        rules_dir = tmp_path / "rules" / ".ai-rules"
        rules_dir.mkdir(parents=True)
        proj = tmp_path / "proj"
        proj.mkdir()
        (rules_dir / "r.yml").write_text(
            "anti_patterns:\n"
            "  - id: probe-rule\n"
            '    pattern: "TODO_PROBE"\n'
            # message 必须含冒号：_apply_literal_replacement 靠冒号后的文本
            # 定位待替换内容（无冒号时另有守卫，本用例专注 flag 语义）。
            '    message: "remove marker: TODO_PROBE"\n'
            "    severity: warning\n"
            '    fix_replacement: "DONE"\n',
            encoding="utf-8",
        )
        target = proj / "s.py"
        target.write_text('x = "TODO_PROBE"\n', encoding="utf-8")
        return proj, target

    @staticmethod
    def _run(repo: Path, proj: Path, rules: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        import sys

        return subprocess.run(
            [
                sys.executable,
                str(repo / "tools/scripts/validate_language_rules.py"),
                str(proj),
                "--lang",
                "python",
                "--custom-rules",
                str(rules),
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

    def test_no_flag_does_not_touch_disk(self, tmp_path: Path) -> None:
        """不带 ``--fix``：即使规则可修复，也必须一个字节都不写。"""
        repo = Path(__file__).resolve().parent.parent
        proj, target = self._make_fixture(tmp_path)
        before = target.read_bytes()

        proc = self._run(repo, proj, tmp_path / "rules")

        assert target.read_bytes() == before, "未传 --fix 却改写了文件"
        # 健康对照：规则确实被检出（否则本用例会因"无事发生"而假绿）
        assert "probe-rule" in proc.stdout, f"规则未被检出，用例失去意义:\n{proc.stdout}"

    def test_dry_run_with_fix_does_not_touch_disk(self, tmp_path: Path) -> None:
        """``--fix --dry-run``：报告预览但不写盘。"""
        repo = Path(__file__).resolve().parent.parent
        proj, target = self._make_fixture(tmp_path)
        before = target.read_bytes()

        proc = self._run(repo, proj, tmp_path / "rules", "--fix", "--dry-run")

        assert target.read_bytes() == before, "--dry-run 却改写了文件"
        assert "Would fix" in proc.stdout, f"未报告预览:\n{proc.stdout}"

    def test_fix_flag_writes_and_keeps_file_parsable(self, tmp_path: Path) -> None:
        """``--fix``：真正写盘，且结果必须仍可解析（ADR-072 兜底生效）。"""
        repo = Path(__file__).resolve().parent.parent
        proj, target = self._make_fixture(tmp_path)
        before = target.read_bytes()

        proc = self._run(repo, proj, tmp_path / "rules", "--fix")

        assert target.read_bytes() != before, "--fix 未改写文件（死参数回归？）"
        assert 'x = "DONE"' in target.read_text(encoding="utf-8"), (
            f"替换结果不符合预期:\n{target.read_text(encoding='utf-8')}"
        )
        ast.parse(target.read_text(encoding="utf-8"))
        assert "Fixed" in proc.stdout, f"未如实报告已修复:\n{proc.stdout}"


class TestNoFixFlagMustNotSkipOutputStages:
    """不传 ``--fix`` 只应禁止写盘, **不得**跳过后续输出阶段。

    这是 ADR-072 gating 的直接连带缺陷, 也是本仓库第七类"假绿灯"形态:
    CLI **退出码为 0**, 看起来一切正常, 但 ``--json`` / ``--health-score``
    的输出被整段吞掉 —— 下游解析 JSON 的调用方会拿到空字符串。

    根因是 ``_apply_auto_fix`` 里有一个历史遗留的 ``return -1``
    "提前退出"信号, 而 ``main`` 把任何非 ``None`` 的返回值都当作
    "该退出了"。ADR-072 让**不传 ``--fix`` 也必须走 dry_run** 之后,
    只要 ``results`` 为空, 这个信号就必然被误触发。

    触发条件必须是 ``results`` 为空 —— 最可靠的构造是 ``--incremental``
    且文件未变化 (第二遍扫描时 ``results`` 就是空的)。
    """

    @staticmethod
    def _run(repo: Path, proj: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        import sys

        return subprocess.run(
            [
                sys.executable,
                str(repo / "tools/scripts/validate_language_rules.py"),
                str(proj),
                "--lang",
                "python",
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

    def _prime_incremental_cache(self, repo: Path, proj: Path) -> None:
        """先跑一遍填充增量缓存, 使下一遍的 ``results`` 为空。"""
        proc = self._run(repo, proj, "--incremental")
        assert proc.returncode == 0, f"填充缓存失败:\n{proc.stdout}\n{proc.stderr}"

    def test_json_output_survives_missing_fix_flag(self, tmp_path: Path) -> None:
        """``--json`` + 不传 ``--fix``: JSON 必须仍然打印出来。"""
        repo = Path(__file__).resolve().parent.parent
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "ok.py").write_text("x = 1\n", encoding="utf-8")
        self._prime_incremental_cache(repo, proj)

        proc = self._run(repo, proj, "--incremental", "--json")

        assert proc.returncode == 0, f"退出码应仍为 0:\n{proc.stdout}"
        assert '"results"' in proc.stdout, (
            "--json 输出被 auto-fix 阶段吞掉了。根因是 dry_run 同时激活了"
            "『不写盘』与『提前退出』两个语义（ADR-072 gating 的连带缺陷）。"
            f"实际输出:\n{proc.stdout}"
        )
        assert '"total_files": 0' in proc.stdout, f"JSON 内容不完整:\n{proc.stdout}"

    def test_health_score_survives_missing_fix_flag(self, tmp_path: Path) -> None:
        """``--health-score`` + 不传 ``--fix``: 分数必须仍然打印出来。"""
        repo = Path(__file__).resolve().parent.parent
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "ok.py").write_text("x = 1\n", encoding="utf-8")
        self._prime_incremental_cache(repo, proj)

        proc = self._run(repo, proj, "--incremental", "--health-score")

        assert "Health Score" in proc.stdout, f"--health-score 输出被吞掉了:\n{proc.stdout}"

    def test_output_is_identical_with_and_without_fix_flag(self, tmp_path: Path) -> None:
        """``--fix`` 只应影响写盘, 不应影响**输出内容**。

        这是本组最直接的契约: 两种调用下 stdout 必须逐字节一致。
        若 gating 让"不写盘"顺带改变了输出, 差异就会暴露在这里。
        """
        repo = Path(__file__).resolve().parent.parent
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "ok.py").write_text("x = 1\n", encoding="utf-8")
        self._prime_incremental_cache(repo, proj)

        without = self._run(repo, proj, "--incremental", "--json")
        with_fix = self._run(repo, proj, "--incremental", "--json", "--fix")

        assert without.returncode == with_fix.returncode, (
            f"--fix 改变了退出码: 不传={without.returncode} 传={with_fix.returncode}"
        )
        assert without.stdout == with_fix.stdout, (
            f"--fix 改变了输出内容 —— 它本应只影响写盘。\n不传 --fix:\n{without.stdout}\n\n传 --fix:\n{with_fix.stdout}"
        )

    def test_empty_results_no_longer_triggers_early_exit(self) -> None:
        """直接锁定 ``_apply_auto_fix`` 的返回值契约。

        它过去返回 ``-1`` 表示"提前退出"。该信号已被移除, 原因见类
        docstring。断言直接落在返回值上, 比端到端断言更早失败。
        """
        from tools.scripts.rules_engine.validators.cli import (
            _apply_auto_fix,
            _handle_auto_fix,
        )

        assert _apply_auto_fix([], dry_run=True) == 0, (
            "_apply_auto_fix 对空结果的 dry_run 调用不得再返回 -1 —— 该值是『提前退出』信号, 会让 main 吞掉后续输出阶段"
        )
        assert _handle_auto_fix([], dry_run=True) is None, (
            "_handle_auto_fix 必须返回 None 表示『继续』, 任何非 None 值都会让 main 提前 return 并跳过后续输出"
        )


class TestLiteralReplacementEmptyMatchText:
    """``_apply_literal_replacement`` 在 message 无冒号时**不得**改写该行。

    这是"写盘前语法自检"抓不到的一类损坏：``str.replace("", x)`` 把内容插到
    行首，产出的代码**语法合法但语义已错**，``ast.parse`` 不会报错。
    """

    def test_message_without_colon_leaves_line_untouched(self) -> None:
        from tools.scripts.fix_applier import _apply_literal_replacement

        line = 'x = "TODO"'
        assert _apply_literal_replacement(line, "DONE", "probe marker") == line, (
            "message 不含冒号时不得改写：str.replace('', x) 会把内容插入行首，产出语法合法但语义已错的代码"
        )

    def test_message_without_colon_makes_no_progress(self, tmp_path: Path) -> None:
        """端到端：这类 issue 不得产生任何写盘副作用。"""
        from tools.scripts.fix_applier import apply_fixes

        target = tmp_path / "s.py"
        target.write_text('x = "TODO"\n', encoding="utf-8")
        before = target.read_bytes()
        issue = Issue(
            rule_id="probe",
            line=1,
            message="probe marker",
            severity="warning",
            fix_replacement="DONE",
            category="style",
            file=str(target),
        )
        apply_fixes(target, [issue], dry_run=False)
        assert target.read_bytes() == before, "无法定位替换目标时却改写了文件"

    def test_message_with_colon_still_replaces(self) -> None:
        """健康对照：有冒号的 message 仍应正常替换（守卫不能过宽）。"""
        from tools.scripts.fix_applier import _apply_literal_replacement

        assert _apply_literal_replacement('x = "TODO"', "DONE", "remove marker: TODO") == 'x = "DONE"'


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
