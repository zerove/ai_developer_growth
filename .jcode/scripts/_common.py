"""jcode Skill Runner - 共享模块 (统一版本)

重定向到统一的 tools/scripts/_common.py，避免重复维护。

提供所有 skill 脚本共用的工具函数:
- run_command(): 执行外部命令并返回结果
- print_check(): 格式化输出检查结果
- get_project_root(): 获取项目根目录
- print_section(): 打印分隔线和标题
- 以及 tools/scripts/_common.py 中的所有功能
"""

import sys
from pathlib import Path

# 确保仓库根目录在 sys.path 上（脚本从 .jcode/scripts/ 直接运行时不在）
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.scripts._common import (  # noqa: E402
    EXTENSION_MAP,
    GOVERNANCE_DOCS,
    SUPPORTED_EXTENSIONS,
    detect_language,
    file_hash,
    filter_supported_files,
    framework_dir,
    get_project_root,
    handle_error,
    load_yaml,
    print_check,
    print_section,
    rules_dir,
    run_command,
    safe_import,
    save_yaml,
)

__all__ = [
    "get_project_root",
    "run_command",
    "print_check",
    "print_section",
    "rules_dir",
    "framework_dir",
    "EXTENSION_MAP",
    "detect_language",
    "file_hash",
    "handle_error",
    "safe_import",
    "load_yaml",
    "save_yaml",
    "filter_supported_files",
    "SUPPORTED_EXTENSIONS",
    "GOVERNANCE_DOCS",
]
