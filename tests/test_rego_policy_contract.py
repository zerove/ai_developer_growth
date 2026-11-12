"""OPA/Rego 策略文件的契约测试。

背景（真实失效形态）:
    策略文件此前使用 Rego v0 语法（部分集合规则写 `violation[{...}] { ... }`、
    直接点号访问 `vuln.package`、用 `join` 拼接字符串）。OPA 1.x 默认启用
    rego.v1，这三种写法在 OPA 1.x 下都会直接 parse/compile 失败：

    - `violation[{...}] { ... }` → v1 要求 `violation contains {...} if { ... }`
    - `vuln.package` → `package` 是 v1 保留字，必须写成 `vuln["package"]`
    - `join(...)` → v1 已移除该内置函数，必须用 `concat(...)`

    失败发生在 `opa eval` 阶段 → 策略作业必红。本地无 OPA 可执行文件时
    退化为静态检查（语法要点逐条断言），有 OPA 时额外跑 `opa check`。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
POLICY_FILE = ROOT / ".jcode" / "policies" / "governance.rego"


def _policy_text() -> str:
    return POLICY_FILE.read_text(encoding="utf-8")


class TestRegoV1Syntax:
    def test_imports_rego_v1(self) -> None:
        assert "import rego.v1" in _policy_text(), "缺少 import rego.v1 (OPA 1.x 默认 v1 语法)"

    def test_partial_rules_use_contains(self) -> None:
        """v1 的部分集合规则必须写 contains，否则 parse 失败。"""
        text = _policy_text()
        assert "violation[{" not in text, "仍在使用 v0 的 violation[{...}] 写法"
        assert text.count("violations contains {") >= 5, "部分集合规则数量异常"

    def test_rule_name_matches_workflow_query(self) -> None:
        """规则名必须是 violations —— 工作流按 `.value.violations` 取违规数。

        规则名写成单数 `violation` 时，工作流的 jq 永远取不到值（恒为 0 条），
        策略门禁形同虚设且不会报错。
        """
        text = _policy_text()
        assert "\nviolation contains {" not in text, "规则名必须是 violations（与工作流查询一致）"
        assert "\nviolations contains {" in text

    def test_no_reserved_keyword_field_access(self) -> None:
        """`package` 是 v1 保留字，不能用点号访问字段。"""
        text = _policy_text()
        for name in ("vuln", "conflict", "stale", "dep", "result"):
            assert f"{name}.package" not in text, f"{name}.package 在 v1 下是保留字冲突"

    def test_join_replaced_by_concat(self) -> None:
        """v1 已移除 join 内置函数。"""
        assert "join(" not in _policy_text(), "join 在 rego v1 下已移除, 需改用 concat"


class TestRegoPolicyBehaviour:
    @pytest.mark.skipif(shutil.which("opa") is None, reason="本地无 opa 可执行文件")
    def test_opa_check_passes(self) -> None:
        result = subprocess.run(
            ["opa", "check", str(POLICY_FILE.parent)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"opa check 失败: {result.stderr}"


def test_policy_dir_is_tracked() -> None:
    """策略目录必须随仓库走（策略作业从 .jcode/policies 读取）。"""
    assert POLICY_FILE.exists(), "缺少 governance.rego"
    assert os.access(POLICY_FILE, os.R_OK)
