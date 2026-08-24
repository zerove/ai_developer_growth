#!/usr/bin/env python3
"""
Enhanced Language & Framework Detector

Detects the primary programming language and framework of a project directory
by analyzing file extensions, config files, and directory structure.

Usage:
    python detect_language.py <project_dir>
    python detect_language.py . --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from tools.scripts._common import EXCLUDE_DIRS, EXTENSION_MAP

# Framework detection patterns
FRAMEWORK_PATTERNS: dict[str, list[str]] = {
    "nextjs": ["next.config.js", "next.config.ts", "pages/", "app/"],
    "react": ["package.json", "react", "jsx", "tsx"],
    "vue": ["package.json", "vue", "vue.config.js"],
    "express": ["package.json", "express", "server.js"],
    "django": ["manage.py", "settings.py", "wsgi.py", "urls.py"],
    "fastapi": ["main.py", "fastapi", "uvicorn"],
    "flask": ["app.py", "flask"],
    "spring-boot": [
        "pom.xml",
        "build.gradle",
        "SpringApplication",
        "@SpringBootApplication",
    ],
    "rails": ["Gemfile", "rails", "config/application.rb"],
    "laravel": ["composer.json", "laravel", "artisan"],
    "dotnet": ["*.csproj", "*.sln", "Program.cs", "Startup.cs"],
    "go": ["go.mod", "go.sum", "main.go"],
    "rust": ["Cargo.toml", "Cargo.lock", "src/main.rs"],
}


def _check_requirements_for_framework(project_dir: Path) -> str | None:
    """Check requirements.txt for specific framework indicators."""
    req_file = project_dir / "requirements.txt"
    if not req_file.exists():
        return None
    try:
        content = req_file.read_text().lower()
        if "django" in content:
            return "django"
        if "fastapi" in content:
            return "fastapi"
        if "flask" in content:
            return "flask"
    except Exception:  # noqa: empty-except
        # 框架探测失败属正常降级, 静默回退到 None 由调用方兜底
        pass
    return None


def detect_framework_from_go_mod(project_dir: Path) -> str | None:
    """Detect Go framework from go.mod file."""
    go_mod = project_dir / "go.mod"
    if not go_mod.exists():
        return None
    try:
        content = go_mod.read_text()
        if "github.com/gin-gonic/gin" in content:
            return "gin"
        if "github.com/gofiber/fiber" in content:
            return "fiber"
        if "github.com/labstack/echo" in content:
            return "echo"
        if "github.com/gorilla/mux" in content:
            return "gorilla/mux"
    except Exception:  # noqa: empty-except
        # 框架探测失败属正常降级, 静默回退到 None 由调用方兜底
        pass
    return None


def detect_framework_from_requirements(project_dir: Path) -> str | None:
    """Detect Python framework from requirements.txt."""
    return _check_requirements_for_framework(project_dir)


def detect_framework(project_dir: Path, language: str) -> str | None:
    """Detect framework for a given language."""
    if language == "python":
        return detect_framework_from_requirements(project_dir)
    elif language == "go":
        return detect_framework_from_go_mod(project_dir)
    return None


# Config file to language/framework mapping
CONFIG_MARKERS: dict[str, str | list[str]] = {
    "tsconfig.json": "typescript",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": ["java", "maven"],
    "build.gradle": ["java", "gradle"],
    "package.json": ["javascript", "typescript"],
    "composer.json": "php",
    "Gemfile": "ruby",
    "CMakeLists.txt": "cpp",
    "Makefile": ["c", "cpp"],
    "docker-compose.yml": "docker",
    "Dockerfile": "docker",
}


# ----------------------------------------------------------
# Helper functions for test compatibility
# ----------------------------------------------------------


def count_extensions(project_dir: Path) -> dict[str, int]:
    """Count files by language extension in a project directory."""
    from collections import Counter

    ext_counter: Counter[str] = Counter()

    for filepath in project_dir.rglob("*"):
        if filepath.is_file():
            # Check if any part of the relative path is in EXCLUDE_DIRS or starts with .
            try:
                rel_parts = filepath.relative_to(project_dir).parts
            except ValueError:
                continue
            if any(part.startswith(".") for part in rel_parts):
                continue
            if any(part in EXCLUDE_DIRS for part in rel_parts):
                continue
            suffix = filepath.suffix.lower()
            if suffix in EXTENSION_MAP:
                ext_counter[EXTENSION_MAP[suffix]] += 1

    return dict(ext_counter)


def detect_language_from_file(filepath: Path) -> str | None:
    """Detect language from file extension."""
    return EXTENSION_MAP.get(filepath.suffix.lower())


def detect_language(project_dir: Path) -> dict[str, Any]:
    """Detect language with confidence score (test compatible wrapper)."""
    result = detect_project_language(project_dir)
    if "error" in result:
        return {"language": "unknown", "confidence": 0.0, "framework": None}

    # Get language and framework from result
    language = result.get("language", "unknown")
    frameworks = result.get("frameworks", [])
    framework = frameworks[0] if frameworks else None
    file_count = result.get("file_count", 0)

    # Handle empty directory
    if language == "unknown" and file_count == 0:
        return {"language": "unknown", "confidence": 0.0, "framework": None}

    # Confidence: higher with more files and config files
    if file_count > 0:
        confidence = min(1.0, file_count / 50.0)
    else:
        # For config-only detection (e.g., pyproject.toml only) - high confidence
        confidence = 0.9

    # Boost confidence if we have config markers
    if result.get("extension_breakdown"):
        confidence = max(confidence, 0.9)

    return {
        "language": language,
        "confidence": confidence,
        "framework": framework,
    }


def _count_language_files(project_dir: Path) -> Counter[str]:
    """按扩展名统计语言文件数 (跳过隐藏目录与排除目录)。"""
    ext_counter: Counter[str] = Counter()
    for filepath in project_dir.rglob("*"):
        if not filepath.is_file():
            continue
        try:
            rel_parts = filepath.relative_to(project_dir).parts
        except ValueError:
            continue
        if any(part.startswith(".") for part in rel_parts):
            continue
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        suffix = filepath.suffix.lower()
        if suffix in EXTENSION_MAP:
            ext_counter[EXTENSION_MAP[suffix]] += 1
    return ext_counter


def _detect_config_languages(project_dir: Path) -> list[str]:
    """根据配置文件标记文件 (如 go.mod/pyproject.toml) 推断语言。"""
    config_languages: list[str] = []
    for config_file, langs in CONFIG_MARKERS.items():
        if (project_dir / config_file).exists():
            if isinstance(langs, list):
                config_languages.extend(langs)
            else:
                config_languages.append(langs)
    return config_languages


def _detect_frameworks(project_dir: Path, primary_language: str, config_languages: list[str]) -> list[str]:
    """检测项目框架; 无实际框架时以配置语言兜底。"""
    frameworks = []
    for fw, patterns in FRAMEWORK_PATTERNS.items():
        for pattern in patterns:
            if any(project_dir.rglob(pattern)) or (project_dir / pattern).exists():
                frameworks.append(fw)
                break

    req_framework = _check_requirements_for_framework(project_dir)
    if req_framework:
        frameworks.insert(0, req_framework)  # Prioritize requirements.txt detection

    go_framework = detect_framework_from_go_mod(project_dir)
    if go_framework:
        frameworks.insert(0, go_framework)

    if not frameworks:
        frameworks.extend(config_languages)

    return list(dict.fromkeys(frameworks))  # preserve order while deduping


def detect_project_language(project_dir: Path) -> dict[str, Any]:
    """Detect primary language and frameworks in a project directory."""
    if not project_dir.exists() or not project_dir.is_dir():
        return {"error": "Invalid directory"}

    # Count files by extension
    ext_counter = _count_language_files(project_dir)
    config_languages = _detect_config_languages(project_dir)

    # Determine primary language
    if ext_counter:
        primary_language = ext_counter.most_common(1)[0][0]
    elif config_languages:
        primary_language = config_languages[0]
    else:
        return {"language": "unknown", "frameworks": [], "file_count": 0}

    frameworks = _detect_frameworks(project_dir, primary_language, config_languages)

    return {
        "language": primary_language,
        "frameworks": frameworks,
        "file_count": sum(ext_counter.values()),
        "extension_breakdown": dict(ext_counter),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Enhanced Language & Framework Detector")
    parser.add_argument("project_dir", nargs="?", default=".", help="Project directory to analyze")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    result = detect_project_language(project_dir)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if "error" in result:
            print(f"错误: {result['error']}", file=sys.stderr)
            return 1
        print(f"项目目录: {project_dir}")
        print(f"主要语言: {result['language']}")
        print(f"检测框架: {', '.join(result['frameworks']) if result['frameworks'] else '无'}")
        print(f"文件总数: {result['file_count']}")
        if result.get("extension_breakdown"):
            print("扩展名分布:")
            for ext, count in sorted(result["extension_breakdown"].items(), key=lambda x: -x[1]):
                print(f"  {ext}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
