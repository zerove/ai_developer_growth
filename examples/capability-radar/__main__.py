#!/usr/bin/env python3
# noqa: N999
"""Capability Radar CLI - AI Era Developer Self-Assessment Tool."""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from assessment import AssessmentEngine, print_result


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="capability-radar",
        description="AI 时代开发者能力雷达图自我评估工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  capability-radar                    # 交互式评估
  capability-radar -i answers.json    # 从 JSON 文件导入
  capability-radar -o report.md       # 导出 Markdown 报告
  capability-radar --json out.json    # 导出 JSON 结果

评估维度 (5 个):
  1. 问题定义与产品思维
  2. 架构决策与系统设计
  3. AI 协作与提示工程
  4. 工程严谨性与质量文化
  5. 学习与知识内化

每个维度 2 题，共 10 题，约 3-5 分钟完成。
等级体系: L0-L4 (代码搬运工 → AI 辅助工程师 → AI 原生工程师 → AI 架构师 → 技术领袖)
""",
    )

    parser.add_argument(
        "-i", "--input",
        metavar="FILE",
        help="从 JSON 文件导入答案 (用于自动化/CI)",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="导出 Markdown 报告文件",
    )
    parser.add_argument(
        "--json",
        metavar="FILE",
        help="导出 JSON 结果文件",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式，仅输出结果摘要",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="capability-radar 0.1.0",
    )

    args = parser.parse_args()

    engine = AssessmentEngine()

    if args.input:
        # Load from JSON
        try:
            result = engine.run_from_json(args.input)
        except FileNotFoundError:
            print(f"错误: 文件不存在: {args.input}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"错误: 解析 JSON 失败: {e}", file=sys.stderr)
            return 1
    else:
        # Interactive mode
        try:
            result = engine.run_interactive()
        except KeyboardInterrupt:
            print("\n\n已取消。")
            return 130
        except EOFError:
            print("\n\n输入结束。")
            return 1

    # Print result
    if not args.quiet:
        print_result(result)
    else:
        # Quiet mode: just summary
        print(f"综合等级: {result.overall_level.label}")
        print(f"最弱维度: {result.weakest_dimension.label} ({result.dimension_scores[result.weakest_dimension]:.2f})")
        print(f"最强维度: {result.strongest_dimension.label} ({result.dimension_scores[result.strongest_dimension]:.2f})")

    # Export files
    if args.json:
        engine.export_json(result, args.json)
        if not args.quiet:
            print(f"\n📄 JSON 结果已保存: {args.json}")

    if args.output:
        engine.export_markdown(result, args.output)
        if not args.quiet:
            print(f"📄 Markdown 报告已保存: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
