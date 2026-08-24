#!/usr/bin/env python3
"""
adg — AI Developer Governance CLI

统一命令行入口，管理项目治理配置。
"""

import argparse
import sys
from pathlib import Path

from ai_dev_framework import __version__
from ai_dev_framework.feedback import print_feedback_stats
from ai_dev_framework.jcode_init import init_jcode
from ai_dev_framework.scan import print_results, scan_files
from ai_dev_framework.sdlc_audit import audit_sdlc, print_audit
from ai_dev_framework.sync import sync_project_workflows


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
    init_parser.add_argument("--ci", choices=["github", "none"], default="none", help="生成 CI 配置文件")
    init_parser.add_argument("--no-hooks", action="store_true", help="不安装 git hooks")

    # adg sync
    sync_parser = sub.add_parser("sync", help="同步最新 JCode 工作流与自动化脚本到当前项目")
    sync_parser.add_argument("--path", default=".", help="目标项目路径")

    # adg check
    check_parser = sub.add_parser("check", help="检查项目治理状态")
    check_parser.add_argument("--path", default=".", help="项目路径")

    # adg scan
    scan_parser = sub.add_parser("scan", help="扫描文件中的反模式")
    scan_parser.add_argument("files", nargs="+", help="要扫描的文件路径")
    scan_parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")
    scan_parser.add_argument("--json", action="store_true", help="JSON 格式输出")

    # adg audit
    audit_parser = sub.add_parser("audit", help="运行合规审计")
    audit_sub = audit_parser.add_subparsers(dest="audit_type", help="审计类型")
    sdlc_parser = audit_sub.add_parser("sdlc", help="AI-SDLC 流程合规审计")
    sdlc_parser.add_argument("--path", default=".", help="项目路径")
    sdlc_parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")

    # adg feedback
    feedback_parser = sub.add_parser("feedback", help="误报反馈管理")
    feedback_parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")
    feedback_parser.add_argument("--reset", action="store_true", help="重置所有反馈数据")

    # adg generate-rules
    gen_parser = sub.add_parser("generate-rules", help="为语言生成代码质量规则（需 Jcode agent 提供规则内容）")
    gen_parser.add_argument("language", nargs="?", help="语言名称（小写）")
    gen_parser.add_argument("--file", help="示例文件路径（agent 基于文件分析）")
    gen_parser.add_argument("--force", action="store_true", help="覆盖已有规则")
    gen_parser.add_argument("--list", action="store_true", help="列出已生成规则的语言")
    gen_parser.add_argument("--status", action="store_true", help="查看生成规则状态")
    gen_parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")

    # adg dashboard
    dashboard_parser = sub.add_parser("dashboard", help="仪表板与趋势报告")
    dashboard_sub = dashboard_parser.add_subparsers(dest="dashboard_type", help="仪表板类型")
    # adg dashboard contributor
    db_contrib = dashboard_sub.add_parser("contributor", help="贡献者仪表板")
    db_contrib.add_argument("--path", default=".", help="项目路径")
    db_contrib.add_argument("--format", choices=["markdown", "text"], default="markdown", help="输出格式")
    # adg dashboard trend
    db_trend = dashboard_sub.add_parser("trend", help="质量趋势报告")
    db_trend.add_argument("--path", default=".", help="项目路径")
    db_trend.add_argument("--lookback", type=int, default=10, help="查看最近 N 个快照")
    db_trend.add_argument("--multi", action="store_true", help="显示多点趋势表格")
    db_trend.add_argument("--sparkline", action="store_true", help="仅显示 sparkline")

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

    elif args.command == "sync":
        res = sync_project_workflows(args.path)
        print(f"✅ JCode 工作流同步成功！已同步 {res['synced_files_count']} 个核心脚本到 {res['target']}")

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

    elif args.command == "audit":
        if args.audit_type == "sdlc":
            exit_code = print_audit(audit_sdlc(args.path), verbose=args.verbose)
            sys.exit(exit_code)
        else:
            print("请指定审计类型: adg audit sdlc")
            sys.exit(1)

    elif args.command == "feedback":
        if args.reset:
            from ai_dev_framework.feedback import reset_feedback

            reset_feedback()
            print("✅ 反馈数据已重置")
        else:
            exit_code = print_feedback_stats(verbose=args.verbose)
            sys.exit(exit_code)

    elif args.command == "dashboard":
        if args.dashboard_type == "contributor":
            from tools.scripts.contributor_dashboard import ContributorDashboard  # type: ignore[import-untyped]

            db = ContributorDashboard(Path(args.path))
            print(db.generate_dashboard(output_format=args.format))
        elif args.dashboard_type == "trend":
            from tools.scripts.rules_engine.quality_trends import QualityTracker  # type: ignore[import-untyped]

            tracker = QualityTracker()
            if args.sparkline:
                print(f"Issues sparkline: {tracker.generate_sparkline('total_issues')}")
                print(f"Errors sparkline:  {tracker.generate_sparkline('errors')}")
            elif args.multi:
                print(tracker.generate_multi_trend_report(lookback=args.lookback))
            else:
                report = tracker.generate_trend_report()
                print(tracker.generate_summary(report))
                print()
                print(tracker.format_trend_report(report))
        else:
            print("用法: adg dashboard contributor|trend [--options]")
            sys.exit(1)

    elif args.command == "generate-rules":
        from tools.scripts.rules_engine.rule_generator import (  # type: ignore[import-untyped]
            KNOWN_LANGUAGES,
            list_generated_languages,
            load_generated_rules,
            print_status,
        )

        if args.list:
            langs = list_generated_languages()
            if langs:
                print(f"已生成规则的语言 ({len(langs)}):")
                for lang in langs:
                    rules = load_generated_rules(lang)
                    print(f"  {lang}: {len(rules)} 条规则")
            else:
                print("暂无生成规则。使用 `adg-dev generate-rules <language>` 生成。")
            sys.exit(0)

        if args.status or not args.language:
            print_status(args.language)
            sys.exit(0)

        lang = args.language.lower().strip()
        if lang not in KNOWN_LANGUAGES:
            print(f"未知语言: '{lang}'。支持的语言:")
            for name in sorted(KNOWN_LANGUAGES):
                print(f"  {name}")
            sys.exit(1)

        print(f"\n📝 为 '{lang}' 生成规则")
        print(f"   {'使用示例文件: ' + args.file if args.file else '基于 agent 知识'}")
        print(f"\n   请使用 Jcode skill `/generate-rules {lang}` 来交互式生成规则。")
        print(f"   agent 会基于对 {lang} 的知识生成适合 ADG 引擎的规则。")
        print("\n   或手动调用 Python API:")
        print("     from tools.scripts.rules_engine.rule_generator import save_rules, format_rules")
        print(f"     save_rules('{lang}', rules_list, force={args.force})")
        sys.exit(0)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
