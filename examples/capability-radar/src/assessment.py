"""Assessment Engine - Runs the capability radar self-assessment."""

import json
from dataclasses import dataclass
from datetime import datetime

from capability_model import (
    Dimension,
    Level,
    get_descriptor,
)


@dataclass
class Answer:
    """Single question answer."""

    dimension: Dimension
    question_id: str
    selected_level: Level
    confidence: int  # 1-5


@dataclass
class AssessmentResult:
    """Complete assessment result."""

    timestamp: str
    overall_score: float  # 0-4 float
    overall_level: Level
    dimension_scores: dict[Dimension, float]  # 0-4 float
    dimension_levels: dict[Dimension, Level]  # rounded
    answers: list[Answer]
    radar_data: dict  # for visualization
    recommendations: list[str]
    weakest_dimension: Dimension
    strongest_dimension: Dimension


class AssessmentEngine:
    """Runs the capability radar assessment."""

    # Questions per dimension - each maps to a level
    QUESTIONS = {
        Dimension.PRODUCT: [
            (
                "product_0",
                "收到模糊需求（如'做个登录页'）时，你的第一反应是？",
                [
                    ("直接开写代码", Level.L0),
                    ("先问清楚用户类型、边界情况", Level.L1),
                    ("挖掘真实目标：'是要降低注册流失还是合规要求？'", Level.L2),
                    ("输出含 MVP 范围、优先级、成功指标的 PRD", Level.L3),
                    ("结合市场/商业判断决定'构建什么'，能说服利益相关者", Level.L4),
                ],
            ),
            (
                "product_1",
                "定义成功指标时，你倾向于？",
                [
                    ("凭感觉/不定指标", Level.L0),
                    ("定义基础验收标准（如'能登录'）", Level.L1),
                    ("定义可量化指标（如'注册转化率 > 60%'）", Level.L2),
                    ("建立北极星指标 + 领先/滞后指标体系", Level.L3),
                    ("指标体系驱动产品迭代决策，定期复盘调整", Level.L4),
                ],
            ),
        ],
        Dimension.ARCHITECTURE: [
            (
                "arch_0",
                "开始新模块/服务开发前，你的设计流程是？",
                [
                    ("直接开写，后期重构", Level.L0),
                    ("画模块图、定接口，理解 SOLID", Level.L1),
                    ("处理并发/一致性/可观测性/演进性，输出 ADR", Level.L2),
                    ("在约束下做 Trade-off，建立团队架构评审机制", Level.L3),
                    ("设计可复用平台/框架，建立架构治理体系", Level.L4),
                ],
            ),
            (
                "arch_1",
                "技术选型（如 Redis vs Memcached）时，你的决策依据？",
                [
                    ("习惯/随意选", Level.L0),
                    ("对比基础优劣", Level.L1),
                    ("结合场景做权衡矩阵：维护成本/扩展性/开发速度", Level.L2),
                    ("输出 ADR，团队评审通过，决策可追溯", Level.L3),
                    ("建立选型标准库，新人也能按图索骥", Level.L4),
                ],
            ),
        ],
        Dimension.AI_COLLABORATION: [
            (
                "ai_0",
                "日常编码中 AI 的使用方式？",
                [
                    ("不用 AI", Level.L0),
                    ("问答式：'帮我写个函数'，逐行审查", Level.L1),
                    (
                        "结构化：Prompt 模板 + CONTEXT.md + 迭代优化，AI 做 60%+",
                        Level.L2,
                    ),
                    (
                        "编排：Prompt Chain / Multi-Agent Workflow，AI 做 80%+ 含测试/部署",
                        Level.L3,
                    ),
                    ("造工具：开发团队级 AI 框架/标准，赋能全组", Level.L4),
                ],
            ),
            (
                "ai_1",
                "AI 生成代码的验证流程？",
                [
                    ("无验证/仅肉眼看", Level.L0),
                    ("跑一遍/人工测试", Level.L1),
                    ("自动化测试 + 静态分析 + AI 审计", Level.L2),
                    ("Self-Correction Loop：验证→重试→修复全自动", Level.L3),
                    ("建立组织级验证标准/门禁", Level.L4),
                ],
            ),
        ],
        Dimension.ENGINEERING: [
            (
                "eng_0",
                "代码质量保障机制？",
                [
                    ("能跑就行，无测试/无 CI", Level.L0),
                    ("有单测、CI 跑通、PR 走形式", Level.L1),
                    ("TDD + 契约测试 + 性能基线 + 安全扫描入 CI", Level.L2),
                    ("追踪 DORA/缺陷逃逸率/技术债偿还率，数据驱动改进", Level.L3),
                    ("建立工程文化、输出最佳实践规范、影响组织级效能", Level.L4),
                ],
            ),
            (
                "eng_1",
                "生产环境出 Bug 时的处理？",
                [
                    ("救火/甩锅", Level.L0),
                    ("修复 + 补测试", Level.L1),
                    ("复盘根因 + 改进流程/工具防复发", Level.L2),
                    ("建立混沌工程/自动化回归/故障演练机制", Level.L3),
                    ("零故障文化：事前预防 > 事后修复", Level.L4),
                ],
            ),
        ],
        Dimension.LEARNING: [
            (
                "learn_0",
                "遇到新技术/陌生报错时，学习方式？",
                [
                    ("直接问 AI，复制粘贴，不记不练", Level.L0),
                    ("搜文档/教程，过目即忘，需要时再搜", Level.L1),
                    ("费曼学习法 + 个人知识库 + 每周产出沉淀", Level.L2),
                    ("跨领域类比、抽象通用模式、形成心智模型、输出原创洞察", Level.L3),
                    ("开源工具/社区贡献/大会分享，建立个人品牌", Level.L4),
                ],
            ),
            (
                "learn_1",
                "避免 AI 依赖症的具体做法？",
                [
                    ("无意识/无对策", Level.L0),
                    ("偶尔尝试不问 AI", Level.L1),
                    ("刻意练习：先自己写再对比、Prompt 反向工程、知识库归档", Level.L2),
                    ("能脱离 AI 独立解决核心问题、指导他人内化", Level.L3),
                    ("建立团队/组织级'去 AI 依赖'培养体系", Level.L4),
                ],
            ),
        ],
    }

    def __init__(self) -> None:
        """Initialize the capability assessor with empty answers."""
        self.answers: list[Answer] = []

    def run_interactive(self) -> AssessmentResult:
        """Run interactive CLI assessment."""
        print("\n" + "=" * 60)
        print("  AI 时代开发者能力雷达图 - 自我评估")
        print("=" * 60)
        print("\n说明：每题选择最符合你当前状态的选项 (1-5)")
        print("共 10 题，约 3-5 分钟完成。\n")

        for dim in Dimension:
            print(f"\n{'─' * 60}")
            print(f"📐 维度: {dim.label}")
            print(f"   {dim.description}")
            print(f"{'─' * 60}")

            for q_id, question, options in self.QUESTIONS[dim]:
                print(f"\n❓ {question}")
                for i, (text, lvl) in enumerate(options, 1):
                    print(f"  {i}. [{lvl.label}] {text}")

                while True:
                    try:
                        choice = int(input("  你的选择 (1-5): ").strip())
                        if 1 <= choice <= 5:
                            break
                        print("  请输入 1-5 之间的数字")
                    except ValueError:
                        print("  请输入数字 1-5")

                confidence = int(input("  确信度 (1-5, 默认 3): ").strip() or "3")
                confidence = max(1, min(5, confidence))

                self.answers.append(
                    Answer(
                        dimension=dim,
                        question_id=q_id,
                        selected_level=options[choice - 1][1],
                        confidence=confidence,
                    )
                )

        return self.calculate_result()

    def run_from_json(self, json_path: str) -> AssessmentResult:
        """Run assessment from JSON file (for automation/CI)."""
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("answers", []):
            self.answers.append(
                Answer(
                    dimension=Dimension(item["dimension"]),
                    question_id=item["question_id"],
                    selected_level=Level(item["level"]),
                    confidence=item.get("confidence", 3),
                )
            )

        return self.calculate_result()

    def calculate_result(self) -> AssessmentResult:
        """Calculate final scores from answers."""
        # Aggregate by dimension (weighted by confidence)
        dim_scores: dict[Dimension, list[tuple[Level, int]]] = {
            d: [] for d in Dimension
        }
        for ans in self.answers:
            dim_scores[ans.dimension].append((ans.selected_level, ans.confidence))

        dimension_scores = {}
        dimension_levels = {}

        for dim in Dimension:
            entries = dim_scores[dim]
            if not entries:
                dimension_scores[dim] = 0.0
                dimension_levels[dim] = Level.L0
                continue

            # Weighted average
            total_weight = sum(conf for _, conf in entries)
            weighted_sum = sum(lvl.value * conf for lvl, conf in entries)
            score = weighted_sum / total_weight

            dimension_scores[dim] = round(score, 2)
            dimension_levels[dim] = Level(round(score))

        # Overall level = average of dimension levels
        overall_score = sum(dimension_scores.values()) / len(Dimension)
        overall_level = Level(round(overall_score))

        # Find weakest/strongest
        weakest = min(dimension_scores, key=dimension_scores.get)
        strongest = max(dimension_scores, key=dimension_scores.get)

        # Generate recommendations
        recommendations = self._generate_recommendations(dimension_levels, weakest)

        # Radar chart data
        radar_data = {
            "labels": [d.label for d in Dimension],
            "scores": [dimension_scores[d] for d in Dimension],
            "max_score": 4.0,
        }

        return AssessmentResult(
            timestamp=datetime.now().isoformat(),
            overall_score=round(overall_score, 2),
            overall_level=overall_level,
            dimension_scores=dimension_scores,
            dimension_levels=dimension_levels,
            answers=self.answers,
            radar_data=radar_data,
            recommendations=recommendations,
            weakest_dimension=weakest,
            strongest_dimension=strongest,
        )

    def _generate_recommendations(
        self, levels: dict[Dimension, Level], weakest: Dimension
    ) -> list[str]:
        """Generate personalized recommendations."""
        recs = []

        # Primary: weakest dimension
        current = levels[weakest]
        next_level = Level(min(current.value + 1, 4))
        descriptor = get_descriptor(weakest, next_level)
        recs.append(
            f"🎯 优先提升【{weakest.label}】: 从 {current.label} → {next_level.label}\n"
            f"   目标行为: {descriptor.key_transition or descriptor.description}\n"
            f"   关键动作: {descriptor.typical_behaviors[0] if descriptor.typical_behaviors else '参考 L{next_level.value} 描述'}"
        )

        # Secondary: any L0 dimensions
        for dim, lvl in levels.items():
            if lvl == Level.L0 and dim != weakest:
                next_lvl = Level.L1
                d = get_descriptor(dim, next_lvl)
                recs.append(
                    f"⚠️ 补齐短板【{dim.label}】: 从 L0 → L1\n"
                    f"   起步动作: {d.typical_behaviors[0] if d.typical_behaviors else '参考 L1 描述'}"
                )

        # Growth path
        if all(lvl.value >= 2 for lvl in levels.values()):
            recs.append(
                "🚀 你已是 L2+ AI 原生工程师，建议下一阶段目标：\n"
                "   - 产出 3 个 ADR + 1 个可复用 Prompt Chain + 80%+ 覆盖率模块 (冲 L3)\n"
                "   - 或：输出 1 个团队级工具/规范 + 2 篇深度技术文章 (冲 L3)"
            )

        return recs

    def export_json(self, result: AssessmentResult, path: str) -> None:
        """Export result to JSON."""
        data = {
            "timestamp": result.timestamp,
            "overall_level": result.overall_level.name,
            "dimension_scores": {
                d.value: s for d, s in result.dimension_scores.items()
            },
            "dimension_levels": {
                d.value: lvl.name for d, lvl in result.dimension_levels.items()
            },
            "weakest_dimension": result.weakest_dimension.value,
            "strongest_dimension": result.strongest_dimension.value,
            "recommendations": result.recommendations,
            "radar_data": result.radar_data,
            "answers": [
                {
                    "dimension": a.dimension.value,
                    "question_id": a.question_id,
                    "level": a.selected_level.name,
                    "confidence": a.confidence,
                }
                for a in result.answers
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def export_markdown(self, result: AssessmentResult, path: str) -> None:
        """Export result as Markdown report."""
        lines = [
            "# 能力雷达图评估报告",
            f"\n**评估时间**: {result.timestamp}",
            f"**综合等级**: {result.overall_level.label}",
            "\n## 维度得分",
            "\n| 维度 | 得分 (0-4) | 等级 |",
            "|------|------------|------|",
        ]

        for dim in Dimension:
            score = result.dimension_scores[dim]
            level = result.dimension_levels[dim]
            marker = (
                " 🎯"
                if dim == result.weakest_dimension
                else (" ⭐" if dim == result.strongest_dimension else "")
            )
            lines.append(f"| {dim.label} | {score:.2f} | {level.label} |{marker}")

        lines.extend(
            [
                "\n## 详细雷达数据",
                f"\n```json\n{json.dumps(result.radar_data, ensure_ascii=False, indent=2)}\n```",
                "\n## 个性化建议",
            ]
        )

        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"\n### {i}. {rec}")

        lines.extend(
            [
                "\n---\n",
                "> 💡 建议每季度重测一次，追踪成长轨迹。\n",
                "> 📚 详细能力模型见: `docs/mindset/capability-model.md`",
            ]
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def print_result(result: AssessmentResult) -> None:
    """Pretty print result to console."""
    print("\n" + "=" * 60)
    print("  📊 评估结果")
    print("=" * 60)
    print(f"\n🎯 综合等级: {result.overall_level.label}")
    print(
        f"📉 最弱维度: {result.weakest_dimension.label} ({result.dimension_scores[result.weakest_dimension]:.2f})"
    )
    print(
        f"📈 最强维度: {result.strongest_dimension.label} ({result.dimension_scores[result.strongest_dimension]:.2f})"
    )

    print("\n📐 维度详情:")
    for dim in Dimension:
        score = result.dimension_scores[dim]
        level = result.dimension_levels[dim]
        bar = "█" * int(score) + "░" * (4 - int(score))
        marker = (
            " ← 重点提升"
            if dim == result.weakest_dimension
            else (" ★" if dim == result.strongest_dimension else "")
        )
        print(f"  {dim.label:12} {bar} {score:.2f}  {level.label}{marker}")

    # ASCII Radar Chart
    print("\n🕸️  雷达图:")
    print_radar_chart(result)

    print("\n💡 个性化建议:")
    for i, rec in enumerate(result.recommendations, 1):
        print(f"\n  {i}. {rec}")

    print("\n" + "=" * 60)


def print_radar_chart(result: AssessmentResult) -> None:
    """Print simple ASCII radar chart."""

    # 5 dimensions, create a simple radial chart
    labels = [d.label for d in Dimension]
    scores = [result.dimension_scores[d] for d in Dimension]

    # Scale for display (max 4.0 -> 20 chars)
    scale = 20 / 4.0

    # Print each dimension as a spoke
    for i, (label, score) in enumerate(zip(labels, scores)):
        bar_len = int(score * scale)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        marker = (
            " ← 最弱"
            if i == 0 and score == min(scores)
            else (" ★最强" if i == 1 and score == max(scores) else "")
        )
        print(f"  {label:<12} {bar} {score:.1f}{marker}")
