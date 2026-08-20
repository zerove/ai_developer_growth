"""Learning path templates for different roles and skill levels."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import json


@dataclass
class LearningStep:
    step_id: str
    title: str
    doc_path: str
    description: str = ""
    estimated_hours: float = 1.0
    prerequisites: list[str] = field(default_factory=list)


@dataclass
class LearningPathTemplate:
    path_id: str
    name: str
    description: str
    target_level: str  # L0-L4
    role: str  # frontend, backend, fullstack, devops, data
    steps: list[LearningStep] = field(default_factory=list)
    total_estimated_hours: float = 0.0

    def calculate_hours(self) -> float:
        self.total_estimated_hours = sum(s.estimated_hours for s in self.steps)
        return self.total_estimated_hours


# Pre-built templates
TEMPLATES: dict[str, LearningPathTemplate] = {
    "ai-beginner": LearningPathTemplate(
        path_id="ai-beginner",
        name="AI 时代入门路径",
        description="从零开始建立 AI 时代思维模式",
        target_level="L1",
        role="any",
        steps=[
            LearningStep(
                "s1",
                "AI 原生思维",
                "mindset/ai-native-thinking.md",
                "理解 AI 时代的核心思维方式",
                2.0,
            ),
            LearningStep(
                "s2",
                "问题分解",
                "mindset/problem-decomposition.md",
                "学会用 AI 辅助分解复杂问题",
                2.0,
            ),
            LearningStep(
                "s3",
                "三层模型",
                "mindset/three-layer-model.md",
                "理解能力三层模型",
                1.5,
            ),
            LearningStep(
                "s4", "杠杆思维", "mindset/leverage-thinking.md", "找到最大杠杆点", 2.0
            ),
            LearningStep(
                "s5",
                "AI 编程助手",
                "tools/ai-coding-assistants.md",
                "掌握 AI 辅助编程工具",
                3.0,
            ),
        ],
    ),
    "ai-practitioner": LearningPathTemplate(
        path_id="ai-practitioner",
        name="AI 实践者路径",
        description="系统性提升 AI 工程实践能力",
        target_level="L2",
        role="backend",
        steps=[
            LearningStep(
                "s1", "系统思维", "mindset/systems-thinking.md", "建立系统思维模式", 3.0
            ),
            LearningStep(
                "s2",
                "资源整合",
                "mindset/resource-integration.md",
                "学会整合 AI 资源",
                2.0,
            ),
            LearningStep(
                "s3", "本地 LLM", "tools/local-llm-setup.md", "部署本地大模型", 4.0
            ),
            LearningStep(
                "s4", "向量搜索", "tools/ai-search-engines.md", "构建语义搜索", 3.0
            ),
            LearningStep(
                "s5",
                "全周期工作流",
                "efficiency/full-cycle-workflow.md",
                "掌握 AI 协作全流程",
                4.0,
            ),
            LearningStep(
                "s6",
                "成本优化",
                "efficiency/cost-optimization.md",
                "优化 AI 使用成本",
                2.0,
            ),
        ],
    ),
    "ai-leader": LearningPathTemplate(
        path_id="ai-leader",
        name="AI 领导者路径",
        description="培养 AI 时代技术领导力",
        target_level="L3",
        role="fullstack",
        steps=[
            LearningStep(
                "s1", "能力模型", "mindset/capability-model.md", "理解五维能力模型", 2.0
            ),
            LearningStep(
                "s2",
                "知识产品化",
                "efficiency/knowledge-productization.md",
                "将知识转化为产品",
                3.0,
            ),
            LearningStep(
                "s3",
                "质量比较",
                "efficiency/quality-comparison.md",
                "建立质量评估体系",
                2.5,
            ),
            LearningStep(
                "s5",
                "开发者体验",
                "efficiency/developer-experience.md",
                "优化开发者体验",
                3.0,
            ),
            LearningStep(
                "s6",
                "治理框架",
                "governance/governance-framework.md",
                "建立团队治理规范",
                3.0,
            ),
        ],
    ),
}


class LearningPathManager:
    """Manage learning path templates and assignments."""

    def __init__(self, data_dir: str = "data/paths"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_template(self, path_id: str) -> Optional[LearningPathTemplate]:
        """Get a built-in or custom template."""
        return TEMPLATES.get(path_id)

    def list_templates(self, role: str | None = None) -> list[LearningPathTemplate]:
        """List available templates, optionally filtered by role."""
        templates = list(TEMPLATES.values())
        if role:
            templates = [t for t in templates if t.role == role or t.role == "any"]
        return templates

    def recommend_path(
        self, current_level: str, target_level: str, role: str = "any"
    ) -> list[LearningPathTemplate]:
        """Recommend learning paths based on current/target level."""
        level_order = ["L0", "L1", "L2", "L3", "L4"]
        try:
            current_idx = level_order.index(current_level)
            target_idx = level_order.index(target_level)
        except ValueError:
            return []

        recommended = []
        for template in TEMPLATES.values():
            try:
                template_idx = level_order.index(template.target_level)
                if current_idx <= template_idx <= target_idx:
                    if template.role == role or template.role == "any":
                        recommended.append(template)
            except ValueError:
                continue
        return recommended

    def create_custom_path(
        self, path_id: str, name: str, description: str, steps: list[dict]
    ) -> LearningPathTemplate:
        """Create a custom learning path."""
        learning_steps = [LearningStep(**step) for step in steps]
        template = LearningPathTemplate(
            path_id=path_id,
            name=name,
            description=description,
            target_level="L2",
            role="any",
            steps=learning_steps,
        )
        template.calculate_hours()

        # Save custom path
        f = self.data_dir / f"{path_id}.json"
        f.write_text(json.dumps(asdict(template), indent=2, ensure_ascii=False))
        return template

    def get_all_paths(self) -> list[LearningPathTemplate]:
        """Get all paths (built-in + custom)."""
        paths = list(TEMPLATES.values())
        for f in self.data_dir.glob("*.json"):
            data = json.loads(f.read_text())
            paths.append(LearningPathTemplate(**data))
        return paths
