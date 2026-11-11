"""Hooks runner: 底层工具执行域（P2-1 第四刀）。

超时/并发/目录排除/语言检测/工具命令构建与执行。
由 hooks_runner.py import 转发，测试 patch 路径不受影响。
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from tools.scripts.language_registry import (
    EXTENSION_MAP,
    Language,
    ToolCategory,
    ToolConfig,
    detect_language,
    get_tool,
)

logger = logging.getLogger(__name__)


def _get_jobs_setting() -> int:
    """获取 jobs 配置（从 [tool.adg].jobs 或默认值 4）。"""
    try:
        from tools.scripts.app_config import get_setting

        return int(str(get_setting("jobs", 4)))
    except Exception:
        return 4


def _timeout_for_category(category: object) -> int:
    """按工具类别获取超时秒数，支持 [tool.adg].timeouts 配置覆盖。

    默认: 测试套件 900s（全量运行且与其他阶段并行时耗时显著变长），其余 300s。
    配置格式: [tool.adg.timeouts] test = 1200, lint = 180 ...
    """
    default = 900 if getattr(category, "name", "") == "TEST" else 300
    key = getattr(category, "name", "").lower()
    try:
        from tools.scripts.app_config import get_setting

        timeouts = get_setting("timeouts", None)
        if isinstance(timeouts, dict) and key in timeouts:
            return int(str(timeouts[key]))
    except Exception as e:  # noqa: BLE001 - 配置缺失时使用默认超时
        logger.debug(f"读取超时配置失败，使用默认 {default}s: {e}")
    return default


def _excluded_scan_dirs() -> set[str]:
    """扫描时排除的目录: 虚拟环境、依赖与构建产物。"""
    return {
        ".venv",
        "venv",
        "node_modules",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "site-packages",
        "dist",
        "build",
        "target",
        "site",
    }


def _count_language_files(project_root: Path) -> dict[Language, int]:
    """扫描所有扩展名, 统计各语言文件数 (排除第三方/构建目录)。"""
    _node_ecosystem_languages = {Language.TYPESCRIPT, Language.JAVASCRIPT}
    has_package_json = (project_root / "package.json").exists()
    excluded = _excluded_scan_dirs()

    ext_counts: dict[Language, int] = {}
    for ext, lang in EXTENSION_MAP.items():
        if lang in _node_ecosystem_languages and not has_package_json:
            continue
        count = sum(1 for p in project_root.rglob(f"*{ext}") if not (set(p.parts) & excluded))
        if count > 0:
            ext_counts[lang] = ext_counts.get(lang, 0) + count
    return ext_counts


def _detect_project_languages(project_root: Path) -> list[Language]:
    """检测项目中使用的所有语言"""
    languages: list[Language] = []

    # Node 生态语言需要 package.json 作为工程化标志；
    # 否则散落的 .ts/.js（如编辑器扩展、构建产物）会因缺少
    # eslint/prettier/tsc 工具链而误报失败
    _node_ecosystem_languages = {Language.TYPESCRIPT, Language.JAVASCRIPT}
    has_package_json = (project_root / "package.json").exists()

    # 1. 通过配置文件检测主要语言
    main_lang = detect_language(project_root)
    if main_lang and not (main_lang in _node_ecosystem_languages and not has_package_json):
        languages.append(main_lang)

    # 2. 扫描扩展名统计语言分布, 按文件数排序后仅纳入占比显著的语言：
    # 示例脚本、编辑器扩展等附带文件不应触发全量工具链门禁
    ext_counts = _count_language_files(project_root)
    total = sum(ext_counts.values())
    for lang, count in sorted(ext_counts.items(), key=lambda kv: kv[1], reverse=True):
        if lang in languages:
            continue
        if count >= 50 or (total > 0 and count / total >= 0.2):
            languages.append(lang)

    return languages


def _run_simple(
    func_or_result: Callable[[], tuple[bool, str]] | tuple[bool, str],
) -> int:
    """Run a simple check function and print output."""
    if callable(func_or_result):
        passed, output = func_or_result()
    else:
        passed, output = func_or_result
    print(output)
    return 0 if passed else 1


def _tool_available(language: Language, tool: ToolConfig) -> str | None:
    """检查工具是否可用, 返回错误消息或 None。"""
    try:
        version_result: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-m", "ruff", "--version"]
            if tool.command == "ruff"
            else [tool.command, tool.version_flag],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if version_result.returncode != 0:
            return f"  ❌ {language.value}: {tool.command} 不可用 ({tool.install_hint})"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return f"  ❌ {language.value}: {tool.command} 未安装 ({tool.install_hint})"
    return None


def _build_tool_command(tool: ToolConfig, fix: bool, check_only: bool) -> list[str]:
    """按 fix/check_only 模式构建工具命令行。"""
    # ruff 统一走 `python -m ruff`（项目 venv 解释器），避免 PATH 解析到 mise 的 0.16
    cmd: list[str] = [sys.executable, "-m", "ruff"] if tool.command == "ruff" else [tool.command]
    if fix and tool.fix_args:
        cmd.extend(tool.fix_args)
    elif check_only and tool.check_args:
        cmd.extend(tool.check_args)
    else:
        cmd.extend(tool.args)
    return cmd


def _execute_tool(cmd: list[str], language: Language, category: ToolCategory, project_root: Path) -> tuple[bool, str]:
    """执行工具命令并格式化输出。"""
    timeout_seconds = _timeout_for_category(category)
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return False, f"  ❌ {language.value}: {category.value} 超时 ({timeout_seconds}s)"
    except Exception as e:
        return False, f"  ❌ {language.value}: {category.value} 错误 - {e}"

    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr

    passed = result.returncode == 0
    status = "✅" if passed else "❌"
    suffix = "通过" if passed else "失败"
    return passed, f"  {status} {language.value}: {category.value} {suffix}\n{output}"


def _run_tool_for_language(
    language: Language,
    category: ToolCategory,
    project_root: Path,
    fix: bool = False,
    check_only: bool = False,
) -> tuple[bool, str]:
    """使用语言工具链运行特定类别工具"""
    tool = get_tool(language, category)
    if tool is None:
        return False, f"  ⚠️  {language.value}: {category.value} 工具未配置"

    unavailable = _tool_available(language, tool)
    if unavailable:
        return False, unavailable

    cmd = _build_tool_command(tool, fix, check_only)
    print(f"  🔧 {language.value}: 运行 {category.value} ({' '.join(cmd)})")
    return _execute_tool(cmd, language, category, project_root)


def _run_basic_check_for_languages(
    languages: list[Language],
    category: ToolCategory,
    project_root: Path,
    fix: bool = False,
    check_only: bool = False,
) -> tuple[bool, str]:
    """为多个语言运行基础检查"""
    all_passed = True
    outputs = []

    for lang in languages:
        passed, output = _run_tool_for_language(lang, category, project_root, fix, check_only)
        all_passed = all_passed and passed
        outputs.append(output)

    return all_passed, "\n".join(outputs)


def _run_lint_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言 lint 检查 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.LINT, args.path, fix=args.fix)


def _run_format_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言格式检查 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.FORMAT, args.path, fix=args.fix)


def _run_typecheck_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言类型检查 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.TYPECHECK, args.path)


def _run_test_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言测试 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.TEST, args.path)


def _run_security_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言安全扫描 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.SECURITY, args.path)


def _parse_languages(lang_str: str) -> list[Language]:
    """解析逗号分隔的语言字符串"""
    languages = []
    for part in lang_str.split(","):
        part = part.strip()
        if part:
            try:
                languages.append(Language(part.lower()))
            except ValueError:
                # 尝试别名
                from tools.scripts.language_registry import LANGUAGE_ALIASES

                if part.lower() in LANGUAGE_ALIASES:
                    languages.append(LANGUAGE_ALIASES[part.lower()])
                else:
                    print(f"  ⚠️  未知语言: {part}，跳过")
    return languages
