"""
Personalized Mentor

AI-powered learning mentor that:
- Assesses skill levels across 5 dimensions (from capability model)
- Identifies skill gaps
- Generates personalized learning plans
- Tracks progress over time
"""

import json
import logging
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class Level(IntEnum):
    """Capability level (0-4)."""

    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4


class Dimension:
    """The five capability dimensions."""

    PRODUCT = "product"  # 问题定义与产品思维
    ARCHITECTURE = "architecture"  # 架构决策与系统设计
    AI_COLLABORATION = "ai_collaboration"  # AI 协作与提示工程
    ENGINEERING = "engineering"  # 工程严谨性与质量
    LEARNING = "learning"  # 学习与知识内化


# Dimension labels in Chinese
DIMENSION_LABELS = {
    Dimension.PRODUCT: "问题定义与产品思维",
    Dimension.ARCHITECTURE: "架构决策与系统设计",
    Dimension.AI_COLLABORATION: "AI 协作与提示工程",
    Dimension.ENGINEERING: "工程严谨性与质量",
    Dimension.LEARNING: "学习与知识内化",
}

# Level labels
LEVEL_LABELS = {
    Level.L0: "代码搬运工",
    Level.L1: "AI 辅助工程师",
    Level.L2: "AI 原生工程师",
    Level.L3: "AI 架构师",
    Level.L4: "AI 时代技术领袖",
}

# Skill gap descriptions for each dimension at each level transition
SKILL_GAPS = {
    Dimension.PRODUCT: {
        Level.L0: "学习澄清需求，问清楚用户类型和边界情况",
        Level.L1: "从「要登录页」挖掘到「要降低注册流失 30%」",
        Level.L2: "独立完成从 0 到 1 的产品定义，含 MVP 范围和验收标准",
        Level.L3: "结合市场/商业判断决定「构建什么」，能说服利益相关者",
    },
    Dimension.ARCHITECTURE: {
        Level.L0: "学习模块设计，画模块图和接口定义",
        Level.L1: "处理并发、一致性、可观测性",
        Level.L2: "在约束下做 Trade-off，文档化 ADR",
        Level.L3: "设计可复用平台/框架，降低全组认知负荷",
    },
    Dimension.AI_COLLABORATION: {
        Level.L0: "开始使用 AI 工具，从问答式使用起步",
        Level.L1: "掌握 Prompt 模板、上下文管理、迭代优化",
        Level.L2: "设计 Prompt Chain、Agent Workflow、自动化 Pipeline",
        Level.L3: "开发 AI 工具/框架给团队用，建立组织级标准",
    },
    Dimension.ENGINEERING: {
        Level.L0: "建立基础规范：有测试、CI 跑通",
        Level.L1: "实践 TDD、契约测试、混沌工程",
        Level.L2: "追踪 DORA 指标、缺陷逃逸率",
        Level.L3: "建立工程文化、指导团队",
    },
    Dimension.LEARNING: {
        Level.L0: "开始",
        Level.L1: "建立个人知识库",
        Level.L2: "从杂乱信息中提炼通用模式，形成心智模型",
        Level.L3: "产出原创洞察、开源工具、技术博客",
    },
}

