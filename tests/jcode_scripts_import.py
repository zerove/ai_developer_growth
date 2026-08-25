"""加载 .jcode/scripts/ 下带连字符文件名的脚本模块（非包路径，需 importlib）。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".jcode" / "scripts"


def load_context_sync_module():
    """动态加载 .jcode/scripts/context-sync.py（含同级 _common 依赖）。"""
    target = _SCRIPTS_DIR / "context-sync.py"
    # 脚本内部用 `from _common import ...` 同级导入, 需保证目录在 sys.path
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("jcode_context_sync", target)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
