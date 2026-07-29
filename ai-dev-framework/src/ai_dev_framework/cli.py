#!/usr/bin/env python3
"""
adg — AI Developer Governance CLI

统一命令行入口，管理项目治理配置。
"""

import argparse
import sys
from pathlib import Path

from ai_dev_framework import __version__
from ai_dev_framework.jcode_init import init_jcode
from ai_dev_framework.scan import scan_files, print_results


def main() -> None:
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        prog="adg",
        description="AI Developer Governance — 项目治理工具",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"adg {__version__}",
    )

    sub = parser.add_subparsers(dest="command", help="可用命令")

    # adg init
    init_parser = sub.add_parser("init", help="初始化项目治理配置")
    init_parser.add_argument("name", help="项目名称")
    init_parser.add_argument("--type", default="generic", help="项目类型")
    init_parser.add_argument("--language", default="python", help="编程语言")
    init_parser.add_argument("--framework", default=None, help="框架名称")
    init_parser.add_argument("--output", default=".", help="输出目录")
    init_parser.add_argument("--force", action="store_true", help="强制覆盖已有配置")

    # adg check
    check_parser = sub.add_parser("check", help="检查项目治理状态")
    check_parser.add_argument("--path", default=".", help="项目路径")

    # adg scan
    scan_parser = sub.add_parser("scan", help="扫描文件中的反模式")
    scan_parser.add_argument("files", nargs="+", help="要扫描的文件路径")
    scan_parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")
    scan_parser.add_argument("--json", action="store_true", help="JSON 格式输出")

    args = parser.parse_args()

    if args.command == "init":
        result = init_jcode(
            project_name=args.name,
            project_type=args.type,
            language=args.language,
            framework=args.framework,
            output_dir=args.output,
            force=args.force,
        )
        if result["success"]:
            print(f"✅ 项目 '{args.name}' 初始化成功！")
            print("\n创建的文件:")
            for f in result["files_created"]:
                print(f"  - {f}")
            print("\n下一步:")
            print("  1. 审查 AGENTS.md 并自定义 agent 定义")
            print("  2. 运行首次审计: adg check")
            print("  3. 检查钩子配置: cat .jcode/hooks.json")
        else:
            print(f"❌ 初始化失败: {result['error']}")
            sys.exit(1)

    elif args.command == "check":
        project_path = Path(args.path)
        jcode_yaml = project_path / "jcode.yaml"
        jcode_json = project_path / "jcode.json"

        if jcode_yaml.exists():
            print(f"✅ 找到配置文件: {jcode_yaml}")
        elif jcode_json.exists():
            print(f"✅ 找到配置文件: {jcode_json}")
        else:
            print("❌ 未找到治理配置 (jcode.yaml/jcode.json)")
            print("   运行 `adg init` 初始化项目")
            sys.exit(1)

        hooks_path = project_path / ".jcode" / "hooks.json"
        if hooks_path.exists():
            print(f"✅ 钩子配置: {hooks_path}")
        else:
            print("⚠️  未找到钩子配置")

        agents_path = project_path / "AGENTS.md"
        if agents_path.exists():
            print(f"✅ Agent 定义: {agents_path}")
        else:
            print("⚠️  未找到 AGENTS.md")

    elif args.command == "scan":
        import json

        results = scan_files(args.files)
        if args.json:
            output = []
            for r in results:
                output.append(
                    {
                        "file": r.file,
                        "language": r.language,
                        "passed": r.passed,
                        "error": r.error,
                        "issues": [
                            {
                                "line": i.line,
                                "column": i.column,
                                "rule_id": i.rule_id,
                                "severity": i.severity,
                                "category": i.category,
                                "message": i.message,
                                "fix_hint": i.fix_hint,
                            }
                            for i in r.issues
                        ],
                    }
                )
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            exit_code = print_results(results, verbose=args.verbose)
            sys.exit(exit_code)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
