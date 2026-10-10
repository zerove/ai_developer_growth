"""ADR-079 守卫: 可直接执行的脚本必须能以脚本路径启动。

## 为什么需要这个守卫

ADR-079 修好了 `hooks_runner.py` 的自举, 但 16 个测试仍然红。追下去发现
**根因和 ADR-079 记述的不一样**, 且是两个独立原因:

1. **脚本侧**: `validate_language_rules.py` 等脚本以脚本路径执行时
   `sys.path[0]` 是 `tools/scripts/`, 仓库根不在其中, 包绝对导入全崩。
2. **测试注入侧**: 两个测试文件用 `sitecustomize.py` 注入缺陷实现, 而
   `sitecustomize` 在 **Python 启动阶段**执行, 早于任何用户模块导入 ——
   此时 `sys.path` 里还没有仓库根, 注入里的 `from tools.scripts...`
   会失败。该文件里明明有 `[sitecustomize] 注入失败` 的告警, 但失败被
   `try/except` 吞掉后**测试照常继续**, 于是"缺陷没装上 → 走正常路径 →
   断言不成立", 表现成与产品缺陷无法区分的红。

两者都属"静默失效"类: 没有报错, 只有行为对不上。

## 为什么是这个形式

判据取**可执行的验收路径**而非源码检查: 真的起一个子进程, 以脚本路径
跑 `--help`, 要求退出码为 0。只 grep 源码里的 `sys.path` 会出现两类假象 ——
- 已自举的脚本 (如 `hooks_runner.py`) 源码里有引导但探测方法写错会误报 OK;
- `ai_context_manager.py` 先崩在缺 `openai` 依赖上, `grep 'tools'` 抓不到。

实测踩过这两个坑, 故本守卫只认退出码与 stderr。

## 变异验证

回退任一脚本的引导 → 本守卫立即变红;
把 `sitecustomize` 注入改为不引导 → 对应 9 个测试变红。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tools" / "scripts"

# 必须能以脚本路径直接执行的脚本。逐个加进来时, 理由写在注释里 ——
# 新增条目不得是"顺手一起改", 必须有调用方证据(门禁配置/测试/文档)。
BOOTSTRAP_REQUIRED = [
    # .pre-commit-config.yaml 的 quality-gate / governance-audit 入口
    "hooks_runner.py",
    # tests/test_write_path_fallback_contracts.py 多处以脚本路径调用
    "validate_language_rules.py",
    # tests/test_detect_language.py 等以脚本路径调用
    "detect_language.py",
    # tests/test_generate_fixes.py 以脚本路径调用
    "generate_fixes.py",
]

# 刻意**不**列入清单的脚本（守卫用 `--help` 判定, 以下两类无法用该判据）:
# - perf_benchmark.py：无 argparse, `--help` 会直接跑完整基准(实测 >100s 超时)。
#   它确实需要自举, 但应由兜底测试 test_every_pkg_importing_script_bootstraps
#   以"退出码 + stderr"覆盖, 而不是塞进这份依赖 `--help` 的清单。
# - jcode_ai_native_workflow.py：同样无 `--help`, 同理由兜底测试覆盖。


def _run_as_script(name: str) -> subprocess.CompletedProcess[str]:
    """以脚本路径执行 `--help` —— 判据是能启动, 不是 help 文本内容。

    刻意不传 PYTHONPATH: 子进程环境必须与 pre-commit / CI 一致, 那里
    仓库根来自 cwd 而非 PYTHONPATH, 多给会让守卫在门禁之外才变红。
    """
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPTS_DIR / name), "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize("script", BOOTSTRAP_REQUIRED)
def test_script_runs_by_path(script: str) -> None:
    """以脚本路径执行不得因包导入崩溃。"""
    proc = _run_as_script(script)

    module_error = "No module named" in proc.stderr
    assert not module_error, (
        f"{script} 以脚本路径执行时导入失败:\n{proc.stderr}\n"
        f"sys.path[0] 是脚本所在目录, 仓库根不在其中 —— 需在包绝对导入前引导。"
    )
    assert proc.returncode == 0, f"{script} --help 退出 {proc.returncode}:\n{proc.stderr}"


def test_every_pkg_importing_script_bootstraps() -> None:
    """兜底: 凡含 `tools.*` 包绝对导入的脚本, 必须能以脚本路径启动。

    **为何不用"所有能跑通的脚本都要登记"那种宽判据**: 实测会命中 60 多个
    自包含脚本(add_navigation.py / validate_case_study.py 等), 它们本就没有
    包导入, 不需要自举, 全登记只会制造噪音并让守卫失去信号。

    精确判据是"含包绝对导入" —— 这正是缺陷的必要条件。以启动是否成功来
    判定而非源码匹配, 因为源码匹配看不出引导是否真的在正确位置生效。

    跳过无 argparse 的脚本: 判据靠 `--help` 快速退出, 而 perf_benchmark.py
    这类脚本收到 `--help` 会直接跑完整基准(实测 >100s 超时), 会把守卫拖死。
    **这是一处已知覆盖缺口**: 这类脚本的自举目前无自动化守卫, 靠人工维护。
    要补齐需另写"按 import 成功判定"的守卫, 但那会与本文件重复。
    """
    unbootstrapped = []

    for candidate in sorted(SCRIPTS_DIR.glob("*.py")):
        name = candidate.name
        if name.startswith("_") or name in set(BOOTSTRAP_REQUIRED):
            continue
        try:
            src = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not _has_pkg_import(src):
            continue
        if "argparse" not in src:
            continue
        proc = _run_as_script(name)
        if proc.returncode != 0 or "No module named" in proc.stderr:
            detail = proc.stderr.strip().splitlines()[-1:]
            unbootstrapped.append(f"{name}: {detail}")

    assert not unbootstrapped, "以下脚本含 tools.* 包绝对导入却无法以脚本路径启动(ADR-079 要求自举):\n" + "\n".join(
        unbootstrapped
    )


def _has_pkg_import(src: str) -> bool:
    """是否含顶层 `tools.*` 包绝对导入。

    刻意只看行首 —— 缩进的 import 位于函数/条件块内, 不参与启动期解析。
    """
    return any(line.startswith(("from tools.", "from tools ", "import tools.")) for line in src.splitlines())
