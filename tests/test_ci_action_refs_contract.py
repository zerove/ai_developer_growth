"""工作流 action 引用（owner/repo@ref）的契约测试。

背景（真实失效形态）:
    `open-policy-agent/setup-opa@v3` 与 `github/codeql-action/upload-sarif@v3`
    这两个 ref 在上游已经不存在（前者最新为 v2，后者最新为 v4），GitHub 会在
    作业启动阶段直接报 "Unable to resolve action ... unable to find version"，
    整条流水线红。这类缺陷只有在远端真正执行时才暴露，因此用测试把
    "允许使用的 ref 集合" 固定下来：任何 action 升降级都必须显式改测试。

同时记录几个已被上游删除、曾经把流水线打红的 ref，避免再次引入。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = ROOT / ".github" / "workflows"

#: 允许使用的第三方 action 引用 (本地 ./ 复用工作流不在此列)
ALLOWED_ACTION_REFS = {
    "actions/attest-build-provenance@v2",
    "actions/cache@v4",
    "actions/checkout@v4",
    "actions/dependency-review-action@v4",
    "actions/deploy-pages@v4",
    "actions/download-artifact@v4",
    "actions/github-script@v7",
    "actions/setup-go@v5",
    "actions/setup-java@v4",
    "actions/setup-node@v4",
    "actions/setup-python@v5",
    "actions/upload-artifact@v4",
    "actions/upload-pages-artifact@v3",
    "dtolnay/rust-toolchain@stable",
    "github/codeql-action/upload-sarif@v4",
    "open-policy-agent/setup-opa@v2",
    "pre-commit/action@v3.0.1",
    "pypa/gh-action-pypi-publish@release/v1",
    "sigstore/cosign-installer@v3.5.0",
    "slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v1.9.0",
    "softprops/action-gh-release@v2",
    "tj-actions/changed-files@v45",
}

#: 上游已删除、曾经把远端流水线打红的 ref —— 再次出现即为回归
FORBIDDEN_ACTION_REFS = {
    "actions-rust-lang/setup-rust@v1",  # 仓库不存在该 action
    "github/codeql-action/upload-sarif@v3",  # 上游只保留 v4
    "open-policy-agent/setup-opa@v3",  # 上游只保留 v2
}

_USES_PATTERN = re.compile(r"uses:\s*['\"]?([^'\"\s]+)")


def _collect_action_refs() -> set[str]:
    """收集工作流里用到的第三方 action 引用。"""
    refs: set[str] = set()
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for match in _USES_PATTERN.finditer(path.read_text(encoding="utf-8")):
            ref = match.group(1)
            if ref.startswith("./") or ref.startswith("docker://"):
                continue
            refs.add(ref)
    return refs


def test_action_refs_are_known_good() -> None:
    """工作流里的 action 引用必须来自允许集合（升级需显式改测试）。"""
    unknown = sorted(_collect_action_refs() - ALLOWED_ACTION_REFS)
    assert not unknown, f"出现了未登记的 action 引用（请确认上游存在该 ref 后再登记）: {unknown}"


def test_removed_action_refs_are_not_reintroduced() -> None:
    """已被上游删除的 ref 不得再次出现。"""
    used = _collect_action_refs()
    assert not (used & FORBIDDEN_ACTION_REFS), (
        f"重新引入了已被上游删除的 action: {sorted(used & FORBIDDEN_ACTION_REFS)}"
    )


def test_dependency_constraints_are_installable() -> None:
    """清单里的版本约束必须真的能装上（tree-sitter-swift 无 0.23.x 发布版本）。"""
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "tree-sitter-swift>=0.23" not in requirements, "tree-sitter-swift 未发布 0.23.x, 该约束无解"
