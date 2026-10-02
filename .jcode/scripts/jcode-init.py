#!/usr/bin/env python3
"""
JCode 项目初始化命令
用法:
    jcode init                    # 交互式生成配置
    jcode init --lang python      # 预设语言生成
    jcode init --template web     # 预设模板生成
    jcode init --output .jcode/project.yaml  # 指定输出路径
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

# 预设语言模板
LANGUAGE_TEMPLATES: dict[str, Any] = {
    "python": {
        "primary": "python",
        "version": ">=3.11",
        "runtime": "cpython",
        "paths": {
            "src": "src",
            "tests": "tests",
            "docs": "docs",
            "config": "config",
            "scripts": "scripts",
        },
        "tools": {
            "format": {"command": "ruff", "args": ["format"], "check_args": ["format", "--check"]},
            "lint": {"command": "ruff", "args": ["check"], "fix_args": ["check", "--fix"]},
            "typecheck": {"command": "mypy", "args": ["--config-file", "pyproject.toml", "src"]},
            "test": {
                "command": "pytest",
                "args": ["-v", "--tb=short"],
                "coverage_args": ["--cov=src", "--cov-report=term-missing", "--cov-report=xml"],
            },
            "security": {"command": "bandit", "args": ["-r", "src", "-f", "json", "-o", "bandit-report.json"]},
            "deps": {"command": "pip-audit", "args": ["--desc"]},
            "docs": {"command": "sphinx-build", "args": ["-b", "html", "docs", "docs/_build"]},
        },
        "thresholds": {
            "coverage": {"overall": 60, "per_file": 50},
            "complexity": {"cyclomatic": 10, "cognitive": 15},
            "naming": {"style": "snake_case"},
        },
    },
    "typescript": {
        "primary": "typescript",
        "version": ">=5.0",
        "runtime": "node",
        "paths": {
            "src": "src",
            "tests": "tests",
            "docs": "docs",
            "config": "config",
        },
        "tools": {
            "format": {"command": "prettier", "args": ["--write"], "check_args": ["--check"]},
            "lint": {"command": "eslint", "args": ["."], "fix_args": [".", "--fix"]},
            "typecheck": {"command": "tsc", "args": ["--noEmit"]},
            "test": {"command": "vitest", "args": ["run"], "coverage_args": ["run", "--coverage"]},
            "security": {"command": "npm", "args": ["audit", "--json"]},
            "deps": {"command": "npm", "args": ["outdated", "--json"]},
            "docs": {"command": "typedoc", "args": ["--out", "docs/api", "src"]},
        },
        "thresholds": {
            "coverage": {"overall": 70, "per_file": 60},
            "complexity": {"cyclomatic": 10},
            "naming": {"style": "camelCase"},
        },
    },
    "rust": {
        "primary": "rust",
        "version": ">=1.70",
        "runtime": "rustc",
        "paths": {
            "src": "src",
            "tests": "tests",
            "docs": "docs",
            "examples": "examples",
            "benches": "benches",
        },
        "tools": {
            "format": {"command": "rustfmt", "args": [], "check_args": ["--check"]},
            "lint": {"command": "cargo", "args": ["clippy", "--all-targets", "--all-features", "--", "-D", "warnings"]},
            "typecheck": {"command": "cargo", "args": ["check", "--all-targets"]},
            "test": {"command": "cargo", "args": ["test", "--all-targets"], "coverage_args": ["llvm-cov", "--html"]},
            "security": {"command": "cargo", "args": ["audit"]},
            "deps": {"command": "cargo", "args": ["outdated"]},
            "docs": {"command": "cargo", "args": ["doc", "--no-deps", "--document-private-items"]},
        },
        "thresholds": {
            "coverage": {"overall": 70},
            "complexity": {"cyclomatic": 15},
            "naming": {"style": "snake_case"},
        },
    },
    "go": {
        "primary": "go",
        "version": ">=1.21",
        "runtime": "go",
        "paths": {
            "src": ".",
            "tests": ".",
            "docs": "docs",
            "cmd": "cmd",
            "internal": "internal",
            "pkg": "pkg",
        },
        "tools": {
            "format": {"command": "gofmt", "args": ["-w", "."], "check_args": ["-l", "."]},
            "lint": {"command": "golangci-lint", "args": ["run"], "fix_args": ["run", "--fix"]},
            "typecheck": {"command": "go", "args": ["vet", "./..."]},
            "test": {
                "command": "go",
                "args": ["test", "-v", "./..."],
                "coverage_args": ["test", "-coverprofile=coverage.out", "./..."],
            },
            "security": {"command": "gosec", "args": ["./..."]},
            "deps": {"command": "go", "args": ["list", "-m", "-u", "all"]},
            "docs": {"command": "go", "args": ["doc", "./..."]},
        },
        "thresholds": {
            "coverage": {"overall": 70},
            "complexity": {"cyclomatic": 10},
            "naming": {"style": "camelCase"},
        },
    },
    "java": {
        "primary": "java",
        "version": ">=17",
        "runtime": "jvm",
        "paths": {
            "src": "src/main",
            "tests": "src/test",
            "docs": "docs",
        },
        "tools": {
            "format": {"command": "google-java-format", "args": ["--replace"]},
            "lint": {"command": "spotbugs", "args": ["-textui"]},
            "typecheck": {"command": "javac", "args": ["-Xlint:all"]},
            "test": {"command": "mvn", "args": ["test"], "coverage_args": ["test", "jacoco:report"]},
            "security": {"command": "mvn", "args": ["org.owasp:dependency-check-maven:check"]},
            "deps": {"command": "mvn", "args": ["versions:display-dependency-updates"]},
            "docs": {"command": "mvn", "args": ["javadoc:javadoc"]},
        },
        "thresholds": {
            "coverage": {"overall": 70},
            "complexity": {"cyclomatic": 10},
            "naming": {"style": "camelCase"},
        },
    },
}
# 预设项目模板
PROJECT_TEMPLATES: dict[str, Any] = {
    "web": {
        "description": "Web 应用项目 (前端 + 后端)",
        "languages": ["typescript", "python"],
        "primary": "typescript",
        "secondary": ["python"],
    },
    "api": {
        "description": "REST/gRPC API 服务",
        "languages": ["go", "python"],
        "primary": "go",
        "secondary": ["python"],
    },
    "cli": {
        "description": "命令行工具",
        "languages": ["rust", "go", "python"],
        "primary": "rust",
        "secondary": ["go", "python"],
    },
    "library": {
        "description": "库/包开发",
        "languages": ["python", "typescript", "rust"],
        "primary": "python",
        "secondary": ["typescript", "rust"],
    },
    "data": {
        "description": "数据科学/ML 项目",
        "languages": ["python", "sql", "r"],
        "primary": "python",
        "secondary": ["sql", "r"],
    },
    "fullstack": {
        "description": "全栈应用",
        "languages": ["typescript", "python", "rust"],
        "primary": "typescript",
        "secondary": ["python", "rust"],
    },
}


def generate_config(args: argparse.Namespace) -> str:
    """生成配置文件内容"""
    # 基础配置
    config: dict[str, Any] = {
        "project": {
            "name": args.name or "my-project",
            "description": args.description or "",
            "version": args.version or "0.1.0",
            "repository": args.repository or "",
            "license": args.license or "MIT",
        },
        "language": {
            "primary": "",
            "secondary": [],
            "version": "",
            "runtime": "",
        },
        "paths": {},
        "tools": {},
        "thresholds": {},
        "hooks": {
            "on_commit": [],
            "on_pr": [],
            "on_merge": [],
            "scheduled": [],
        },
        "agents": {
            "enabled": [],
            "custom": [],
            "collaboration": {
                "max_parallel": 4,
                "timeout": 300,
                "retry": 2,
            },
        },
        "ci": {
            "provider": "github",
            "env": ["PYTHONPATH=src"],
            "cache": ["~/.cache/pip", "~/.cache/ruff", "~/.cache/mypy"],
            "matrix": {
                "python": ["3.11", "3.12", "3.13"],
                "os": ["ubuntu-latest", "macos-latest", "windows-latest"],
            },
            "deploy": {
                "enabled": False,
                "environments": ["staging", "production"],
                "approval_required": True,
            },
        },
        "notifications": {
            "channels": [],
            "templates": {
                "build_failed": "🔴 构建失败: {{project}} #{{build_number}} - {{commit_message}}",
                "deploy_success": "🟢 部署成功: {{project}} v{{version}} -> {{environment}}",
            },
        },
        "extensions": {
            "rule_packs": [],
            "skills": [],
            "plugins": [],
        },
        "_metadata": {
            "jcode_version": "1.0.0",
            "config_version": 1.0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "schema_url": "https://jcode.dev/schema/project.json",
        },
    }
    # 语言配置
    lang_cfg = cast(dict[str, object], config["language"])
    if args.template and args.template in PROJECT_TEMPLATES:
        template = PROJECT_TEMPLATES[args.template]
        primary_lang = template["primary"]
        lang_cfg["primary"] = primary_lang
        lang_cfg["secondary"] = template.get("secondary", [])
    elif args.lang:
        primary_lang = args.lang
        lang_cfg["primary"] = primary_lang
        lang_cfg["secondary"] = args.secondary or []
    else:
        primary_lang = "python"
        lang_cfg["primary"] = primary_lang
        lang_cfg["secondary"] = []
    # 获取语言模板
    lang_template = cast(dict[str, object], LANGUAGE_TEMPLATES.get(primary_lang, LANGUAGE_TEMPLATES["python"]))
    # 语言版本
    lang_cfg["version"] = args.lang_version or lang_template["version"]
    lang_cfg["runtime"] = lang_template["runtime"]
    # 路径
    paths = cast(dict[str, object], lang_template.get("paths", {}))
    config["paths"] = paths
    if args.src:
        config["paths"]["src"] = args.src
    if args.tests:
        config["paths"]["tests"] = args.tests
    if args.docs:
        config["paths"]["docs"] = args.docs
    # 工具链
    tools = cast(dict[str, dict[str, object]], lang_template.get("tools", {}))
    for tool_name, tool_config in tools.items():
        config["tools"][tool_name] = tool_config
    # 阈值
    thresholds = cast(dict[str, dict[str, object]], lang_template.get("thresholds", {}))
    for threshold_name, threshold_config in thresholds.items():
        config["thresholds"][threshold_name] = threshold_config
    # 转换为 YAML
    return dict_to_yaml(config)


# YAML 标量起始处的指示符字符不会被当成文本：">" 折叠块、"*" 锚点、"&" 别名、
# "!" 标签、"%" 指令、"@"/"`" 保留、"{}"/"[]" 流集合、"-"/"?" 序列与显式键。
# 早前只对含 ":" / "${" / "#" 的值加引号，导致 version: >=3.11 解析即 ScannerError。
_PLAIN_SAFE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-/ ]*$")
_YAML_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "y", "n", "~"}


def _needs_quoting(value: str) -> bool:
    if value == "" or value != value.strip():
        return True
    if value.lower() in _YAML_RESERVED:
        return True
    if ": " in value or value.endswith(":") or " #" in value:
        return True
    return _PLAIN_SAFE.match(value) is None


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        if _needs_quoting(value):
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return value
    return str(value)


def dict_to_yaml(data: dict[str, Any], indent: int = 0) -> str:
    """将字典转换为 YAML 字符串（手写发射器，标量一律经 _scalar 转义）"""
    lines: list[str] = []
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(dict_to_yaml(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    lines.append(dict_to_yaml(item, indent + 2))
                else:
                    lines.append(f"{prefix}  - {_scalar(item)}")
        else:
            lines.append(f"{prefix}{key}: {_scalar(value)}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        description="JCode 项目初始化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
预设语言: {", ".join(LANGUAGE_TEMPLATES.keys())}
预设模板: {", ".join(PROJECT_TEMPLATES.keys())}
示例:
  jcode init                          # 交互式
  jcode init --lang python            # Python 项目
  jcode init --lang typescript        # TypeScript 项目
  jcode init --template api           # API 服务模板
  jcode init --template web           # Web 应用模板
  jcode init --output .jcode/project.yaml  # 指定输出
        """,
    )
    parser.add_argument("--lang", choices=list(LANGUAGE_TEMPLATES.keys()), help="主语言")
    parser.add_argument("--secondary", nargs="+", help="次要语言列表")
    parser.add_argument("--lang-version", help="语言版本要求")
    parser.add_argument("--template", choices=list(PROJECT_TEMPLATES.keys()), help="项目模板")
    parser.add_argument("--name", help="项目名称")
    parser.add_argument("--description", help="项目描述")
    parser.add_argument("--version", help="版本号")
    parser.add_argument("--repository", help="Git 仓库 URL")
    parser.add_argument("--license", help="许可证")
    parser.add_argument("--src", help="源代码目录")
    parser.add_argument("--tests", help="测试目录")
    parser.add_argument("--docs", help="文档目录")
    parser.add_argument(
        "--ci",
        choices=[
            "github",
            "gitlab",
            "bitbucket",
            "azure",
            "jenkins",
            "circleci",
            "travis",
            "drone",
            "woodpecker",
            "gitea",
            "forgejo",
        ],
        help="CI 提供商",
    )
    parser.add_argument("--output", "-o", type=Path, default=Path(".jcode/project.yaml"), help="输出路径")
    parser.add_argument("--force", "-f", action="store_true", help="覆盖已存在的文件")
    return parser


def _write_config(output_path: Path, content: str, args: argparse.Namespace) -> int:
    """写入生成的配置到目标路径。返回 0 成功 / 1 失败。"""
    if output_path.exists() and not args.force:
        print(f"❌ 文件已存在: {output_path}")
        print("使用 --force 覆盖，或指定其他 --output 路径")
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"✅ 配置已生成: {output_path}")
    print(f"   项目: {args.name or 'my-project'}")
    print(f"   主语言: {args.lang or args.template or 'python'}")
    print(f"   模板: {args.template or '无'}")
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    yaml_content = generate_config(args)
    return _write_config(args.output, yaml_content, args)


if __name__ == "__main__":
    sys.exit(main())
