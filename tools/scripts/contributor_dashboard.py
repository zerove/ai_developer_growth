#!/usr/bin/env python3
"""
贡献者仪表板生成器
生成贡献者统计、案例研究统计、工具推荐统计等
"""

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


class ContributorDashboard:
    def __init__(self, repo_root: Path = Path(".")) -> None:
        self.repo_root = repo_root
        self.stats: dict[str, Any] = {}

    def analyze_case_studies(self) -> dict[str, Any]:
        """分析案例研究统计"""
        cases_dir = self.repo_root / "case-studies"
        if not cases_dir.exists():
            return {"total": 0, "by_type": {}, "by_tool": {}, "avg_boost": 0, "max_boost": 0}

        total = 0
        by_type: Counter[str] = Counter()
        by_tool: Counter[str] = Counter()
        boosts: list[float] = []

        for case_file in cases_dir.glob("*.md"):
            if case_file.name in ["README.md", "INDEX.md"]:
                continue
            content = case_file.read_text(encoding="utf-8")
            total += 1

            # 提取项目类型
            type_match = re.search(r"项目类型[：:]\s*([^\n|]+)", content)
            if type_match:
                by_type[type_match.group(1).strip()] += 1

            # 提取工具栈
            tool_match = re.search(r"AI 工具栈[：:]\s*([^\n|]+)", content)
            if tool_match:
                by_tool[tool_match.group(1).strip()] += 1

            # 提取效率提升
            boost_match = re.search(r"效率提升[：:]\s*([\d.]+)x", content)
            if boost_match:
                boosts.append(float(boost_match.group(1)))

        return {
            "total": total,
            "by_type": dict(by_type),
            "by_tool": dict(by_tool),
            "avg_boost": round(sum(boosts) / len(boosts), 1) if boosts else 0,
            "max_boost": max(boosts) if boosts else 0,
        }

    def analyze_tool_matrix(self) -> dict[str, int]:
        """分析工具矩阵"""
        matrix_file = self.repo_root / "docs" / "tools" / "ai-tool-matrix.md"
        if not matrix_file.exists():
            return {"recommended": 0, "stable": 0, "legacy": 0, "total": 0}

        content = matrix_file.read_text(encoding="utf-8")

        # 统计推荐/稳定/遗留工具
        recommended = len(re.findall(r"✅\s*\*\*推荐\*\*", content))
        stable = len(re.findall(r"⚠️\s*\*\*稳定\*\*", content))
        legacy = len(re.findall(r"❌\s*\*\*遗留\*\*", content))

        return {"recommended": recommended, "stable": stable, "legacy": legacy, "total": recommended + stable + legacy}

    def analyze_contributors(self) -> dict[str, Any]:
        """分析贡献者 (从 git log)"""
        try:
            import subprocess

            # 获取贡献者提交数
            result = subprocess.run(
                ["git", "shortlog", "-sn", "--all"], capture_output=True, text=True, cwd=self.repo_root
            )
            contributors = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    count, name = line.strip().split("\t", 1)
                    contributors.append({"name": name, "commits": int(count)})

            return {"total_contributors": len(contributors), "top_contributors": contributors[:10], "all": contributors}
        except (subprocess.SubprocessError, ValueError, FileNotFoundError):
            return {"total_contributors": 0, "top_contributors": [], "all": []}

    def analyze_docs_coverage(self) -> dict[str, Any]:
        """分析文档覆盖率"""
        docs_dir = self.repo_root / "docs"
        if not docs_dir.exists():
            return {"total": 0, "categories": {}}

        total = 0
        categories = {}

        for cat_dir in docs_dir.iterdir():
            if cat_dir.is_dir() and not cat_dir.name.startswith("."):
                md_files = list(cat_dir.glob("*.md"))
                categories[cat_dir.name] = len(md_files)
                total += len(md_files)

        return {"total": total, "categories": categories}

    def analyze_quality_fixes(self) -> dict[str, Any]:
        """分析质量修复情况 — 每个贡献者修复了多少质量问题"""
        try:
            import subprocess

            # 从 git log 分析修复提交
            result = subprocess.run(
                ["git", "log", "--all", "--oneline", "--grep=fix", "--grep=quality", "--format=%an %s", "--regexp-ignore-case"],
                capture_output=True, text=True, cwd=self.repo_root
            )
            fixers: Counter[str] = Counter()
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    name = line.split(" ", 1)[0]
                    fixers[name] += 1

            return {
                "total_fix_commits": sum(fixers.values()),
                "top_fixers": [{"name": k, "fixes": v} for k, v in fixers.most_common(10)],
            }
        except (subprocess.SubprocessError, ValueError, FileNotFoundError):
            return {"total_fix_commits": 0, "top_fixers": []}

    def generate_dashboard(self, output_format: str = "markdown") -> str:
        """生成仪表板"""
        case_stats = self.analyze_case_studies()
        tool_stats = self.analyze_tool_matrix()
        contrib_stats = self.analyze_contributors()
        docs_stats = self.analyze_docs_coverage()

        date_str = datetime.now().strftime("%Y-%m-%d")

        if output_format == "markdown":
            lines = []
            lines.append("# 📊 贡献者仪表板")
            lines.append(f"> 生成时间: {date_str}")
            lines.append("")

            # 案例研究统计
            lines.append("## 📚 案例研究统计")
            lines.append(f"- **总数**: {case_stats['total']} 个真实案例")
            lines.append(f"- **平均效率提升**: {case_stats['avg_boost']}x")
            lines.append(f"- **最高效率提升**: {case_stats['max_boost']}x")
            lines.append("")
            lines.append("### 按项目类型分布")
            for typ, count in sorted(case_stats["by_type"].items(), key=lambda x: -x[1]):
                lines.append(f"- {typ}: {count}")
            lines.append("")
            lines.append("### 按 AI 工具栈分布")
            for tool, count in sorted(case_stats["by_tool"].items(), key=lambda x: -x[1]):
                lines.append(f"- {tool}: {count}")
            lines.append("")

            # 工具矩阵
            lines.append("## 🛠️ AI 工具矩阵")
            lines.append(f"- **推荐 (✅)**: {tool_stats['recommended']} 个")
            lines.append(f"- **稳定 (⚠️)**: {tool_stats['stable']} 个")
            lines.append(f"- **遗留 (❌)**: {tool_stats['legacy']} 个")
            lines.append("")

            # 文档覆盖
            lines.append("## 📚 文档覆盖率")
            lines.append(f"- **总文档数**: {docs_stats['total']}")
            for cat, count in sorted(docs_stats["categories"].items(), key=lambda x: -x[1]):
                lines.append(f"  - {cat}: {count}")
            lines.append("")

            # 贡献者
            lines.append("## 👥 贡献者排行榜")
            for i, c in enumerate(contrib_stats["top_contributors"][:10], 1):
                lines.append(f"{i}. **{c['name']}** - {c['commits']} commits")
            lines.append("")
            lines.append(f"**总贡献者**: {contrib_stats['total_contributors']} 人")
            lines.append("")

            # 质量修复统计
            fix_stats = self.analyze_quality_fixes()
            if fix_stats["total_fix_commits"] > 0:
                lines.append("## 🔧 质量修复统计")
                lines.append(f"- **总修复提交**: {fix_stats['total_fix_commits']} 次")
                lines.append("### 修复者排行:")
                for f in fix_stats["top_fixers"][:5]:
                    lines.append(f"- {f['name']}: {f['fixes']} 次修复")
                lines.append("")

            lines.append("---")
            lines.append("*由 `tools/scripts/contributor_dashboard.py` 自动生成*")

            return "\n".join(lines)

        elif output_format == "json":
            return json.dumps(
                {
                    "generated_at": date_str,
                    "case_studies": case_stats,
                    "tool_matrix": tool_stats,
                    "contributors": contrib_stats,
                    "docs_coverage": docs_stats,
                },
                ensure_ascii=False,
                indent=2,
            )

        return ""


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="生成贡献者仪表板")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", "-o", help="输出文件路径")
    args = parser.parse_args()

    dashboard = ContributorDashboard()
    result = dashboard.generate_dashboard(args.format)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"✅ 仪表板已保存到: {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
