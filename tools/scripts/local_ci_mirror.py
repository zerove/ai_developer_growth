#!/usr/bin/env python3
"""本地 CI 镜像：用本地工具链跑一遍远端 workflow 的等价门禁。

## 为什么

私有仓库的 GitHub Actions 消耗账户分钟配额，配额耗尽时 run 会被立即拒绝
（job 被创建但 `steps` 全空），远端门禁**一次都没真正执行** —— 见 ADR-057。
此时若没有本地等价物，"远端绿灯"就成了假象；而仓库里其实已经有全部对应工具
（hooks_runner / governance 脚本 / 规则引擎），只是没有被组织成"一次跑完"的入口。

本脚本把远端 job 映射到**本地可执行**的等价命令，逐项给出
PASS / FAIL / SKIP + 耗时，并汇总退出码：

- FAIL → 退出码非 0（与 CI 一致，阻断）；
- SKIP → **显式报告**（缺工具/需网络），不静默放过；
  `--strict-skips` 可把 SKIP 视为失败。

## 用法

    python -m tools.scripts.local_ci_mirror                 # 跑全部本地等价门禁
    python -m tools.scripts.local_ci_mirror --list          # 列出门禁清单
    python -m tools.scripts.local_ci_mirror --only lint test # 只跑指定门禁
    python -m tools.scripts.local_ci_mirror --skip test      # 跳过指定门禁
    python -m tools.scripts.local_ci_mirror --incremental    # 测试走增量模式
    python -m tools.scripts.local_ci_mirror --json           # 机器可读输出
    python -m tools.scripts.local_ci_mirror --strict-skips    # SKIP 也算失败

退出码: 0 全部通过（或仅 SKIP 且未开 --strict-skips）/ 1 存在失败。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # python -m tools.scripts.local_ci_mirror (根已在 path)
    from tools.scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # python tools/scripts/local_ci_mirror.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


@dataclass(frozen=True)
class Gate:
    """一个本地等价门禁。"""

    name: str
    command: tuple[str, ...]
    requires: tuple[str, ...] = ()
    note: str = ""
    optional: bool = False  # 仅供参考的门禁（如远端存活探测），失败不阻断

    def missing_tools(self) -> list[str]:
        """缺失的外部工具（缺失则跳过，而不是假装通过）。"""
        return [tool for tool in self.requires if shutil.which(tool) is None]


@dataclass
class GateResult:
    """单个门禁的执行结果。"""

    name: str
    status: str
    duration: float = 0.0
    detail: str = ""
    optional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "duration": round(self.duration, 2),
            "detail": self.detail,
            "optional": self.optional,
        }


@dataclass
class GateRegistry:
    """门禁清单（远端 job → 本地等价命令）。"""

    gates: list[Gate] = field(default_factory=list)

    def names(self) -> list[str]:
        return [gate.name for gate in self.gates]

    def select(self, only: list[str], skip: list[str]) -> list[Gate]:
        gates = self.gates
        if only:
            wanted = set(only)
            unknown = wanted - set(self.names())
            if unknown:
                raise ValueError(f"未知门禁: {', '.join(sorted(unknown))}")
            gates = [gate for gate in gates if gate.name in wanted]
        if skip:
            skipped = set(skip)
            gates = [gate for gate in gates if gate.name not in skipped]
        return gates


def _python() -> str:
    """优先用仓库虚拟环境的解释器。"""
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def build_registry() -> GateRegistry:
    """构建门禁清单（与 .github/workflows/jobs-*.yml 一一对应）。"""
    py = _python()
    runner = (py, "-m", "tools.scripts.hooks_runner")
    return GateRegistry(
        gates=[
            Gate("lint", (*runner, "lint"), note="ruff check（对应 jobs-lint.yml）"),
            Gate("format", (*runner, "format"), note="ruff format --check（对应 jobs-lint.yml）"),
            Gate("typecheck", (*runner, "typecheck"), note="mypy（对应 jobs-type-check.yml）"),
            Gate("test", (*runner, "test"), note="pytest（对应 jobs-tests.yml）"),
            Gate(
                "quality-gate", (*runner, "quality-gate", "--full"), note="规则引擎门禁（对应 jobs-quality-gates.yml）"
            ),
            Gate("baseline", (*runner, "baseline", "recompute"), note="基线一致性（对应 doctor-gate）"),
            Gate("governance-audit", (*runner, "governance-audit"), note="治理审计（对应 jobs-governance-audit.yml）"),
            Gate("docs-validate", (*runner, "docs-validate", "full"), note="治理文档校验（对应 docs-governance.yml）"),
            Gate("link-audit", (py, "tools/scripts/link_auditor.py", ".", "--check-all"), note="断链检查"),
            Gate("case-study", (py, "tools/scripts/validate_case_study.py", "--all", "--strict"), note="案例格式"),
            Gate(
                "tool-matrix",
                (py, "-m", "tools.scripts.update_ai_tool_matrix", "--check"),
                note="工具矩阵一致性",
            ),
            Gate(
                "agent-validation",
                (py, "tools/scripts/validate_agent_definition.py", "--path", "agents/"),
                note="Agent 定义校验（对应 jobs-agent-validation.yml）",
            ),
            Gate("semantic-graph", (py, "-m", "tools.scripts.semantic_code_graph"), note="语义代码图"),
            Gate("arch-guard", (py, "-m", "tools.scripts.architecture_drift_guard"), note="架构漂移防御"),
            Gate("secret-scan", (*runner, "secret-scan"), requires=("gitleaks",), note="密钥扫描（需 gitleaks）"),
            Gate("sbom", (*runner, "sbom", "--output", ".cache/local-ci-sbom.json"), note="SBOM 生成"),
            Gate("dep-graph", (*runner, "dep-graph"), note="依赖图分析（对应 jobs-dependency-graph.yml）"),
            Gate("ci-heartbeat", (*runner, "ci-heartbeat"), optional=True, note="远端门禁存活探测（仅告警）"),
        ]
    )


def run_gate(gate: Gate, cwd: Path = REPO_ROOT) -> GateResult:
    """执行单个门禁，返回结果（缺工具 → skipped，不静默通过）。"""
    missing = gate.missing_tools()
    if missing:
        return GateResult(
            name=gate.name,
            status=STATUS_SKIPPED,
            detail=f"缺少工具: {', '.join(missing)}（未执行，非通过）",
            optional=gate.optional,
        )

    started = time.monotonic()
    try:
        completed = subprocess.run(list(gate.command), cwd=cwd, check=False)  # noqa: S603 - 命令为内置常量
        code = completed.returncode
    except OSError as exc:
        return GateResult(
            name=gate.name,
            status=STATUS_SKIPPED,
            detail=f"无法执行: {exc}",
            optional=gate.optional,
        )
    duration = time.monotonic() - started

    status = STATUS_PASSED if code == 0 else STATUS_FAILED
    return GateResult(
        name=gate.name,
        status=status,
        duration=duration,
        detail=f"exit={code}",
        optional=gate.optional,
    )


def summarize(results: list[GateResult], strict_skips: bool = False) -> dict[str, Any]:
    """汇总结果 → 退出码语义（FAIL 或（strict 下的）SKIP → 失败）。"""
    passed = sum(1 for r in results if r.status == STATUS_PASSED)
    failed = [r for r in results if r.status == STATUS_FAILED and not r.optional]
    skipped = [r for r in results if r.status == STATUS_SKIPPED]
    blocking_failed = bool(failed) or (strict_skips and bool(skipped))
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(failed),
        "skipped": len(skipped),
        "ok": not blocking_failed,
        "strict_skips": strict_skips,
    }


def _print_text(results: list[GateResult], summary: dict[str, Any]) -> None:
    """文本报告：逐项状态 + 汇总。"""
    icons = {STATUS_PASSED: "✅", STATUS_FAILED: "❌", STATUS_SKIPPED: "⏭️ "}
    for result in results:
        icon = icons.get(result.status, "?")
        if result.optional and result.status != STATUS_PASSED:
            icon = "⚠️ "
        suffix = " (仅告警)" if result.optional else ""
        print(f"{icon} {result.name:<20} {result.duration:6.1f}s  {result.detail}{suffix}")
    print("")
    print(
        f"汇总: 通过 {summary['passed']}/{summary['total']}，失败 {summary['failed']}，"
        f"跳过 {summary['skipped']}（跳过项未被执行，不等于通过）"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="本地 CI 镜像（远端 Actions 不可用时的等价门禁）")
    parser.add_argument("--list", action="store_true", help="只列出门禁清单")
    parser.add_argument("--only", nargs="+", default=[], help="只跑指定门禁（空格分隔，可重复该参数）")
    parser.add_argument("--skip", nargs="+", default=[], help="跳过指定门禁（空格分隔，可重复该参数）")
    parser.add_argument("--incremental", action="store_true", help="测试走增量模式（仅跑相关测试）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--strict-skips", action="store_true", help="把跳过项也视为失败")
    args = parser.parse_args(argv)

    registry = build_registry()
    if args.list:
        for gate in registry.gates:
            tools = f" [需要: {', '.join(gate.requires)}]" if gate.requires else ""
            print(f"{gate.name:<20} {gate.note}{tools}")
        return 0

    try:
        gates = registry.select(args.only, args.skip)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.incremental:
        gates = [
            Gate("test", (*g.command[:-1], "--incremental"), note=g.note) if g.name == "test" else g for g in gates
        ]

    results = [run_gate(gate) for gate in gates]
    summary = summarize(results, args.strict_skips)

    if args.json:
        print(json.dumps({"results": [r.to_dict() for r in results], "summary": summary}, ensure_ascii=False))
    else:
        _print_text(results, summary)

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
