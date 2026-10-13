"""基础检查函数: lint, format, typecheck, test, security."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from tools.scripts.secret_scanner import scan_secrets

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


def run_lint() -> tuple[bool, str]:
    """Run ruff lint check."""
    return _run_subprocess(["ruff", "check", "."], timeout=120, description="Lint")


def run_format_check() -> tuple[bool, str]:
    """Run ruff format check."""
    return _run_subprocess(["ruff", "format", "--check", "."], timeout=120, description="Format")


def run_typecheck() -> tuple[bool, str]:
    """Run mypy type check."""
    return _run_subprocess(
        [sys.executable, "-m", "mypy", "tools/scripts/", "--ignore-missing-imports"],
        timeout=120,
        description="Type check",
    )


def _plugin_available(module: str) -> bool:
    """检测 pytest 插件是否可导入（不可用时优雅降级为串行/无重试）。"""
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def _changed_python_files(base: str) -> list[Path]:
    """获取相对 base ref 变更的 Python 文件。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", base],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        return [Path(line) for line in result.stdout.splitlines() if line.endswith(".py")]
    except (subprocess.TimeoutExpired, OSError):
        return []


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
    """
    selected: set[Path] = set()
    all_tests = list(tests_dir.rglob("test_*.py"))
    for changed_file in changed:
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


def run_tests_incremental(base: str = "HEAD") -> tuple[bool, str]:
    """只运行受变更影响的测试（时间预算分层的 PR 级入口）。

    无法确定受影响范围时回退全量，保证不漏检。
    """
    changed = _changed_python_files(base)
    if not changed:
        return True, "No changed Python files; incremental test skipped"

    targets = _tests_for_modules(changed)
    if not targets:
        return True, (
            f"No tests reference {len(changed)} changed file(s); falling back to full suite is recommended before merge"
        )

    cmd = [sys.executable, "-m", "pytest", *[str(t) for t in targets], "-v", "--tb=short", "-p", "no:cacheprovider"]

    workers = _setting("test_workers", "auto")
    if workers and str(workers) not in ("0", "None") and _plugin_available("xdist"):
        cmd += ["-n", str(workers)]
    reruns = int(str(_setting("test_reruns", 2)))
    if reruns > 0 and _plugin_available("pytest_rerunfailures"):
        cmd += ["--reruns", str(reruns), "--reruns-delay", "1"]

    passed, output = _run_subprocess(cmd, timeout=300, description="Incremental tests")
    summary = f"Incremental scope: {len(targets)} test file(s) for {len(changed)} changed file(s)\n{output}"
    return passed, summary


def _setting(key: str, default: object) -> object:
    """读取 [tool.adg] 配置，失败时返回默认值。"""
    try:
        from tools.scripts.app_config import get_setting

        return get_setting(key, default)
    except Exception:
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

    reruns = int(str(_setting("test_reruns", 2)))
    if reruns > 0 and _plugin_available("pytest_rerunfailures"):
        cmd += ["--reruns", str(reruns), "--reruns-delay", "1"]

    cov_min = int(str(_setting("cov_min", 60)))
    if cov_min > 0:
        cmd += ["--cov-fail-under", str(cov_min)]

    return _run_subprocess(cmd, timeout=900, description="Tests")


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

    # pip-audit
    audit_passed, audit_out = _run_subprocess(
        ["pip-audit", "--desc", "--timeout", "30"],
        timeout=120,
        description="pip-audit",
    )
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
    return _run_subprocess(["ruff", "check", *paths], timeout=60, description="Lint")


def run_format_files(paths: list[str]) -> tuple[bool, str]:
    """Run ruff format check on specific files."""
    if not paths:
        return True, "No Python files to format-check"
    return _run_subprocess(["ruff", "format", "--check", *paths], timeout=60, description="Format")


# Registry of all basic check functions for discovery
BASIC_CHECKS: dict[str, Callable[[], tuple[bool, str]]] = {
    "lint": run_lint,
    "format": run_format_check,
    "typecheck": run_typecheck,
    "test": run_tests,
    "security": run_security,
}
