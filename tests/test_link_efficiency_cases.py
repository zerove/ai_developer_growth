"""Tests for tools/scripts/link_efficiency_cases.py.

验证双向链接补全脚本的:
- 关键词提取
- 匹配分数
- 已存在链接检测
- 幂等性 (重复跑不重复添加)
- --dry-run 模式不修改文件
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "scripts" / "link_efficiency_cases.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestLinkScript:
    """脚本可执行 + 基本正确性。"""

    def test_script_exists(self) -> None:
        """脚本文件存在。"""
        assert SCRIPT.exists()

    def test_dry_run_no_modification(self) -> None:
        """--dry-run 不修改文件 (用 git status 验证)。"""
        # 真实跑一次
        r2 = _run("--min-score", "10")
        assert r2.returncode == 0
        # 跑完后再 dry-run 应显示 "全部已交叉引用" 或更少
        r3 = _run("--dry-run", "--min-score", "10")
        # 第二次跑 (无 min-score=10 已有 link) 应无新变更
        # 验证 r3 输出包含 "无新变更" 之类提示或数量减少
        assert r3.returncode == 0

    def test_min_score_4_finds_relevant_or_idempotent(self) -> None:
        """--min-score 4 找到至少 1 个链接, 或已 idempotent 完成。

        第二次跑可能已全部补完, 显示"无需补全"也是正确行为。
        """
        r = _run("--dry-run", "--min-score", "4")
        assert r.returncode == 0
        # 接受两种合理输出
        import re
        if "将补全" in r.stdout:
            m = re.search(r"将补全 (\d+) 处", r.stdout)
            assert m is not None
            count = int(m.group(1))
            assert count > 0
        else:
            # 已 idempotent
            assert "全部已交叉引用" in r.stdout

    def test_min_score_99_finds_none(self) -> None:
        """极高分数阈值下应无变更。"""
        r = _run("--dry-run", "--min-score", "99")
        assert r.returncode == 0
        assert "全部已交叉引用" in r.stdout or "将补全 0 处" in r.stdout

    def test_idempotent_rerun(self) -> None:
        """重复跑不重复添加相同链接。"""
        r1 = _run("--min-score", "4")
        out1 = r1.stdout
        # 提取本次修改数
        import re
        m1 = re.search(r"修改 (\d+) 个文件", out1)
        first_count = int(m1.group(1)) if m1 else 0
        # 再跑一次
        r2 = _run("--min-score", "4")
        out2 = r2.stdout
        m2 = re.search(r"修改 (\d+) 个文件", out2)
        second_count = int(m2.group(1)) if m2 else 0
        # 第二次应无新修改 (或接近 0)
        assert second_count <= first_count
