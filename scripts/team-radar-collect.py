#!/usr/bin/env python3
"""
团队能力雷达收集脚本

用于收集团队成员能力雷达数据，生成团队健康度报告。

用法:
    python team-radar-collect.py [team_name] [--input-dir DIR] [--output-dir DIR]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 五个能力维度
DIMENSIONS = [
    "product",           # 问题定义与产品思维
    "architecture",      # 架构决策与系统设计
    "ai_collab",         # AI 协作与提示工程
    "engineering",       # 工程严谨性与质量文化
    "learning",          # 学习与知识内化
]

DIMENSION_LABELS = {
    "product": "问题定义与产品思维",
    "architecture": "架构决策与系统设计",
    "ai_collab": "AI 协作与提示工程",
    "engineering": "工程严谨性与质量文化",
    "learning": "学习与知识内化",
}

LEVEL_LABELS = {
    0: "L0: 代码搬运工",
    1: "L1: AI 辅助工程师",
    2: "L2: AI 原生工程师",
    3: "L3: AI 架构师/技术负责人",
    4: "L4: AI 时代技术领袖",
}


def load_radar_file(file_path: Path) -> dict:
    """加载单个雷达数据文件"""
    try:
        with open(file_path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  无法读取 {file_path}: {e}")
        return None


def collect_radar_data(input_dir: Path) -> dict[str, dict]:
    """收集目录下所有雷达数据"""
    results = {}

    # 查找所有 radar-report-*.json 文件
    for json_file in input_dir.glob("radar-report-*.json"):
        member_name = json_file.stem.replace("radar-report-", "").replace(".json", "")
        data = load_radar_file(json_file)
        if data:
            results[member_name] = data
            print(f"  ✅ 加载: {member_name}")
        else:
            print(f"  ❌ 失败: {member_name}")

    return results


def aggregate_team_radar(individual_results: dict[str, dict]) -> dict:
    """聚合团队雷达 (匿名平均)"""
    if not individual_results:
        return {}

    aggregated = {}

    for dim in DIMENSIONS:
        scores = []
        for member, data in individual_results.items():
            if "dimension_scores" in data and dim in data["dimension_scores"]:
                scores.append(data["dimension_scores"][dim])

        if scores:
            avg = sum(scores) / len(scores)
            min_s = min(scores)
            max_s = max(scores)

            # 分布统计
            dist = {}
            for i in range(5):
                dist[f"L{i}"] = sum(1 for s in scores if int(s) == i)

            aggregated[DIMENSION_LABELS[dim]] = {
                "average": round(avg, 2),
                "min": round(min_s, 2),
                "max": round(max_s, 2),
                "distribution": dist,
                "dimension_key": dim,
            }

    return aggregated


def find_weakest_strongest(team_radar: dict) -> tuple:
    """找出最弱和最强维度"""
    if not team_radar:
        return None, None

    # 过滤掉非维度键
    dim_data = {k: v for k, v in team_radar.items() if "average" in v}
    if not dim_data:
        return None, None

    weakest = min(dim_data.items(), key=lambda x: x[1]["average"])
    strongest = max(dim_data.items(), key=lambda x: x[1]["average"])

    return weakest[0], strongest[0]


def generate_team_report(team_radar: dict, team_name: str, output_dir: Path) -> Path:
    """生成团队雷达 Markdown 报告"""
    weakest, strongest = find_weakest_strongest(team_radar)

    lines = [
        f"# {team_name} 团队能力雷达报告",
        f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**参与人数**: {len([k for k in team_radar.keys() if k != 'individual'])}",
        "\n## 📊 团队雷达概览\n",
    ]

    # 雷达图概览
    for dim_name, data in team_radar.items():
        if "average" not in data:
            continue
        score = data["average"]
        bar = "█" * int(score * 5) + "░" * (20 - int(score * 5))
        marker = ""
        if strongest and dim_name == strongest:
            marker = " ★最强"
        elif weakest and dim_name == weakest:
            marker = " ⚠️最弱"
        lines.append(f"- **{dim_name}**: {bar} {score:.2f}{marker}")

    # 详细数据表
    lines.append("\n## 📊 详细数据")
    lines.append("\n| 维度 | 平均分 | 最低 | 最高 | 标准差 | 分布 |")
    lines.append("|------|--------|------|------|--------|------|")

    for dim_name, data in team_radar.items():
        if "average" not in data:
            continue
        avg = data["average"]
        min_s = data["min"]
        max_s = data["max"]
        dist = data["distribution"]
        dist_str = ", ".join(f"{k}:{v}" for k, v in sorted(dist.items()))
        lines.append(f"| {dim_name} | {avg:.2f} | {min_s:.2f} | {max_s:.2f} | {dist_str} |")

    # 个性化建议
    lines.extend([
        "\n## ⚠️ 团队短板识别",
        f"最弱维度: {weakest} ({team_radar[weakest]['average']:.2f})" if weakest else "无数据",
        f"最强维度: {strongest} ({team_radar[strongest]['average']:.2f})" if strongest else "无数据",
        "\n## 📋 建议行动",
        "1. **针对最弱维度安排专项培训/工作坊**",
        "2. **结对编程/Code Review 重点关注弱项**",
        "3. **邀请内部专家分享强项经验**",
        "4. **招聘/内部流动补充短板维度人才**",
        "5. **建立导师制，强项成员带弱项成员**",
        "\n---\n",
        f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ])

    report_file = Path(output_dir) / f"team-radar-report-{datetime.now().strftime('%Y%m%d')}.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("\n".join(lines), encoding="utf-8")

    return report_file


def main():
    parser = argparse.ArgumentParser(description="团队能力雷达收集与报告生成")
    parser.add_argument("team_name", nargs="?", default="team", help="团队名称")
    parser.add_argument("--input-dir", "-i", default="radar-data", help="输入数据目录 (包含 radar-report-*.json)")
    parser.add_argument("--output-dir", "-o", default="radar-reports", help="输出报告目录")
    parser.add_argument("--member", "-m", action="append", help="指定成员列表 (可多次使用)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"❌ 输入目录不存在: {input_dir}")
        print(f"请先运行能力雷达评估生成数据，或将 radar-report-*.json 放入 {input_dir}/")
        return 1

    print(f"🔍 扫描目录: {input_dir}")
    print(f"📁 团队名称: {args.team_name}")
    print(f"📂 输出目录: {output_dir}")

    # 收集数据
    if args.member:
        # 指定成员模式
        individual_results = {}
        for member in args.member:
            radar_file = input_dir / f"radar-report-{member}.json"
            if radar_file.exists():
                data = load_radar_file(radar_file)
                if data:
                    individual_results[member] = data
                    print(f"  ✅ 加载: {member}")
                else:
                    print(f"  ❌ 读取失败: {member}")
            else:
                print(f"  ⚠️  文件不存在: {radar_file}")
    else:
        # 自动扫描模式
        individual_results = collect_radar_data(Path(args.input_dir))

    if not individual_results:
        print("❌ 未找到任何有效雷达数据")
        return 1

    print(f"\n✅ 成功加载 {len(individual_results)} 位成员的雷达数据")

    # 聚合团队雷达
    team_radar = aggregate_team_radar(individual_results)

    # 生成报告
    output_dir = Path(args.output_dir)
    report_file = generate_team_report(team_radar, args.team_name, output_dir)

    # 同时保存 JSON
    json_file = output_dir / f"team-radar-{datetime.now().strftime('%Y%m%d')}.json"
    json_file.parent.mkdir(parents=True, exist_ok=True)
    report_data = {
        "team": args.team_name,
        "date": datetime.now().isoformat(),
        "members": len(individual_results),
        "radar": {k: v for k, v in team_radar.items() if k != "individual"},
        "individual": individual_results,
    }
    json_file.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n✅ 团队雷达报告已生成:")
    print(f"   📄 Markdown: {report_file}")
    print(f"   📊 JSON: {json_file}")

    # 打印摘要
    print("\n📊 团队雷达摘要:")
    for dim_name, data in team_radar.items():
        if "average" in data:
            bar = "█" * int(data["average"] * 5) + "░" * (20 - int(data["average"] * 5))
            print(f"  {dim_name:12} {bar} {data['average']:.2f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
