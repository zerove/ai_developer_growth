"""基础检查函数: lint, format, typecheck, test, security."""

from __future__ import annotations

import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.scripts._common import ruff_command
from tools.scripts.secret_scanner import scan_secrets

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    CheckResult = tuple[bool, str]

# Supported code file extensions for file-based checks
CODE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".cs",
        ".php",
        ".rb",
        ".cpp",
        ".swift",
        ".scala",
        ".ex",
        ".exs",
        ".lua",
        ".zig",
        ".r",
        ".R",
        ".clj",
        ".hs",
        ".dart",
        ".ps1",
    }
)

# Subset used for incremental/diff checks (languages with active rule support)
INCREMENTAL_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".cs",
        ".php",
        ".rb",
        ".cpp",
        ".swift",
        ".scala",
        ".dart",
    }
)


def _run_subprocess(
    cmd: list[str],
    *,
    timeout: int = 120,
    description: str = "",
) -> tuple[bool, str]:
    """Run a subprocess command and return (passed, output).

    Args:
        cmd: Command and arguments to execute.
        timeout: Timeout in seconds.
        description: Human-readable name for error messages.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except FileNotFoundError:
        return False, f"{description}: command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, f"{description}: timed out after {timeout}s"


def run_lint(fix: bool = False) -> tuple[bool, str]:
    """Run ruff lint check;fix=True 时原地改写。"""
    cmd = ruff_command("check", "--fix", ".") if fix else ruff_command("check", ".")
    return _run_subprocess(cmd, timeout=120, description="Lint")


def run_format_check(fix: bool = False) -> tuple[bool, str]:
    """Run ruff format check;fix=True 时原地改写 (不是校验, 是应用)。"""
    cmd = ruff_command("format", "." if fix else "--check", ".")
    return _run_subprocess(cmd, timeout=120, description="Format")


def run_typecheck() -> tuple[bool, str]:
    """Run mypy type check（与 CI/pyproject 口径对齐）。"""
    return _run_subprocess(
        [sys.executable, "-m", "mypy", "tools", ".jcode", "ai-dev-framework/src"],
        timeout=180,
        description="Type check",
    )


def _plugin_available(module: str) -> bool:
    """检测 pytest 插件是否可导入（不可用时优雅降级为串行/无重试）。"""
    try:
        # find_spec 只查存在性, 不执行模块顶层代码 (也不触发 sec-001 规则)。
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _changed_files(base: str) -> tuple[list[Path], bool]:
    """获取相对 base ref 变更的所有文件。

    Returns:
        (文件列表, 是否成功获取)。成功时 ok=True（空列表表示无变更）；失败时 ok=False。
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", base],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return [], False
        return [Path(line) for line in result.stdout.splitlines() if line], True
    except (subprocess.TimeoutExpired, OSError):
        return [], False


def _changed_python_files(base: str) -> tuple[list[Path], bool]:
    """获取相对 base ref 变更的 Python 文件。

    Returns:
        (Python 文件列表, 是否成功获取)
    """
    files, ok = _changed_files(base)
    if not ok:
        return [], False
    return [p for p in files if p.suffix == ".py"], True


def _matches_module(test_file: Path, stem: str, module_path: str) -> bool:
    """测试文件是否覆盖某模块 (同名约定或 import 反查, Phase 36c cc 拆分).

    Returns:
        True 表示该测试文件与变更模块相关
    """
    if test_file.name in (f"test_{stem}.py", f"test_{stem}_checks.py"):
        return True
    try:
        head = test_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return module_path in head or f"from {module_path}" in head or f"import {stem}" in head


def _tests_for_modules(changed: list[Path], tests_dir: Path = Path("tests")) -> list[Path]:
    """启发式映射: 变更模块 → 可能覆盖它的测试文件。

    规则:
    1. 变更文件本身在 tests/ 下 → 直接收入
    2. 同名约定: tools/scripts/foo.py → tests/test_foo.py / tests/foo/test_*.py
    3. import 反查: 测试文件文本中出现该模块路径或模块名

    仅处理主仓库 tests/ 子树内的变更；`examples/` 下属于独立示例项目，
    其测试由对应示例的 CI（jobs-example-tests）自行执行，本仓库增量门禁不
    做范围映射（含其 tests/ 夹名，避免误把示例测试打进根 venv）。
    """
    selected: set[Path] = set()
    all_tests = list(tests_dir.rglob("test_*.py"))
    for changed_file in changed:
        if "examples" in changed_file.parts:
            continue
        parts = changed_file.parts
        if "tests" in parts:
            selected.add(changed_file)
            continue
        stem = changed_file.stem
        module_path = str(changed_file.with_suffix("")).replace("/", ".").lstrip("./")
        for test_file in all_tests:
            if _matches_module(test_file, stem, module_path):
                selected.add(test_file)
    return sorted(selected)