# Recommended learning resources for each dimension
LEARNING_RESOURCES = {
    Dimension.PRODUCT: [
        {"level": Level.L1, "title": "产品思维基础", "doc_id": "mindset/product-thinking"},
        {"level": Level.L2, "title": "技术选型方法论", "doc_id": "mindset/tech-selection-methodology"},
        {"level": Level.L3, "title": "架构决策方法", "doc_id": "mindset/architecture-decision"},
    ],
    Dimension.ARCHITECTURE: [
        {"level": Level.L1, "title": "全周期工作流", "doc_id": "efficiency/full-cycle-workflow"},
        {"level": Level.L2, "title": "多 Agent 模式", "doc_id": "efficiency/multi-agent-patterns"},
        {"level": Level.L3, "title": "上下文工程", "doc_id": "efficiency/context-engineering"},
    ],
    Dimension.AI_COLLABORATION: [
        {"level": Level.L1, "title": "Prompt 工程", "doc_id": "learning/prompt-engineering"},
        {"level": Level.L2, "title": "AI 编码效率", "doc_id": "efficiency/ai-coding-efficiency"},
        {"level": Level.L3, "title": "AI 架构设计", "doc_id": "efficiency/ai-architecture-design"},
    ],
    Dimension.ENGINEERING: [
        {"level": Level.L1, "title": "TDD 方法论", "doc_id": "learning/test-driven-development"},
        {"level": Level.L2, "title": "CI/CD 实践", "doc_id": "learning/continuous-integration"},
        {"level": Level.L3, "title": "代码质量工具", "doc_id": "tools/ai-code-quality-tools"},
    ],
    Dimension.LEARNING: [
        {"level": Level.L1, "title": "AI 学习法", "doc_id": "learning/ai-learning-method"},
        {"level": Level.L2, "title": "知识内化", "doc_id": "learning/knowledge-internalization"},
        {"level": Level.L3, "title": "开发者社区", "doc_id": "efficiency/developer-community"},
    ],
}


@dataclass
class SkillAssessment:
    """Assessment of a single dimension."""

    dimension: str
    current_level: Level
    target_level: Level
    confidence: float  # 0-1, how confident we are in the assessment
    gap_description: str
    recommended_resources: list[dict]


@dataclass
class MentorPlan:
    """Personalized learning plan."""

    user_name: str
    assessments: list[SkillAssessment]
    overall_level: Level
    weakest_dimension: str
    strongest_dimension: str
    priority_actions: list[str]
    estimated_weeks: int

    def to_dict(self) -> dict:
        return {
            "user_name": self.user_name,
            "overall_level": self.overall_level.name,
            "overall_level_label": LEVEL_LABELS[self.overall_level],
            "weakest_dimension": DIMENSION_LABELS.get(
                self.weakest_dimension, self.weakest_dimension
            ),
            "strongest_dimension": DIMENSION_LABELS.get(
                self.strongest_dimension, self.strongest_dimension
            ),
            "assessments": [
                {
                    "dimension": DIMENSION_LABELS.get(a.dimension, a.dimension),
                    "current_level": a.current_level.name,
                    "target_level": a.target_level.name,
                    "gap": a.gap_description,
                    "resources": a.recommended_resources,
                }
                for a in self.assessments
            ],
            "priority_actions": self.priority_actions,
            "estimated_weeks": self.estimated_weeks,
        }


