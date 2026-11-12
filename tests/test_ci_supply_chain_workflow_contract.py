"""供应链/依赖图工作流与 CLI 契约的测试。

背景（真实失效形态）:
    1. `jobs-supply-chain.yml` 里写的是 `${policy-file:+--policy-file "..."}` ——
       bash 的参数展开只认合法变量名，带连字符的 `policy-file` 被解析成
       `${policy` 加字面量，最终把 `file:+--policy-file` 当成 CLI 参数传进去，
       argparse 报 "unrecognized arguments" → 作业必失败。
    2. 作业里的 `dep-graph ... --sbom sbom.json` 是各 CI 模板成文的契约，
       但 CLI 只认 `--path`，且没有 `export` 子命令 → 4 个依赖图作业全红。
    3. 依赖图作业的 "Generate SBOM" 步骤带 `if: inputs.sbom-path == ''`，
       上游 sbom 作业的产物不会跨作业传递 → SBOM 文件根本不存在。

这些都不产生"看不懂"的报错，只是流水线恒红，因此用测试锁住契约。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from tools.scripts.hooks.runner_parsers import _add_dep_graph_parsers

ROOT = Path(__file__).resolve().parent.parent
SUPPLY_CHAIN_WORKFLOW = ROOT / ".github" / "workflows" / "jobs-supply-chain.yml"
DEP_GRAPH_WORKFLOW = ROOT / ".github" / "workflows" / "jobs-dependency-graph.yml"
ADVANCED_WORKFLOW = ROOT / ".github" / "workflows" / "advanced-governance.yml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps(path: Path, job: str) -> list[dict]:
    return _load(path)["jobs"][job]["steps"]


def _run_script(path: Path, job: str, step_name: str) -> str:
    for step in _steps(path, job):
        if step.get("name") == step_name:
            return str(step.get("run", ""))
    raise AssertionError(f"未找到步骤: {step_name}")


# ── supply-chain 作业 ───────────────────────────────────────


def test_supply_chain_step_avoids_invalid_parameter_expansion() -> None:
    """带连字符的变量名做参数展开会把字面量当 CLI 参数传出去。"""
    script = _run_script(SUPPLY_CHAIN_WORKFLOW, "supply-chain", "Run Supply Chain Action")
    code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))
    assert "policy-file:+" not in code, "仍使用非法变量名做参数展开"
    assert "output-file:+" not in code, "仍使用非法变量名做参数展开"


def test_supply_chain_step_passes_policy_file_explicitly() -> None:
    """策略文件必须通过合法变量传给 CLI, 且空值时不传该参数。"""
    script = _run_script(SUPPLY_CHAIN_WORKFLOW, "supply-chain", "Run Supply Chain Action")
    assert 'POLICY_FILE="${{ inputs.policy-file }}"' in script
    assert 'policy_args=(--policy-file "$POLICY_FILE")' in script


def test_supply_chain_setup_go_disables_cache() -> None:
    """仓库没有 go.sum, setup-go 的缓存恢复会报 "Dependencies file is not found"。"""
    go_steps = [s for s in _steps(SUPPLY_CHAIN_WORKFLOW, "supply-chain") if "setup-go" in str(s.get("uses", ""))]
    assert go_steps, "未找到 setup-go 步骤"
    assert go_steps[0]["with"].get("cache") is False, "无 go.sum 时必须显式关闭 setup-go 缓存"


# ── 依赖图作业 ──────────────────────────────────────────────


def test_dep_graph_workflow_uses_sbom_contract() -> None:
    """依赖图命令必须消费 --sbom 指定的 SBOM 文件。"""
    script = _run_script(DEP_GRAPH_WORKFLOW, "dependency-graph", "Run Dependency Graph Analysis")
    assert "--sbom" in script
    assert "dep-graph analyze" in script
    assert "dep-graph export" in script


def test_dep_graph_workflow_generates_sbom_locally() -> None:
    """SBOM 必须在本作业内生成 —— 上游作业的产物不会跨作业传递。"""
    steps = _steps(DEP_GRAPH_WORKFLOW, "dependency-graph")
    sbom_steps = [s for s in steps if s.get("name") == "Generate SBOM"]
    assert sbom_steps, "缺少本作业内的 SBOM 生成步骤"
    assert "if" not in sbom_steps[0], "SBOM 生成步骤不得被条件跳过"


def test_dep_graph_cli_accepts_sbom_for_every_action() -> None:
    """CLI 必须支持各动作的 --sbom 参数（与工作流/模板契约一致）。"""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_dep_graph_parsers(subparsers)
    for action in ("analyze", "circular", "conflicts"):
        args = parser.parse_args(["dep-graph", action, "--sbom", "sbom.json", "--format", "json"])
        assert args.sbom == Path("sbom.json"), f"{action} 未接受 --sbom"
    impact = parser.parse_args(["dep-graph", "impact", "--sbom", "sbom.json", "--package", "pkg"])
    assert impact.sbom == Path("sbom.json"), "impact 未接受 --sbom"


def test_dep_graph_cli_has_export_action() -> None:
    """export 子命令缺失会让模板里的 mermaid 导出作业必失败。"""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_dep_graph_parsers(subparsers)
    args = parser.parse_args(["dep-graph", "export", "--format", "mermaid"])
    assert args.format == "mermaid"


def test_advanced_governance_export_job_uses_mermaid() -> None:
    """流水线里的导出作业必须与 CLI 的 export 动作对齐。"""
    job = _load(ADVANCED_WORKFLOW)["jobs"]["dep-graph-export-mermaid"]
    assert job["with"]["action"] == "export"
    assert job["with"]["format"] == "mermaid"