def _uncovered_changed_modules(changed: list[Path], targets: list[Path]) -> bool:
    """变更模块在增量范围内找不到匹配测试时回退全量 —— 不漏检。

    启发式映射（`_tests_for_modules`）靠"同名约定/import 反查"枚举测试；
    行为测试（只经 `docs/`、功能门禁等触碰、不 import 模块）会被漏掉 ——
    比如 `link_auditor.py` 的 `docs/archive/README.md` 孤儿判定测试
    `test_doc_index_reachability` 此前被本地增量放行、远端 CI 才抓到。
    """
    for changed_file in changed:
        if "examples" in changed_file.parts or "tests" in changed_file.parts:
            continue
        stem = changed_file.stem
        module_path = str(changed_file.with_suffix("")).replace("/", ".").lstrip("./")
        if not any(_matches_module(t, stem, module_path) for t in targets):
            return True
    return False


# ── 行为测试注册表 ──────────────────────────────────────────────
# 跨文件行为测试: 改动模块 X 后除启发式枚举外也跑这些测试。
# 历史上远端 CI full-suite 才抓到的漏洞均在此登记:
#   - link_auditor.py 改 archive 层跳过时, test_doc_index_reachability
#     （MOC 孤儿判定）被本地增量放行, 远端 CI 才抓到 —— 先前借同名约定
#     测试 test_link_auditor.py 覆盖, 但它不经 import 触及 MOC 逻辑。
BEHAVIOR_TESTS: dict[str, list[str]] = {
    "link_auditor": ["test_doc_index_reachability.py"],
}


def _add_behavior_tests(changed: list[Path], targets: list[Path]) -> list[Path]:
    """合并注册表中为变更模块声明的行为测试（按文件名匹配，不存在则忽略）。"""
    extra: set[Path] = set()
    for changed_file in changed:
        for name in BEHAVIOR_TESTS.get(changed_file.stem, []):
            candidate = Path("tests") / name
            if candidate.is_file():
                extra.add(candidate)
    return sorted(set(targets) | extra)


def run_tests_incremental(base: str = "HEAD") -> tuple[bool, str]:
    """只运行受变更影响的测试（时间预算分层的 PR 级入口）。

    无法确定受影响范围时回退全量，保证不漏检。
    """
    # 检查 base 是否可解析（fail-closed）
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", base],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except Exception:
        return run_tests()

    changed, ok = _changed_python_files(base)
    if not ok:
        return run_tests()
    if not changed:
        return True, "No changed Python files; incremental test skipped"

    targets = _tests_for_modules(changed)
    if not targets or _uncovered_changed_modules(changed, targets):
        # 无法确定受影响范围时回退全量 —— 保证不漏检
        return run_tests()
    targets = _add_behavior_tests(changed, targets)

    cmd = [sys.executable, "-m", "pytest", *[str(t) for t in targets], "-v", "--tb=short", "-p", "no:cacheprovider"]

    workers = _setting("test_workers", "auto")
    if workers and str(workers) not in ("0", "None") and _plugin_available("xdist"):
        cmd += ["-n", str(workers)]
    reruns = _get_test_reruns(2)
    if reruns > 0 and _plugin_available("pytest_rerunfailures"):
        cmd += ["--reruns", str(reruns), "--reruns-delay", "1"]

    timeout = _get_timeout("test_incremental", 300)
    passed, output = _run_subprocess(cmd, timeout=timeout, description="Incremental tests")
    summary = f"Incremental scope: {len(targets)} test file(s) for {len(changed)} changed file(s)\n{output}"
    return passed, summary


def _setting(key: str, default: object) -> object:
    """读取 [tool.adg] 配置，失败时返回默认值。"""
    try:
        from tools.scripts.app_config import get_setting

        return get_setting(key, default)
    except Exception:
        return default


def _get_test_reruns(default: int = 2) -> int:
    """获取测试重试次数：环境变量 ADG_TEST_RERUNS 优先于配置。"""
    env_val = os.environ.get("ADG_TEST_RERUNS")
    if env_val is not None:
        try:
            v = int(env_val.strip())
            if v >= 0:
                return v
        except ValueError:
            pass
    try:
        v = int(str(_setting("test_reruns", default)))
        return v if v >= 0 else default
    except Exception:
        return default


def _get_timeout(name: str, default: int) -> int:
    """从配置读取超时（[tool.adg] timeouts.{name}），失败时返回默认值。"""
    try:
        timeouts = _setting("timeouts", {})
        if isinstance(timeouts, dict) and name in timeouts:
            try:
                return int(timeouts[name])
            except (ValueError, TypeError):
                return default
    except Exception:
        logger.debug("读取超时配置 %s 失败", name, exc_info=True)
    return default


