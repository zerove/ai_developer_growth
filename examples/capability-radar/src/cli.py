#!/usr/bin/env python3
"""Capability Radar CLI - AI Era Developer Self-Assessment Tool."""

import argparse
import sys

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

等级体系 (L0-L4):
  L0: 代码搬运工        L1: AI 辅助工程师
  L2: AI 原生工程师     L3: AI 架构师/技术负责人
  L4: AI 时代技术领袖

详细能力模型: docs/mindset/capability-model.md
        """,
    )

    parser.add_argument("-i", "--input", help="从 JSON 文件导入答案 (非交互模式)", metavar="FILE")
    parser.add_argument("-o", "--output", help="导出 Markdown 报告到文件", metavar="FILE")
    parser.add_argument("--json", help="导出 JSON 结果到文件", metavar="FILE")
    parser.add_argument("--demo", action="store_true", help="使用演示数据快速跑通流程")

    args = parser.parse_args()

    engine = AssessmentEngine()

    if args.demo:
        # Run with demo data (all L2)
        print("🎮 演示模式: 使用预设答案 (全 L2)...")
        from capability_model import Dimension, Level

        for dim in Dimension:
            for q_id, _, _ in engine.QUESTIONS[dim]:
                engine.answers.append(
                    type(
                        "Answer",
                        (),
                        {
                            "dimension": dim,
                            "question_id": q_id,
                            "selected_level": Level.L2,
                            "confidence": 3,
                        },
                    )()
                )
        result = engine.calculate_result()
    elif args.input:
        # Load from JSON
        result = engine.run_from_json(args.input)
    else:
        # Interactive mode
        result = engine.run_interactive()

    # Print to console
    print_result(result)

    # Export if requested
    if args.output:
        engine.export_markdown(result, args.output)
        print(f"\n📄 Markdown 报告已保存: {args.output}")

    if args.json:
        engine.export_json(result, args.json)
        print(f"📊 JSON 结果已保存: {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
