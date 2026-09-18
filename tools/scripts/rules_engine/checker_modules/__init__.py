"""Checker 核心模块化包。

将原 checker.py 拆分为职责单一的模块：
- cache.py: 缓存管理 (CheckStore, 缓存读写)
- reporter.py: 结果报告生成 (SARIF/JUnit/文本/JSON)
- core.py: 核心检查逻辑 (check_file, check_directory)
- linters.py: 外部 linter 集成 (ruff, eslint, bandit 等)
- markers.py: 标记/框架检测/语言检测
- noqa.py: noqa 抑制处理
- workers.py: 并行 worker 进程管理
"""

from .cache import (
    CheckStore,
    check_with_cache,
    init_cache_store,
)
from .core import (
    _check_files_parallel,
    _check_files_serial,
    check_directory,
    check_file,
)
from .linters import (
    run_bandit,
    run_eslint,
    run_external_linters,
    run_ruff,
)
from .markers import (
    check_marker,
    check_package_json,
    check_text_contains,
    config_excluded_dirs,
    detect_framework,
    detect_language,
    load_context_markers,
    load_ignored_rules,
    parse_noqa_lines,
)
from .noqa import (
    filter_suppressed_issues,
    is_issue_suppressed,
)
from .reporter import (
    generate_json_report,
    generate_junit_report,
    generate_sarif_report,
    generate_text_report,
)
from .workers import (
    worker_check,
    worker_init,
)

__all__ = [
    # 核心入口
    "check_file",
    "check_directory",
    "_check_files_serial",
    "_check_files_parallel",
    # 缓存
    "CheckStore",
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
    # NOQA
    "filter_suppressed_issues",
    "is_issue_suppressed",
    # Workers
    "worker_init",
    "worker_check",
]