def run_tests() -> tuple[bool, str]:
    """Run pytest test suite with coverage gate, parallel workers and flaky retry.

    配置项（[tool.adg]）:
    - test_workers: xdist 并行数，"auto" 或整数；0/None 禁用
    - test_reruns: flaky 重试次数；0 禁用
    - cov_min: 覆盖率门禁百分比；0 禁用
    插件缺失时自动降级，不会导致门禁误报。
    """
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
        # 与 CI (jobs/tests.yml) 同一口径: --cov=tools。此前本地用
        # --cov=tools/scripts, 把 tools/ 下 9 个子包 (dashboard/report/
        # marketplace/cicd/fix_engine/multiproject/chat_integration/
        # ai_recommender/benchmarks, 约 2540 LOC) 排除在度量之外, 本地看到的
        # 覆盖率因此偏高。实测纳入后总覆盖率 87.15%, 仍高于 80% 门禁。
        "--cov=tools",
        "--cov=.jcode/scripts",
        "--cov-report=term-missing",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]

    workers = _setting("test_workers", "auto")
    if workers and str(workers) not in ("0", "None") and _plugin_available("xdist"):
        cmd += ["-n", str(workers)]

    reruns = _get_test_reruns(2)
    if reruns > 0 and _plugin_available("pytest_rerunfailures"):
        cmd += ["--reruns", str(reruns), "--reruns-delay", "1"]

    cov_min = int(str(_setting("cov_min", 60)))
    if cov_min > 0:
        cmd += ["--cov-fail-under", str(cov_min)]

    # 超时用于**兜住挂死**, 不是性能指标。此前固定 900s, 但健康状态下实测全量
    # 需要 902s(空闲) ~ 1277s(有负载), 于是该守卫会随机报失败 —— 一个在代码
    # 正常时误报的守卫比没有守卫更糟, 它会训练人用 --no-verify 绕过。
    # 取 1800s: 约为观测上限的 1.4 倍, 既留出余量又仍能兜住真正的挂死。
    timeout = _get_timeout("test", 1800)
    return _run_subprocess(cmd, timeout=timeout, description="Tests")


def _run_builtin_secret_scan() -> tuple[bool, str]:
    """运行内置 secret 扫描（工作区，不含 git 历史——历史扫描留给夜间任务）。"""
    try:
        secret_result = scan_secrets(Path("."), scan_workspace=True, scan_git_history=False)
    except Exception as e:  # noqa: BLE001 - 扫描器故障不应静默放行
        return False, f"secret scanner error: {e}"
    if secret_result.findings:
        lines = [f"❌ {len(secret_result.findings)} secret(s):"]
        for f in secret_result.findings[:20]:
            lines.append(f"  [{f.severity}] {f.rule_id} in {f.file}:{f.line}")
        return False, "\n".join(lines)
    tools = ", ".join(secret_result.tools_used) or "builtin-regex"
    return True, f"No secrets found (tools: {tools})"


def run_security() -> tuple[bool, str]:
    """Run security scan (bandit + pip-audit + builtin secret scan).

    secret 扫描复用 tools.scripts.secret_scanner 的多工具实现:
    gitleaks/trufflehog 不可用时自动回退到内置正则+熵检测。
    """
    results: list[tuple[str, bool, str]] = []

    # bandit
    bandit_passed, bandit_out = _run_subprocess(
        [
            "bandit",
            "-r",
            "tools/scripts/",
            "-f",
            "json",
            "-o",
            "bandit-report.json",
            "-ll",
        ],
        timeout=120,
        description="Bandit",
    )
    results.append(("bandit", bandit_passed, bandit_out))

    # pip-audit: `|| true` 可选降级（与 doctor 声明及 test_gate_hardening 约定一致；
    # 缺失时跳过而非失败。CI 安装 pip-audit，故不影响远端判别力。）
    audit_passed, audit_out = _run_subprocess(
        ["pip-audit", "--desc", "--timeout", "30"],
        timeout=120,
        description="pip-audit",
    )
    if not audit_passed and "command not found" in audit_out:
        audit_passed = True
        audit_out += "\n(pip-audit 未安装，按 || true 降级跳过)"
    results.append(("pip-audit", audit_passed, audit_out))

    # 内置 secret 扫描
    results.append(("secret-scan", *_run_builtin_secret_scan()))

    all_passed = all(r[1] for r in results)
    output = "\n".join(f"=== {r[0]} ===\n{r[2]}" for r in results)
    return all_passed, output


def run_lint_files(paths: list[str]) -> tuple[bool, str]:
    """Run ruff lint on specific files."""
    if not paths:
        return True, "No Python files to lint"
    return _run_subprocess(ruff_command("check", *paths), timeout=60, description="Lint")


def run_format_files(paths: list[str]) -> tuple[bool, str]:
    """Run ruff format check on specific files."""
    if not paths:
        return True, "No Python files to format-check"
    return _run_subprocess(ruff_command("format", "--check", *paths), timeout=60, description="Format")


# Registry of all basic check functions for discovery
BASIC_CHECKS: dict[str, Callable[[], tuple[bool, str]]] = {
    "lint": run_lint,
    "format": run_format_check,
    "typecheck": run_typecheck,
    "test": run_tests,
    "security": run_security,
}