class PersonalizedMentor:
    """AI-powered personalized learning mentor.

    Usage:
        mentor = PersonalizedMentor()
        plan = mentor.create_plan(
            name="张三",
            scores={
                "product": 1,
                "architecture": 2,
                "ai_collaboration": 3,
                "engineering": 1,
                "learning": 2,
            }
        )
        mentor.print_plan(plan)
    """

    ALL_DIMENSIONS = [
        Dimension.PRODUCT,
        Dimension.ARCHITECTURE,
        Dimension.AI_COLLABORATION,
        Dimension.ENGINEERING,
        Dimension.LEARNING,
    ]

    def create_plan(
        self,
        name: str,
        scores: dict[str, int],
        target_level: int | None = None,
    ) -> MentorPlan:
        """Create a personalized learning plan.

        Args:
            name: User's name.
            scores: Dict mapping dimension name to level (0-4).
            target_level: Optional target level (defaults to max+1 or L4).

        Returns:
            MentorPlan with assessments and recommendations.
        """
        # Parse scores into Level enums
        dim_levels: dict[str, Level] = {}
        for dim in self.ALL_DIMENSIONS:
            score = scores.get(dim, 0)
            dim_levels[dim] = Level(min(max(score, 0), 4))

        # Calculate overall level (average, rounded down)
        avg = sum(dim_levels.values()) / len(dim_levels)
        overall = Level(min(int(avg), 4))

        # Find weakest and strongest
        weakest = min(dim_levels, key=dim_levels.get)
        strongest = max(dim_levels, key=dim_levels.get)

        # Create assessments
        assessments = []
        for dim in self.ALL_DIMENSIONS:
            current = dim_levels[dim]
            # Target is one level up, unless already at max
            if current < Level.L4:
                dim_target = Level(min(current.value + 1, 4))
            else:
                dim_target = Level.L4

            gap = SKILL_GAPS.get(dim, {}).get(current, "已达最高等级")
            resources = [
                r
                for r in LEARNING_RESOURCES.get(dim, [])
                if r["level"] > current and r["level"] <= dim_target
            ]

            assessments.append(
                SkillAssessment(
                    dimension=dim,
                    current_level=current,
                    target_level=dim_target,
                    confidence=0.8,
                    gap_description=gap,
                    recommended_resources=resources,
                )
            )

        # Generate priority actions (focus on weakest dimension)
        priority_actions = self._generate_actions(weakest, dim_levels[weakest])

        # Estimate time (2-4 weeks per level up, depending on gaps)
        gaps_to_fill = sum(
            1 for a in assessments if a.current_level < a.target_level
        )
        estimated_weeks = gaps_to_fill * 3

        return MentorPlan(
            user_name=name,
            assessments=assessments,
            overall_level=overall,
            weakest_dimension=weakest,
            strongest_dimension=strongest,
            priority_actions=priority_actions,
            estimated_weeks=estimated_weeks,
        )

    def _generate_actions(self, weakest_dim: str, current_level: Level) -> list[str]:
        """Generate priority actions for the weakest dimension."""
        actions = []
        label = DIMENSION_LABELS.get(weakest_dim, weakest_dim)

        if current_level < Level.L1:
            actions.append(f"【紧急】提升{label}: 从 L0 → L1")
            actions.append(f"  起步: {SKILL_GAPS.get(weakest_dim, {}).get(Level.L0, '开始学习')}")
        elif current_level < Level.L2:
            actions.append(f"【重要】提升{label}: 从 L1 → L2")
            actions.append(f"  目标: {SKILL_GAPS.get(weakest_dim, {}).get(Level.L1, '继续深入')}")
        elif current_level < Level.L3:
            actions.append(f"【进阶】提升{label}: 从 L2 → L3")
            actions.append(f"  目标: {SKILL_GAPS.get(weakest_dim, {}).get(Level.L2, '追求卓越')}")
        else:
            actions.append("已达到 L3+ 水平，保持并分享经验")

        # Add general action
        actions.append("  建议: 每周花 3-5 小时专注提升该维度")

        return actions

    def print_plan(self, plan: MentorPlan) -> None:
        """Pretty print the learning plan."""
        print(f"\n{'=' * 60}")
        print(f"  个性化学习计划 - {plan.user_name}")
        print(f"{'=' * 60}")

        print("\n📊 综合评估:")
        print(f"  当前等级: {plan.overall_level.name} ({LEVEL_LABELS[plan.overall_level]})")
        print(
            f"  最弱维度: {DIMENSION_LABELS.get(plan.weakest_dimension, plan.weakest_dimension)}"
        )
        print(
            f"  最强维度: {DIMENSION_LABELS.get(plan.strongest_dimension, plan.strongest_dimension)}"
        )
        print(f"  预计周期: {plan.estimated_weeks} 周")

        print("\n📋 各维度详情:")
        for a in plan.assessments:
            dim_label = DIMENSION_LABELS.get(a.dimension, a.dimension)
            marker = " 🎯" if a.dimension == plan.weakest_dimension else ""
            print(f"\n  {dim_label}{marker}")
            print(f"    当前: {a.current_level.name} → 目标: {a.target_level.name}")
            print(f"    差距: {a.gap_description}")
            if a.recommended_resources:
                print("    推荐:")
                for r in a.recommended_resources[:2]:
                    print(f"      - {r['title']} ({r['doc_id']})")

        print("\n🎯 优先行动:")
        for action in plan.priority_actions:
            print(f"  {action}")

        print(f"\n{'=' * 60}\n")

    def export_plan(self, plan: MentorPlan, path: str | Path) -> None:
        """Export plan to JSON."""
        Path(path).write_text(
            json.dumps(plan.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Exported mentor plan to {path}")
