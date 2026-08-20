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

from tools.scripts._common import EXTENSION_MAP

# Framework detection patterns
FRAMEWORK_PATTERNS: dict[str, list[str]] = {
    "django": ["manage.py", "settings.py", "wsgi.py", "urls.py"],
    "fastapi": ["main.py", "fastapi", "uvicorn"],
    "flask": ["app.py", "flask"],
    "express": ["package.json", "express", "server.js"],
    "nextjs": ["next.config.js", "next.config.ts", "pages/", "app/"],
    "react": ["package.json", "react", "jsx", "tsx"],
    "vue": ["package.json", "vue", "vue.config.js"],
    "spring-boot": ["pom.xml", "build.gradle", "SpringApplication", "@SpringBootApplication"],
    "rails": ["Gemfile", "rails", "config/application.rb"],
    "laravel": ["composer.json", "laravel", "artisan"],
    "dotnet": ["*.csproj", "*.sln", "Program.cs", "Startup.cs"],
    "go": ["go.mod", "go.sum", "main.go"],
    "rust": ["Cargo.toml", "Cargo.lock", "src/main.rs"],
}

# Config file to language/framework mapping
CONFIG_MARKERS: dict[str, str | list[str]] = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": ["java", "maven"],
    "build.gradle": ["java", "gradle"],
    "package.json": ["javascript", "typescript"],
    "tsconfig.json": "typescript",
    "composer.json": "php",
    "Gemfile": "ruby",
    "CMakeLists.txt": "cpp",
    "Makefile": ["c", "cpp"],
    "docker-compose.yml": "docker",
    "Dockerfile": "docker",
}


def detect_project_language(project_dir: Path) -> dict[str, Any]:
    """Detect primary language and frameworks in a project directory."""
    if not project_dir.exists() or not project_dir.is_dir():
        return {"error": "Invalid directory"}

    # Count files by extension
    ext_counter: Counter[str] = Counter()

    for filepath in project_dir.rglob("*"):
        if filepath.is_file() and not any(part.startswith(".") for part in filepath.parts):
            suffix = filepath.suffix.lower()
            if suffix in EXTENSION_MAP:
                ext_counter[EXTENSION_MAP[suffix]] += 1

    if not ext_counter:
        return {"language": "unknown", "frameworks": [], "file_count": 0}

    primary_language = ext_counter.most_common(1)[0][0]

    # Detect frameworks
    frameworks = []
    for fw, patterns in FRAMEWORK_PATTERNS.items():
        for pattern in patterns:
            if any(project_dir.rglob(pattern)) or (project_dir / pattern).exists():
                frameworks.append(fw)
                break

    # Check config markers
    for config_file, langs in CONFIG_MARKERS.items():
        if (project_dir / config_file).exists():
            if isinstance(langs, list):
                frameworks.extend(langs)
            else:
                frameworks.append(langs)

    frameworks = list(set(frameworks))

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
