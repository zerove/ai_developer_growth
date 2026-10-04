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
    """`--fix` 是死参数: 被解析、被文档化, 但从未被读取。

    这组用例的作用是**记录当前真实行为**, 而不是主张它应该这样。
    修复它属于 CLI 行为变更（从"永不写盘"变成"按 --fix 写盘"）,
    且还需同时让规则集携带 ``fix_replacement``（见
    ``test_second_layer_blocks_writes_even_if_wired``）,
    与 ADR-072 的写盘兜底是不同范围的事, 需单独评估。

    若将来有人修了这个参数, 本组用例会红 —— 那是**预期的**:
    那意味着行为变了, 需要同步更新 ADR-072 的记录。
    """

    FIX_FLAG_REFERENCES = 0

    def test_args_fix_is_never_read(self) -> None:
        """validators/cli.py 里 args.fix 的引用数必须是 0（当前事实）。"""
        import ast as _ast

        cli_path = Path(__file__).resolve().parent.parent / "tools/scripts/rules_engine/validators/cli.py"
        tree = _ast.parse(cli_path.read_text(encoding="utf-8"))

        refs = 0
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Attribute) and node.attr == "fix":
                refs += 1

        assert refs == self.FIX_FLAG_REFERENCES, (
            f"args.fix 现在有 {refs} 处引用（原先 0 处）。"
            "若这是有意修复 --fix 死参数, 请同步更新 ADR-072 的「附带发现」一节。"
        )

    def test_fix_flag_is_documented_in_help(self) -> None:
        """--fix 仍被列为正式选项 —— 与「从未被读取」并存, 正是问题所在。"""
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

    def test_second_layer_blocks_writes_even_if_wired(self) -> None:
        """第二层遮蔽: 实际加载的规则集不带 fix_replacement, 接上参数也不写盘。

        这是比 `args.fix` 更深的一层 —— 即使把参数接上, 只要规则数据里
        没有 `fix_replacement`, ``apply_fixes`` 就会合理地返回 0 条。
        记录这一点是为了避免"接上 --fix 就完事"的错误预期。
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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
