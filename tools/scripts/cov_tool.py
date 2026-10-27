"""覆盖率差分与单模块门禁工具: 防止覆盖率悄悄回退。

子命令:
  diff    对比两次 coverage.json, 输出按百分点排序的模块升降表
  module  单模块覆盖率 + 缺失行号 + 补测试建议
  gate    模块级门禁: 历史基线 -5pp 触发失败
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

# ADR-079: 统一路径引导 —— `python -m tools.scripts.X`（包上下文）与
# `python tools/scripts/X.py`（path[0]=tools/scripts）均由 _bootstrap 幂等补齐仓库根。
try:  # python -m tools.scripts.X (根已在 path)
    from tools.scripts import _bootstrap
except ModuleNotFoundError:  # python tools/scripts/X.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401


from tools.scripts._common import get_project_root  # noqa: E402


def _read_coverage_json(path: Path) -> dict[str, Any]:
    """Parse coverage.py JSON report; return empty dict on failure."""
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))
    except (OSError, json.JSONDecodeError):
        return {}


def _file_to_module(file_path: str) -> str:
    """Map coverage file path to module name (e.g. tools/scripts/foo.py → tools.scripts.foo)."""
    p = file_path
    if p.endswith(".py"):
        p = p[:-3]
    return p.replace("/", ".").lstrip(".")


def _module_summary(cov_data: dict[str, Any], module: str) -> dict[str, Any]:
    """Return {statements, missing, percent} for a dotted module path; {} if absent."""
    if not cov_data or "files" not in cov_data:
        return {}
    target = module.replace(".", "/") + ".py"
    if target not in cov_data["files"]:
        # also try the bare module form
        bare = module.split(".")[-1] + ".py"
        for f in cov_data["files"]:
            if f.endswith("/" + bare) or f == bare:
                target = f
                break
        else:
            return {}
    f = cov_data["files"][target]
    summary = f.get("summary", {})
    return {
        "statements": summary.get("num_statements", 0),
        "missing": summary.get("missing_lines", 0),
        "percent": summary.get("percent_covered", 0.0),
    }


def _gather_module_table(cov_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Flatten coverage JSON into {module_dotted: summary} dict."""
    out: dict[str, dict[str, Any]] = {}
    if not cov_data or "files" not in cov_data:
        return out
    for f, data in cov_data["files"].items():
        s = data.get("summary", {})
        out[_file_to_module(f)] = {
            "statements": s.get("num_statements", 0),
            "missing": s.get("missing_lines", 0),
            "percent": round(s.get("percent_covered", 0.0), 1),
        }
    return out


def cmd_diff(args: argparse.Namespace) -> int:
    """对比旧/新 coverage.json, 输出模块级百分点变化表。"""
    old_path = Path(args.old)
    new_path = Path(args.new)
    old = _read_coverage_json(old_path)
    new = _read_coverage_json(new_path)
    if not old or not new:
        print("❌ Need both --old and --new coverage JSON files")
        return 1

    old_t = _gather_module_table(old)
    new_t = _gather_module_table(new)

    print("═" * 70)
    print(f" Coverage Diff: {old_path.name} → {new_path.name}")
    print("═" * 70)
    print(f" {'module':<45} {'old%':>7}  {'new%':>7}  {'Δ':>7}")
    print("-" * 70)

    rows: list[tuple[str, float, float, float]] = []
    for mod in sorted(set(old_t) | set(new_t)):
        o = old_t.get(mod, {}).get("percent", 0.0)
        n = new_t.get(mod, {}).get("percent", 0.0)
        rows.append((mod, o, n, n - o))

    rows.sort(key=lambda r: r[3])
    for mod, o, n, d in rows:
        sign = "+" if d >= 0 else ""
        flag = " 🔻" if d < -1 else (" ⬆" if d > 1 else "")
        print(f" {mod:<45} {o:>6.1f}%  {n:>6.1f}%  {sign}{d:>5.1f}pp{flag}")

    overall_o = old.get("totals", {}).get("percent_covered", 0.0)
    overall_n = new.get("totals", {}).get("percent_covered", 0.0)
    print("-" * 70)
    print(f" {'TOTAL':<45} {overall_o:>6.1f}%  {overall_n:>6.1f}%  {overall_n - overall_o:>+5.1f}pp")
    return 0


def cmd_module(args: argparse.Namespace) -> int:
    """单模块覆盖率详情 (V2.21 P5-26 拆分: 抽 _print_module_summary + _print_missing_lines + _print_suggestion)."""
    cov_path = Path(args.coverage)
    module = args.module
    cov_data = _read_coverage_json(cov_path)
    if not cov_data:
        print(f"❌ Coverage file not found or invalid: {cov_path}")
        return 1

    target = module.replace(".", "/") + ".py"
    if target not in cov_data.get("files", {}):
        print(f"❌ Module {module} not in coverage data (looked for {target})")
        return 1

    file_data = cov_data["files"][target]
    pct, miss, stmts = _extract_module_summary(file_data)

    _print_module_summary(module, target, pct, miss, stmts)
    if miss > 0:
        _print_missing_lines(cov_data, target)
    _print_suggestion(module, target, pct)
    return 0


