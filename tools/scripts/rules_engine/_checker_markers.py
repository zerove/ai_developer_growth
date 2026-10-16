"""Framework / language marker detection helpers for the rules engine."""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine.logger import logger


def _config_excluded_dirs() -> set[str]:
    """从 [tool.adg].exclude 合并额外的排除目录。"""
    overrides: set[str] = {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".cache",
        "build",
        "dist",
        ".opencode",
        ".tox",
        "htmlcov",
        ".coverage",
        "site-packages",
        "MagicMock",
    }
    try:
        from tools.scripts.app_config import get_setting

        extra = get_setting("exclude", [])
        if isinstance(extra, list):
            overrides.update(str(item) for item in extra)
    except Exception:
        import logging

        logging.getLogger(__name__).warning("Failed to load exclude config", exc_info=True)
    return overrides


# 目录遍历时排除的路径段（避免误扫构建产物、依赖、缓存）
DEFAULT_EXCLUDED_DIRS: set[str] = _config_excluded_dirs()

FRAMEWORK_DETECTORS: dict[str, dict[str, list[str]]] = {
    "react": {"files": ["package.json"], "packages": ["react", "react-dom"]},
    "vue": {"files": ["package.json"], "packages": ["vue"]},
    "express": {"files": ["package.json"], "packages": ["express"]},
    "nextjs": {"files": ["package.json", "next.config.js"], "packages": ["next"]},
    "django": {"files": ["manage.py", "requirements.txt"], "packages": ["django"]},
    "fastapi": {
        "files": ["requirements.txt", "pyproject.toml"],
        "packages": ["fastapi"],
    },
    "actix": {"files": ["Cargo.toml"], "packages": ["actix-web"]},
    "spring": {"files": ["pom.xml", "build.gradle"], "packages": ["spring-context"]},
    "spring-boot": {
        "files": ["pom.xml", "build.gradle"],
        "packages": ["spring-boot-starter"],
    },
}


def _detect_framework(dirpath: Path) -> str | None:
    """Detect project framework from project files (V2.21 P5-37 拆分: 抽 _check_marker)."""
    for fw_name, hints in FRAMEWORK_DETECTORS.items():
        for filename in hints["files"]:
            marker = dirpath / filename
            if marker.exists() and _check_marker(marker, hints["packages"]):
                return fw_name
    return None


def _check_marker(marker: Path, packages: list[str]) -> bool:
    """检查 marker 文件是否匹配 framework (按文件名分派, 模块级 helper).

    Args:
        marker: marker 文件路径
        packages: 框架依赖包列表

    Returns:
        是否匹配
    """
    if marker.name == "package.json":
        return _check_package_json(marker, packages)
    if marker.name == "Cargo.toml":
        return _check_text_contains(marker, packages)
    if marker.name in ("requirements.txt", "pyproject.toml"):
        return _check_text_contains(marker, packages, lower=True)
    if marker.name == "manage.py":
        return True
    if marker.name in ("pom.xml", "build.gradle"):
        return True  # best effort
    return False


def _check_package_json(marker: Path, packages: list[str]) -> bool:
    """检查 package.json 依赖 (模块级 helper).

    Args:
        marker: package.json 路径
        packages: 框架包列表

    Returns:
        是否任一包在 dependencies/devDependencies 中
    """
    import json

    try:
        data = json.loads(marker.read_text())
    except Exception:
        return True  # best effort
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    return any(pkg in deps for pkg in packages)


def _check_text_contains(marker: Path, packages: list[str], lower: bool = False) -> bool:
    """检查 marker 文件内容是否含任一 package (模块级 helper).

    Args:
        marker: 文件路径
        packages: 包列表
        lower: 是否 lowercase (requirements.txt/pyproject.toml)

    Returns:
        是否含任一包
    """
    content = marker.read_text()
    if lower:
        content = content.lower()
    return any(pkg in content for pkg in packages)


def _load_context_markers(dirpath: Path) -> dict[str, str]:
    """Load user-defined context markers from .adg/config.yml."""
    for search_dir in [
        dirpath,
        dirpath.parent,
        dirpath.parents[2] if len(dirpath.parents) > 2 else None,
    ]:
        if search_dir is None:
            continue
        config_path = search_dir / ".adg" / "config.yml"
        if config_path.exists():
            try:
                from .context import load_role_config

                return load_role_config(config_path)
            except Exception as exc:
                logger.debug(f"角色配置加载失败: {exc}")
    return {}


def _detect_language(filepath: Path) -> str:
    """Detect language from file extension."""
    ext = filepath.suffix.lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
    }
    return mapping.get(ext, "unknown")
