"""核心检查逻辑模块。

提供核心检查入口：
- check_file: 单文件检查
- check_directory: 目录检查（串行/并行）
"""

from __future__ import annotations

# 重新导出公共 API
from tools.scripts.rules_engine.checker import (
    _apply_context_role,
    _check_file_skip_conditions,
    _check_files_parallel,
    _check_files_serial,
    _check_with_cache,
    _discover_target_files,
    _file_not_found_result,
    _init_cache_store,
    _load_directory_rules,
    _prepare_file_check,
    _run_all_checkers,
    _run_architecture_analysis,
    _run_semantic_checks,
    check_directory,
    check_file,
)

# 导入各子模块的功能
from .cache import check_with_cache, init_cache_store
from .linters import run_bandit, run_eslint, run_external_linters, run_ruff
from .markers import (
    check_marker,
    check_package_json,
    check_text_contains,
    config_excluded_dirs,
    detect_framework,
    detect_language,
    load_context_markers,
    load_ignored_rules,
    load_ignored_rules_from_config,
    parse_noqa_lines,
)
from .noqa import filter_suppressed_issues

# 重新导出缓存相关
# 重新导出报告生成
from .reporter import (
    generate_json_report,
    generate_junit_report,
    generate_sarif_report,
    generate_text_report,
)
from .workers import worker_check, worker_init

# 重新导出 linters

# 重新导出 markers

# 重新导出 noqa

# 重新导出 workers

__all__ = [
    # 核心入口
    "check_file",
    "check_directory",
    # 内部函数
    "_check_file_skip_conditions",
    "_prepare_file_check",
    "_apply_context_role",
    "_file_not_found_result",
    "_run_all_checkers",
    "_load_directory_rules",
    "_discover_target_files",
    "_init_cache_store",
    "_run_architecture_analysis",
    "_check_with_cache",
    "_check_files_serial",
    "_check_files_parallel",
    "check_directory",
    "_run_semantic_checks",
    # 缓存
    "init_cache_store",
    "check_with_cache",
    # 报告
    "generate_sarif_report",
    "generate_junit_report",
    "generate_text_report",
    "generate_json_report",
    # Linters
    "run_external_linters",
    "run_ruff",
    "run_eslint",
    "run_bandit",
    # 标记/检测
    "detect_language",
    "detect_framework",
    "load_context_markers",
    "check_marker",
    "check_package_json",
    "check_text_contains",
    "config_excluded_dirs",
    "load_ignored_rules",
    "parse_noqa_lines",
    "load_ignored_rules_from_config",
    # NOQA
    "filter_suppressed_issues",
    # Workers
    "worker_init",
    "worker_check",
]
