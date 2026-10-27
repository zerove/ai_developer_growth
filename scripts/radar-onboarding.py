#!/usr/bin/env python3
"""
能力雷达 Onboarding 引导脚本

帮助新员工快速上手能力雷达自评工具
"""

import json
import sys
from pathlib import Path

# Add capability-radar src to path
RADAR_SRC = Path(__file__).parent.parent / "examples" / "capability-radar" / "src"
sys.path.insert(0, str(RADAR_SRC))

from assessment import AssessmentEngine, print_result  # noqa: E402
from capability_model import Dimension, Level  # noqa: E402


def print_welcome() -> None:
    """打印欢迎横幅"""
    print("=" * 60)
    print("  🎯 欢迎使用 AI 时代开发者能力雷达 - Onboarding 引导")
    print("=" * 60)
    print()
    print("这个工具将帮助你在 15 分钟内完成能力自评，")
    print("生成个人能力雷达图和个性化成长建议。")
    print()
    print("📋 评估维度 (5个):")
    for dim in Dimension:
        print(f"   {dim.value}: {dim.label}")
    print()
    print("📊 等级体系 (L0-L4):")
    for level in Level:
        print(f"   {level.value}: {level.label}")
    print()


def run_interactive() -> None:
    """运行交互式评估"""
    print_welcome()

    engine = AssessmentEngine()
    result = engine.run_interactive()

    # 打印结果
    print_result(result)

    # 询问是否导出
    export = input("\n是否导出报告? (y/n, 默认 y): ").strip().lower()
    if export != "n":
        format_choice = input("导出格式 (md/json/both, 默认 both): ").strip().lower()
        if format_choice == "md":
            engine.export_markdown(result)
        elif format_choice == "json":
            engine.export_json(result)
        else:
            engine.export_markdown(result)
            engine.export_json(result)
        print("✅ 报告已导出")


def run_demo() -> None:
    """运行演示模式"""
    print_welcome()
    print("🎮 演示模式：使用预设 L2 答案快速跑通流程")
    print()

    engine = AssessmentEngine()

    # 使用预设的 L2 答案
    for dim in Dimension:
        for q_id, _, _ in engine.QUESTIONS[dim]:
            engine.answers.append(
                {
                    "dimension": dim,
                    "question_id": q_id,
                    "selected_level": Level.L2,
                    "confidence": 3,
                }
            )

    result = engine.calculate_result()
    print_result(result)

    print("\n✅ 演示完成！现在你可以运行交互式评估：")
    print("   python -m src.cli")


def run_batch(input_file: str, output_md: str | None = None, output_json: str | None = None) -> None:
    """批量导入评估"""
    print(f"📥 从 {input_file} 导入答案...")

    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    engine = AssessmentEngine()
    for item in data.get("answers", []):
        engine.answers.append(
            {
                "dimension": Dimension(item["dimension"]),
                "question_id": item["question_id"],
                "selected_level": Level(item["level"]),
                "confidence": item.get("confidence", 3),
            }
        )

    result = engine.calculate_result()

    if output_md:
        engine.export_markdown(result, output_md)
        print(f"✅ Markdown 报告已保存: {output_md}")

    if output_json:
        engine.export_json(result, output_json)
        print(f"✅ JSON 报告已保存: {output_json}")

    if not output_md and not output_json:
        print_result(result)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="能力雷达 Onboarding 引导脚本")
    parser.add_argument("--demo", action="store_true", help="运行演示模式")
    parser.add_argument("--input", "-i", help="输入答案 JSON 文件")
    parser.add_argument("--output", "-o", help="输出 Markdown 报告文件")
    parser.add_argument("--json", help="输出 JSON 报告文件")

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.input:
        run_batch(args.input, args.output, args.json)
    else:
        run_interactive()


if __name__ == "__main__":
    main()
