"""ADR-079 补齐守卫: 凡含 `tools.*` 包绝对导入的模块都必须可被导入。

## 为什么需要这个守卫

`test_script_bootstrap_contract.py` 用 `--help` 判定脚本能否以脚本路径
启动, 但它有**两处覆盖缺口**, 导致上一轮修完 36 个脚本后仍有盲区:

1. **只看顶层**: `SCRIPTS_DIR.glob("*.py")` 匹配不到 `rules_engine/`、
   `adg_cli/commands/cmd/`、`hooks/`、`config/` 下的嵌套模块。
2. **跳过无 argparse 的脚本**: `perf_benchmark.py` 收到 `--help` 会直接
   跑完整基准(实测 >100s 超时), 守卫只能 `continue`。上一轮统计这类
   模块有 86 个, 它们的自举无任何自动化守卫, 靠人工维护。

本守卫用 **import 成功** 作为判据, 覆盖上面两类缺口:
- 覆盖**递归**全部子目录, 不只顶层;
- 不需要 `--help`、不执行 `main()`, 所以对无 argparse 的脚本同样安全
  (`main()` 都由 `if __name__ == "__main__":` 保护, import 不触发副作用)。

## 为什么判据取"能导入"而非源码匹配

判据沿用 ADR-079 的教训 —— 源码里**有** `sys.path.insert` 不代表引导
真的生效(`jcode_ai_native_workflow.py` 曾把引导放在包导入**之后**, 用
grep 判定会误报 OK)。import 成功是真实验收路径。

## 为什么不逐个起子进程

109 个模块逐个 `python -c "import X"` 需 109 次解释器启动(约 60s+)。
本守卫在**单个**子进程里逐个 import 并记录失败项, 一次启动覆盖全部,
且能区分"导入失败"与"导入成功但无该模块"。

## 变异验证

把任一模块的包绝对导入改成不存在的模块名 → 本守卫立即变红;
删除某模块的仓库根引导并以脚本路径执行 → 对应的
`test_script_runs_by_path` 变红(两者判据互补, 不重复)。
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tools" / "scripts"


def _iter_pkg_importing_modules() -> list[str]:
    """递归找出含顶层 `tools.*` 包绝对导入的模块, 返回点分模块名。

    用 AST 而非逐行 grep: 缩进的 import 位于函数/条件块内, 不参与
    启动期解析, 行首匹配会误纳; AST 能同时正确处理别名与多行导入。
    """
    found: list[str] = []
    for path in sorted(SCRIPTS_DIR.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        if not _has_toplevel_pkg_import(tree):
            continue
        rel = path.relative_to(REPO_ROOT).with_suffix("")
        found.append(".".join(rel.parts))
    return found


def _has_toplevel_pkg_import(tree: ast.Module) -> bool:
    """模块顶层(非函数/条件块内)是否 import 了 `tools.*`。"""
    for node in tree.body:
        targets: list[str] = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets = [node.module]
        if any(t == "tools" or t.startswith("tools.") for t in targets):
            return True
    return False


_PROBE = """
import importlib, json, sys
sys.path.insert(0, sys.argv[1])
failed = {}
for mod in json.loads(sys.argv[2]):
    try:
        importlib.import_module(mod)
    except BaseException as exc:
        failed[mod] = f"{type(exc).__name__}: {exc}"
print("__RESULT__" + json.dumps(failed))
"""


def test_all_pkg_importing_modules_importable() -> None:
    """凡含 `tools.*` 包绝对导入的模块都必须能导入(ADR-079 自举契约)。

    覆盖 `test_script_bootstrap_contract.py` 的两处缺口: 递归子目录 +
    无 argparse 的模块。后者无法用 `--help` 判定, 但 import 判据通用。
    """
    modules = _iter_pkg_importing_modules()
    assert modules, "扫描未命中任何模块 —— 判据若失效本守卫会变成空跑"

    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            _PROBE,
            str(REPO_ROOT),
            json.dumps(modules),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, f"探测子进程异常退出:\n{proc.stderr}"

    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("__RESULT__")), None)
    assert line is not None, f"探测子进程未产出结果:\n{proc.stdout}\n{proc.stderr}"

    failed: dict[str, str] = json.loads(line.removeprefix("__RESULT__"))
    assert not failed, "以下模块含 tools.* 包绝对导入但导入失败(ADR-079 要求自举):\n" + "\n".join(
        f"  {m}: {err}" for m, err in sorted(failed.items())
    )
