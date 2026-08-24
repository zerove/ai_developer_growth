"""jcode Skill Runner - 共享模块 (统一版本)

重定向到统一的 tools/scripts/_common.py，避免重复维护。

提供所有 skill 脚本共用的工具函数:
- run_command(): 执行外部命令并返回结果
- print_check(): 格式化输出检查结果
- get_project_root(): 获取项目根目录
- print_section(): 打印分隔线和标题
- 以及 tools/scripts/_common.py 中的所有功能
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any, cast

# 动态导入 tools/scripts/_common.py，避免循环导入
_tools_common_path = Path(__file__).parent.parent.parent / "tools" / "scripts" / "_common.py"
spec = importlib.util.spec_from_file_location("_common_tools", _tools_common_path)
_common_tools = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
sys.modules["_common_tools"] = _common_tools
spec.loader.exec_module(_common_tools)  # type: ignore[union-attr]

# 导出所有公共 API

get_project_root = cast(Any, _common_tools.get_project_root)
run_command = cast(Any, _common_tools.run_command)
print_check = cast(Any, _common_tools.print_check)
print_section = cast(Any, _common_tools.print_section)
rules_dir = cast(Any, _common_tools.rules_dir)
framework_dir = cast(Any, _common_tools.framework_dir)
EXTENSION_MAP = cast(Any, _common_tools.EXTENSION_MAP)
detect_language = cast(Any, _common_tools.detect_language)
file_hash = cast(Any, _common_tools.file_hash)
handle_error = cast(Any, _common_tools.handle_error)
safe_import = cast(Any, _common_tools.safe_import)
load_yaml = cast(Any, _common_tools.load_yaml)
save_yaml = cast(Any, _common_tools.save_yaml)
filter_supported_files = cast(Any, _common_tools.filter_supported_files)
SUPPORTED_EXTENSIONS = cast(Any, _common_tools.SUPPORTED_EXTENSIONS)

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
]
