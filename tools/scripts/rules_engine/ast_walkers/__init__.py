"""AST Walkers 模块化包。

从原 _ast_walkers.py 拆分的按语言分组的私有方法，
以 mixin 类形式提供，支持 Python/JS/TS/Rust/Go 及通用 fallback。

导出:
- _ImportWalkers: import/globals/error 提取与通用工具
- _FunctionWalkers: 函数提取 (Python/JS/TS/Rust/Go/通用)
- _ClassWalkers: 类提取 (Python/JS/TS/Rust/Go)
"""

from .base import _ImportWalkers
from .generic import _GenericClassWalkers, _GenericFunctionWalkers
from .go import _GoClassWalkers, _GoFunctionWalkers
from .javascript import _JavaScriptClassWalkers, _JavaScriptFunctionWalkers
from .python import _PythonClassWalkers, _PythonFunctionWalkers
from .rust import _RustClassWalkers, _RustFunctionWalkers

# 兼容旧接口：组合 mixin 类（避免 MRO 冲突，仅单继承 _ImportWalkers）
# 这些导入用于构建类层级，虽未直接导出但为类继承所需
# ruff: noqa: F401


# 兼容旧接口：组合 mixin 类（避免 MRO 冲突，仅单继承 _ImportWalkers）
class _FunctionWalkers(_PythonFunctionWalkers):
    """函数提取相关私有方法（Python/JS/TS/Rust/Go/通用 fallback）。"""

    pass


class _ClassWalkers(_FunctionWalkers):
    """类提取相关私有方法。"""

    pass


__all__ = [
    "_ImportWalkers",
    "_FunctionWalkers",
    "_ClassWalkers",
]
