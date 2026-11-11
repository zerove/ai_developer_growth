"""扫描路径相关的共享常量与判定（跳过目录、文件数上限）。

## 为什么单独成模块

`detect.py` 需要 `MAX_FILES` / `is_skipped_dir`, 而 `core.py` 需要
`detect._load_yaml`。两者都留在原处就成环:

    core.py → detect.py → core.py

把路径相关的常量与判定下沉到本模块后, 依赖方向单一:

    core.py  → _paths.py
    detect.py → _paths.py
    core.py  → detect.py   (仅 YAML 解析, 单向)

`core.py` 保留同名重导出, 公开 API 不变。
"""

from __future__ import annotations

SKIP_DIRS = {
    ".git",
    ".svn",
    "node_modules",
    "target",
    "vendor",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".opencode",
    "coverage",
    ".next",
    ".nuxt",
    # Generated documentation / build output
    "book",
    "site",
    "_build",
    "out",
    "public",
    "static",
    # IDE / editor
    ".idea",
    ".vscode",
    ".vs",
    "*.swp",
    # Cache directories
    ".cache",
    "tmp",
    ".tmp",
}


def _config_excluded_dirs() -> set[str]:
    """合并 [tool.adg].exclude 配置到跳过集合（与 rules_engine 同源）。"""
    try:
        from tools.scripts.app_config import get_setting

        extra = get_setting("exclude", [])
        if isinstance(extra, list):
            return {str(item) for item in extra}
    except Exception:  # noqa: BLE001 - 配置读取失败时回退静态集合
        pass
    return set()


# 含用户配置的完整排除集：段匹配用（模块加载时冻结一次）
SKIP_DIRS_ALL = SKIP_DIRS | _config_excluded_dirs()

# 目录名前缀模式：.venv-adg / venv-test 等变体也视为虚拟环境
_DIR_PREFIX_PATTERNS = (".venv", "venv")


def is_skipped_dir(name: str) -> bool:
    """目录名是否应跳过：精确集合命中，或虚拟环境类前缀模式命中。"""
    if name in SKIP_DIRS_ALL:
        return True
    return name.startswith(_DIR_PREFIX_PATTERNS)


MAX_FILES = 5000
