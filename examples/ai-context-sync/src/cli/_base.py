"""CLI 共享基础设施（app 与错误处理装饰器）。

## 为什么要单独成模块

`cli/__init__.py` 需要导入各命令模块以注册命令, 而各命令模块又需要
`cli_error_handler`。若该装饰器定义在 `cli/__init__.py`, 就形成

    cli/__init__.py → cli/commands/*.py → cli/__init__.py

的**循环依赖** —— 架构检查 (`arch-cycle`) 会直接报错, 且包初始化顺序
变得脆弱（命令模块在 `__init__` 尚未执行完时被导入）。

把共享符号下沉到本模块后, 依赖方向变为

    cli/__init__.py → cli/_base.py
    cli/commands/*.py → cli/_base.py

不再有环。
"""

from __future__ import annotations

import functools
from typing import Any

import typer

from ..exceptions import AISyncError
from ..logger import logger


def cli_error_handler(func: Any) -> Any:
    """把领域异常与未预期异常统一转换为 typer.Exit。"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except typer.Exit:
            raise  # 合法重抛 typer.Exit（透传退出信号）
        except AISyncError as e:
            logger.error(f"❌ {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {e}")
            raise typer.Exit(code=1)

    return wrapper
