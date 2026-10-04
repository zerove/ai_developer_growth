"""fix_applier 写盘兜底回归 (ADR-072 第四路径).

ADR-072 修好了三条写盘路径 (``ast_fixer`` / ``auto_fix`` / ``FixEngine``),
本文件补上第四条: ``tools/scripts/fix_applier.apply_fixes``。

取证 (本轮实测, 非推断): ``_apply_literal_replacement`` 取 ``message``
最后一个冒号后的文本做替换, ``fix_replacement`` 本身坏掉时会把文件改坏,
而旧实现仍如实返回 1 个 FixResult —— 即**声称修复成功**:

    输入: x = 1 / y = 2       替换 "2" -> "(2"
    磁盘: x = 1 / y = (2      -> SyntaxError: '(' was never closed
    返回: 1 个 FixResult

锁定三件事:
    1. 写盘结果不可解析时**一个字节都不写**, 且返回哨兵而非成功;
    2. 哨兵必须是 ``[MANUAL FIX REQUIRED]`` —— 留空会被汇总层计入
       auto-fixed, 正是 ADR-072 要消灭的假绿灯;
    3. 对照组: 合法替换照常落盘, 防兜底退化成"永不修复"。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.scripts.fix_applier import apply_fixes  # noqa: E402
from tools.scripts.rules_engine.validators.models import Issue  # noqa: E402

MANUAL = "[MANUAL FIX REQUIRED]"


def _issue(line: int, message: str, replacement: str) -> Issue:
    """构造 Issue; ``message`` 最后一个冒号之后即待替换子串。"""
    return Issue(
        rule_id="probe",
        severity="error",
        category="probe",
        file="",
        line=line,
        message=message,
        fix_replacement=replacement,
    )


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()  # noqa: S324


class TestFixApplierWriteGuard:
    """ADR-072 第四条写盘路径的兜底。"""

    def test_broken_replacement_refuses_to_write(self, tmp_path: Path) -> None:
        target = tmp_path / "s.py"
        target.write_text("x = 1\ny = 2\n", encoding="utf-8")
        before = _md5(target)

        fixes = apply_fixes(target, [_issue(2, "m: 2", "(2")])

        print(f"\n[缺陷样本] 返回={[(f.rule_id, f.fixed) for f in fixes]}")
        print(f"[缺陷样本] 磁盘 md5 {before[:12]} -> {_md5(target)[:12]}")

        assert len(fixes) == 1, fixes
        assert fixes[0].rule_id == "syntax-check-rejected", fixes[0].rule_id
        # 哨兵值是关键: 汇总层以它判定"是否已自动修复"
        assert fixes[0].fixed == MANUAL, fixes[0].fixed
        assert _md5(target) == before, "磁盘被写坏了"
        assert target.read_text(encoding="utf-8") == "x = 1\ny = 2\n"
        assert "ADR-072" in fixes[0].description, fixes[0].description

    def test_control_healthy_replacement_still_writes(self, tmp_path: Path) -> None:
        """对照组: 兜底不得退化成"永不修复"。"""
        target = tmp_path / "ok.py"
        src = "import os\ncmd = os.system('ls')\n"
        target.write_text(src, encoding="utf-8")
        before = _md5(target)

        fixes = apply_fixes(target, [_issue(2, "m: os.system('ls')", "subprocess.run('ls', shell=True)")])

        print(f"\n[合法样本] 返回={[(f.rule_id, f.fixed) for f in fixes]}")
        print(f"[合法样本] 磁盘 md5 {before[:12]} -> {_md5(target)[:12]}")
        print(f"[合法样本] 内容={target.read_text(encoding='utf-8')!r}")

        assert len(fixes) == 1, fixes
        assert fixes[0].rule_id == "probe", fixes[0].rule_id
        assert fixes[0].fixed != MANUAL, "合法修复被误判为拒绝"
        assert _md5(target) != before, "合法修复未落盘"
        compile(target.read_text(encoding="utf-8"), str(target), "exec")

    def test_dry_run_never_writes_even_when_broken(self, tmp_path: Path) -> None:
        target = tmp_path / "dry.py"
        target.write_text("x = 1\ny = 2\n", encoding="utf-8")
        before = _md5(target)

        fixes = apply_fixes(target, [_issue(2, "m: 2", "(2")], dry_run=True)

        assert _md5(target) == before, "dry_run 竟写了盘"
        # dry_run 下自检不应介入, 故不得报拒绝
        assert all(f.rule_id != "syntax-check-rejected" for f in fixes), fixes

    def test_sed_style_regex_replacement_still_works(self, tmp_path: Path) -> None:
        """另一条替换分支 (sed 风格) 也必须照常落盘, 防止只测了字面量分支。"""
        target = tmp_path / "sed.py"
        src = "try:\n    pass\nexcept:\n    pass\n"
        target.write_text(src, encoding="utf-8")
        before = _md5(target)

        fixes = apply_fixes(target, [_issue(3, "Avoid bare except", "s/except:/except Exception:/")])

        print(f"\n[sed 分支] 返回={[(f.rule_id, f.fixed) for f in fixes]}")
        print(f"[sed 分支] 磁盘 md5 {before[:12]} -> {_md5(target)[:12]}")

        assert len(fixes) == 1, fixes
        assert _md5(target) != before
        assert "except Exception:" in target.read_text(encoding="utf-8")
        compile(target.read_text(encoding="utf-8"), str(target), "exec")