def _extract_module_summary(file_data: dict[str, Any]) -> tuple[float, int, int]:
    """提取模块 summary (pct, miss, stmts) 三元组 (模块级 helper).

    Args:
        file_data: coverage files[target] 数据

    Returns:
        (percent_covered, missing_lines, num_statements) 三元组
    """
    s = file_data.get("summary", {})
    return (
        s.get("percent_covered", 0.0),
        s.get("missing_lines", 0),
        s.get("num_statements", 0),
    )


def _print_module_summary(module: str, target: str, pct: float, miss: int, stmts: int) -> None:
    """打印模块 summary 表头 (模块级 helper).

    Args:
        module: 模块名 (dotted)
        target: 相对路径
        pct: 覆盖率
        miss: missing lines
        stmts: 总语句数
    """
    print("═" * 60)
    print(f" Module: {module}  →  {target}")
    print("═" * 60)
    print(f" Statements : {stmts}")
    print(f" Missing    : {miss}")
    print(f" Coverage   : {pct:.1f}%")


def _print_missing_lines(cov_data: dict[str, Any], target: str) -> None:
    """打印 missing lines 样本 (模块级 helper).

    Args:
        cov_data: 完整 coverage 数据
        target: 目标文件相对路径
    """
    for f, d in cov_data.get("files", {}).items():
        if f != target:
            continue
        ml = d.get("missing_lines", [])
        if ml:
            print(f"\n Missing lines (sample 30): {ml[:30]}{'...' if len(ml) > 30 else ''}")
        break


def _print_suggestion(module: str, target: str, pct: float) -> None:
    """打印补测试建议 (模块级 helper).

    Args:
        module: 模块名
        target: 相对路径
        pct: 覆盖率
    """
    py_file = Path(get_project_root()) / target
    if py_file.exists() and pct < 90.0:
        print(f"\n 💡 Suggestion: {module} < 90%. Add targeted tests in tests/test_{py_file.stem}_full.py")


def cmd_gate(args: argparse.Namespace) -> int:
    """模块级门禁: 与基线对比, 跌幅超阈值则失败。"""
    cov_path = Path(args.coverage)
    baseline_path = Path(args.baseline)
    threshold = float(args.threshold)

    cov_data = _read_coverage_json(cov_path)
    baseline = _read_coverage_json(baseline_path)
    if not cov_data or not baseline:
        print("❌ Need both --coverage and --baseline JSON files")
        return 1

    cur = _gather_module_table(cov_data)
    base = _gather_module_table(baseline)
    failed: list[tuple[str, float, float]] = []

    for mod, b_data in base.items():
        c_data = cur.get(mod, {})
        b = b_data.get("percent", 0.0)
        c = c_data.get("percent", 0.0)
        if b - c > threshold:
            failed.append((mod, b, c))

    if not failed:
        print(f"✅ Coverage gate passed (threshold: -{threshold}pp)")
        return 0

    print(f"❌ Coverage gate failed (threshold: -{threshold}pp):")
    for mod, b, c in sorted(failed, key=lambda r: r[1] - r[2], reverse=True):
        print(f"  {mod:<45} baseline={b:.1f}%  current={c:.1f}%  Δ={b - c:+.1f}pp")
    return 1


def cmd_snapshot(args: argparse.Namespace) -> int:
    """从 .coverage 数据生成基线 JSON(便于后续 diff/gate)。"""
    cov_file = Path(args.coverage)
    out_file = Path(args.output)
    if not cov_file.exists():
        print(f"❌ Coverage file not found: {cov_file}")
        return 1
    # 触发 coverage 转换
    subprocess.run(
        [sys.executable, "-m", "coverage", "json", "-o", str(out_file), "--include=tools/scripts/*"],
        check=False,
        cwd=str(get_project_root()),
    )
    if out_file.exists():
        print(f"✓ Baseline written to {out_file}")
        return 0
    print(f"❌ Failed to write {out_file}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="cov-tool", description="Coverage diff and per-module gate")
    sub = parser.add_subparsers(dest="command", required=True)

    p_diff = sub.add_parser("diff", help="Compare two coverage JSON files")
    p_diff.add_argument("--old", required=True, help="Older coverage.json")
    p_diff.add_argument("--new", required=True, help="Newer coverage.json")
    p_diff.set_defaults(func=cmd_diff)

    p_mod = sub.add_parser("module", help="Show per-module coverage detail")
    p_mod.add_argument("--coverage", required=True, help="Path to coverage.json")
    p_mod.add_argument("--module", required=True, help="Dotted module name (e.g. tools.scripts.foo)")
    p_mod.set_defaults(func=cmd_module)

    p_gate = sub.add_parser("gate", help="Module-level coverage gate vs baseline")
    p_gate.add_argument("--coverage", required=True, help="Path to current coverage.json")
    p_gate.add_argument("--baseline", required=True, help="Path to baseline coverage.json")
    p_gate.add_argument("--threshold", default="2.0", help="Max allowed drop in percentage points")
    p_gate.set_defaults(func=cmd_gate)

    p_snap = sub.add_parser("snapshot", help="Generate baseline coverage.json from .coverage")
    p_snap.add_argument("--coverage", default=".coverage", help="Source .coverage file")
    p_snap.add_argument("--output", default=".jcode/cov-baseline.json", help="Output baseline JSON")
    p_snap.set_defaults(func=cmd_snapshot)

    args = parser.parse_args()
    return cast(int, args.func(args))


if __name__ == "__main__":
    sys.exit(main())
