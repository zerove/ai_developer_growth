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

# 动态导入 tools/scripts/_common.py，避免循环导入
_tools_common_path = Path(__file__).parent.parent.parent / "tools" / "scripts" / "_common.py"
spec = importlib.util.spec_from_file_location("_common_tools", _tools_common_path)
_common_tools = importlib.util.module_from_spec(spec)
sys.modules["_common_tools"] = _common_tools
spec.loader.exec_module(_common_tools)

# 导出所有公共 API
get_project_root = _common_tools.get_project_root
run_command = _common_tools.run_command
print_check = _common_tools.print_check
print_section = _common_tools.print_section
rules_dir = _common_tools.rules_dir
framework_dir = _common_tools.framework_dir
EXTENSION_MAP = _common_tools.EXTENSION_MAP
detect_language = _common_tools.detect_language
file_hash = _common_tools.file_hash
handle_error = _common_tools.handle_error
safe_import = _common_tools.safe_import
load_yaml = _common_tools.load_yaml
save_yaml = _common_tools.save_yaml
filter_supported_files = _common_tools.filter_supported_files
SUPPORTED_EXTENSIONS = _common_tools.SUPPORTED_EXTENSIONS

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
