"""ADR-072「关于 FixEngine」小节的真实复核。

此前 FixEngine 的兜底只经由 ``tests/test_adg_new_modules.py`` 间接触及,
从未有人**直接调用**并观察返回字典与磁盘字节。本用例把 ADR-072 记录的
样本原样喂进去, 打印真实观察值, 锁定三件事:

1. 缺陷样本: 返回 ``success=False`` 且 ``syntax_violation=True``,
   ``fixes_applied == 0``, 磁盘**逐字节不变**;
2. 对照组: 合法样本照常修复, 防兜底退化成"永不修复";
3. 无缺陷样本: 不触发兜底, ``syntax_violation`` 键根本不出现。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.fix_engine import FixEngine  # noqa: E402

# ADR-072「关于 FixEngine」记录的原始缺陷样本, 逐字复制。
# 该样本经 SEC002 (os.system -> subprocess.run) 修复后会变成非法 Python,
# 因为 fixes.yml 的 ``[^)]+`` 捕获组在嵌套括号处截断了参数列表。
BROKEN_SAMPLE = 'import os\ncmd = os.system(f"ls {d()}")\n'

# 合法样本: SEC002 修复后仍是可解析 Python, 用作对照组。
HEALTHY_SAMPLE = 'import os\ncmd = os.system("ls")\n'

# 无可修复项的健康样本: 兜底完全不应介入。
CLEAN_SAMPLE = "X = 1\n"


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()  # noqa: S324


class TestFixEngineSyntaxGuard:
    """ADR-072: FixEngine 写盘兜底的真实观察。"""

    def test_broken_sample_rejected_and_disk_untouched(self, tmp_path: Path) -> None:
        target = tmp_path / "s.py"
        target.write_text(BROKEN_SAMPLE, encoding="utf-8")
        before = _md5(target)

        result = FixEngine().fix_file(target, language="python")

        # 先打印真实观察值, 再断言 —— 失败时输出能直接说明实况。
        print(f"\n[缺陷样本] result={ {k: v for k, v in result.items() if k != 'fixes'} }")
        print(f"[缺陷样本] 磁盘 md5 {before[:12]} -> {_md5(target)[:12]}")
        print(f"[缺陷样本] 磁盘内容={target.read_text(encoding='utf-8')!r}")

        assert result["success"] is False, result
        assert result.get("syntax_violation") is True, result
        assert result.get("fixes_applied") == 0, result
        assert _md5(target) == before, "磁盘被写坏了"
        assert target.read_text(encoding="utf-8") == BROKEN_SAMPLE
        # 错误信息必须可执行: 指明是哪个异常, 而非"修复失败"这种空话。
        assert "ADR-072" in result["error"], result["error"]

    def test_healthy_sample_still_fixed(self, tmp_path: Path) -> None:
        """对照组: 兜底不得退化成"永不修复"。"""
        target = tmp_path / "ok.py"
        target.write_text(HEALTHY_SAMPLE, encoding="utf-8")
        before = _md5(target)

        result = FixEngine().fix_file(target, language="python")

        print(f"\n[合法样本] result={ {k: v for k, v in result.items() if k != 'fixes'} }")
        print(f"[合法样本] 磁盘 {before[:12]} -> {_md5(target)[:12]}  内容={target.read_text(encoding='utf-8')!r}")

        assert result["success"] is True, result
        assert result["fixes_applied"] >= 1, result
        assert _md5(target) != before, "合法修复未落盘, 兜底可能退化成永不修复"
        compile(target.read_text(encoding="utf-8"), str(target), "exec")  # 仍可解析

    def test_clean_sample_guard_not_engaged(self, tmp_path: Path) -> None:
        """无可修复项时兜底不应出现, 否则说明它在无条件介入。"""
        target = tmp_path / "clean.py"
        target.write_text(CLEAN_SAMPLE, encoding="utf-8")

        result = FixEngine().fix_file(target, language="python")

        print(f"\n[干净样本] result={ {k: v for k, v in result.items() if k != 'fixes'} }")
        assert "syntax_violation" not in result, result

    def test_dry_run_never_writes_and_never_triggers_guard(self, tmp_path: Path) -> None:
        """dry_run 下不得写盘, 也不该因未落盘的结果去报语法违规。"""
        target = tmp_path / "dry.py"
        target.write_text(BROKEN_SAMPLE, encoding="utf-8")
        before = _md5(target)

        result = FixEngine().fix_file(target, language="python", dry_run=True)

        print(f"\n[dry_run] result={ {k: v for k, v in result.items() if k != 'fixes'} }")
        assert _md5(target) == before, "dry_run 竟写了盘"
        assert result.get("syntax_violation") is not True, result
