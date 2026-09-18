"""标记/检测/语言识别模块。

提供：
- 语言检测
- 框架检测
- 上下文标记加载
- 标记检查
- package.json 检查
- 文本内容检查
- 排除目录配置
- 忽略规则加载
- noqa 行解析
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def detect_language(filepath: Path) -> str:
    """Detect language from file extension."""
    ext_map = {
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
        ".hpp": "cpp",
        ".hh": "cpp",
        ".hxx": "cpp",
        ".c": "cpp",
        ".h": "cpp",
    }
    return ext_map.get(filepath.suffix.lower(), "unknown")


def detect_framework(dirpath: Path) -> str | None:
    """检测项目框架。"""
    # 简单启发式：检查关键文件
    if (dirpath / "package.json").exists():
        try:
            import json

            pkg = json.loads((dirpath / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "fastapi" in deps:
                return "fastapi"
            if "django" in deps:
                return "django"
            if "flask" in deps:
                return "flask"
            if "react" in deps:
                return "react"
            if "vue" in deps:
                return "vue"
            if "next" in deps:
                return "nextjs"
            return "node"
        except Exception:
            return "node"
    if (dirpath / "Cargo.toml").exists():
        return "rust"
    if (dirpath / "go.mod").exists():
        return "go"
    if (dirpath / "pom.xml").exists() or (dirpath / "build.gradle").exists():
        return "java"
    if (dirpath / "composer.json").exists():
        return "php"
    if (dirpath / "requirements.txt").exists() or (dirpath / "pyproject.toml").exists():
        try:
            import tomllib

            pyproject = tomllib.loads((dirpath / "pyproject.toml").read_bytes())
            deps = pyproject.get("project", {}).get("dependencies", [])
            if any("fastapi" in d for d in deps):
                return "fastapi"
            if any("django" in d for d in deps):
                return "django"
            if any("flask" in d for d in deps):
                return "flask"
        except Exception:
            pass
        return "python"
    return None


def load_context_markers(dirpath: Path) -> dict[str, Any]:
    """加载上下文标记文件。"""
    markers: dict[str, Any] = {}
    marker_file = dirpath / ".adg" / "context_markers.yml"
    if marker_file.exists():
        try:
            import yaml

            markers = yaml.safe_load(marker_file.read_text()) or {}
        except Exception:
            pass
    return markers


def check_marker(filepath: Path, marker_name: str) -> bool:
    """检查文件是否包含特定标记。"""
    try:
        content = filepath.read_text(encoding="utf-8")
        return marker_name in content
    except Exception:
        return False


def check_package_json(dirpath: Path, key: str) -> Any:
    """检查 package.json 中的键值。"""
    pkg_file = Path(dirpath) / "package.json"
    if not pkg_file.exists():
        return None
    try:
        import json

        keys = key.split(".")
        val = json.loads(pkg_file.read_text())
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return None
        return val
    except Exception:
        return None


def check_text_contains(filepath: Path, pattern: str) -> bool:
    """检查文件内容是否包含模式。"""
    try:
        content = filepath.read_text(encoding="utf-8")
        return pattern in content
    except Exception:
        return False


def config_excluded_dirs() -> set[str]:
    """获取默认排除目录配置。"""
    return {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".git",
        "dist",
        "build",
        "target",
        ".venv",
        "venv",
        "env",
        ".env",
        ".tox",
        ".coverage",
        "htmlcov",
        ".mypy_cache",
        ".ruff_cache",
    }


def load_ignored_rules(filepath: Path) -> set[str]:
    """加载忽略规则配置。"""
    ignored = set()
    try:
        content = filepath.read_text(encoding="utf-8")
        import re

        # 查找 # noqa: RULE1,RULE2 模式
        for match in re.finditer(r"#\s*noqa\s*:\s*([^\n]+)", content):
            rules_str = match.group(1).strip()
            for rule in rules_str.split(","):
                ignored.add(rule.strip())
    except Exception:
        pass
    return ignored


def parse_noqa_lines(content: str) -> dict[int, set[str]]:
    """解析 noqa 行，返回 行号 -> 忽略规则集合。"""
    import re

    result: dict[int, set[str]] = {}
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        match = re.search(r"#\s*noqa\s*:\s*([^\n]+)", line)
        if match:
            rules_str = match.group(1).strip()
            rules = {r.strip() for r in rules_str.split(",") if r.strip()}
            if rules:
                result[i] = rules
    return result


def load_ignored_rules_from_config(dirpath: Path) -> set[str]:
    """从配置文件加载忽略规则。"""
    ignored = set()
    config_file = Path(dirpath) / ".adg" / "ignored_rules.yml"
    if config_file.exists():
        try:
            import yaml

            data = yaml.safe_load(config_file.read_text()) or {}
            ignored.update(data.get("rules", []))
        except Exception:
            pass
    return ignored
