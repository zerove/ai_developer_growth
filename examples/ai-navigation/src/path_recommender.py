"""
AI Navigation - Personalized Path Recommender

Recommends learning paths based on user background and goals.
"""

from dataclasses import dataclass, field

from .knowledge_index import KnowledgeIndex


@dataclass
class UserProfile:
    """User profile for personalization."""

    role: str  # e.g., "前端工程师", "后端工程师", "全栈工程师"
    experience: str  # e.g., "1年", "3年", "5年+"
    current_tools: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)


@dataclass
class LearningStep:
    """A step in a learning path."""

    step_number: int
    doc_id: str
    title: str
    reason: str
    estimated_time: str
    doc_type: str
    priority: int  # 1-5, 5 is highest


@dataclass
class LearningPath:
    """A personalized learning path."""

    name: str
    description: str
    steps: list[LearningStep]
    total_time: str
    difficulty: str
    prerequisites: list[str]


class PathRecommender:
    """Recommends personalized learning paths."""

    # Role-based starting points
    ROLE_STARTERS = {
        "前端工程师": {
            "methodology": ["cursor-best-practices", "copilot-optimization"],
            "case_study": ["react-dashboard"],
            "first_steps": ["学习 AI 代码补全", "掌握 Prompt 工程基础"],
        },
        "后端工程师": {
            "methodology": ["full-cycle-workflow", "ai-testing-strategies"],
            "case_study": ["fastapi-migration"],
            "first_steps": ["了解 AI 辅助调试", "学习架构设计 Prompt"],
        },
        "全栈工程师": {
            "methodology": ["full-cycle-workflow", "prompt-versioning"],
            "case_study": ["saas-refactoring"],
            "first_steps": ["建立 AI 工作流", "学习全栈 AI 协作"],
        },
        "默认": {
            "methodology": ["ai-learning-methodology", "knowledge-internalization"],
            "case_study": [],
            "first_steps": ["了解 AI 开发工具", "学习基础 Prompt 技巧"],
        },
    }

    # Goal-based recommendations
    GOAL_RECOMMENDATIONS = {
        "提升效率": {
            "keywords": ["效率", "工作流", "自动化"],
            "priority_docs": ["full-cycle-workflow", "ai-automation"],
            "case_filter": lambda doc: "效率" in doc.content,
        },
        "学习 RAG": {
            "keywords": ["RAG", "检索", "向量"],
            "priority_docs": ["rag-for-developers"],
            "case_filter": lambda doc: "RAG" in doc.content or "检索" in doc.content,
        },
        "代码质量": {
            "keywords": ["测试", "质量", "重构"],
            "priority_docs": ["ai-testing-strategies", "tdd-ai"],
            "case_filter": lambda doc: "测试" in doc.content or "重构" in doc.content,
        },
        "架构设计": {
            "keywords": ["架构", "设计", "系统"],
            "priority_docs": ["ai-architecture"],
            "case_filter": lambda doc: "架构" in doc.content or "设计" in doc.content,
        },
    }

    def __init__(self, index: KnowledgeIndex):
        self.index = index

    def recommend(self, user: UserProfile) -> list[LearningPath]:
        """Recommend learning paths based on user profile."""
        paths = []

        # Path 1: Role-based path
        role_path = self._create_role_path(user)
        if role_path:
            paths.append(role_path)

        # Path 2: Goal-based paths
        for goal in user.goals:
            goal_path = self._create_goal_path(user, goal)
            if goal_path:
                paths.append(goal_path)

        # Path 3: Tool-based path
        if user.current_tools:
            tool_path = self._create_tool_path(user)
            if tool_path:
                paths.append(tool_path)

        return paths

    def _create_role_path(self, user: UserProfile) -> LearningPath | None:
        """Create a path based on user role."""
        role_config = self.ROLE_STARTERS.get(user.role, self.ROLE_STARTERS["默认"])

        steps = []
        step_num = 1

        # Add methodology docs
        for doc_id in role_config["methodology"]:
            doc = self.index.get_document(f"methodology-{doc_id}")
            if doc:
                steps.append(
                    LearningStep(
                        step_number=step_num,
                        doc_id=doc.id,
                        title=doc.title,
                        reason=f"适合{user.role}的基础方法论",
                        estimated_time=doc.metadata.get("reading_time", "10min"),
                        doc_type="methodology",
                        priority=5,
                    )
                )
                step_num += 1

        # Add case studies
        for case_id in role_config["case_study"]:
            doc = self.index.get_document(f"case-{case_id}")
            if doc:
                steps.append(
                    LearningStep(
                        step_number=step_num,
                        doc_id=doc.id,
                        title=doc.title,
                        reason=f"与{user.role}工作相关的实战案例",
                        estimated_time="15min",
                        doc_type="case_study",
                        priority=4,
                    )
                )
                step_num += 1

        if not steps:
            return None

        return LearningPath(
            name=f"{user.role} AI 成长路径",
            description=f"为{user.role}设计的 AI 辅助开发学习路径",
            steps=steps,
            total_time=f"{len(steps) * 15}min",
            difficulty=self._get_difficulty(user.experience),
            prerequisites=role_config["first_steps"],
        )

    def _create_goal_path(self, user: UserProfile, goal: str) -> LearningPath | None:
        """Create a path based on user goal."""
        goal_config = self.GOAL_RECOMMENDATIONS.get(goal)
        if not goal_config:
            return None

        steps = []
        step_num = 1

        # Add priority docs
        for doc_id in goal_config["priority_docs"]:
            doc = self.index.get_document(f"methodology-{doc_id}")
            if doc:
                steps.append(
                    LearningStep(
                        step_number=step_num,
                        doc_id=doc.id,
                        title=doc.title,
                        reason=f"直接相关: {goal}",
                        estimated_time=doc.metadata.get("reading_time", "10min"),
                        doc_type="methodology",
                        priority=5,
                    )
                )
                step_num += 1

        # Add relevant case studies
        case_filter = goal_config.get("case_filter")
        if case_filter:
            for doc in self.index.documents:
                if doc.type == "case_study" and case_filter(doc):
                    steps.append(
                        LearningStep(
                            step_number=step_num,
                            doc_id=doc.id,
                            title=doc.title,
                            reason=f"案例实践: {goal}",
                            estimated_time="15min",
                            doc_type="case_study",
                            priority=3,
                        )
                    )
                    step_num += 1
                    if len(steps) >= 5:  # Limit case studies
                        break

        if not steps:
            return None

        return LearningPath(
            name=f"{goal}学习路径",
            description=f"围绕「{goal}」目标的学习路径",
            steps=steps,
            total_time=f"{len(steps) * 15}min",
            difficulty="intermediate",
            prerequisites=["了解基础 AI 开发工具"],
        )

    def _create_tool_path(self, user: UserProfile) -> LearningPath | None:
        """Create a path based on tools used."""
        steps = []
        step_num = 1

        # Find docs related to user's tools
        for doc in self.index.documents:
            tools_in_doc = doc.metadata.get("tools_used", [])
            if isinstance(tools_in_doc, str):
                tools_in_doc = [t.strip() for t in tools_in_doc.split(",")]

            # Check if any user tool is mentioned
            if any(tool in tools_in_doc for tool in user.current_tools):
                steps.append(
                    LearningStep(
                        step_number=step_num,
                        doc_id=doc.id,
                        title=doc.title,
                        reason=f"与你使用的 {', '.join(user.current_tools)} 相关",
                        estimated_time=doc.metadata.get("reading_time", "10min"),
                        doc_type=doc.type,
                        priority=3,
                    )
                )
                step_num += 1
                if len(steps) >= 4:
                    break

        if not steps:
            return None

        return LearningPath(
            name=f"{', '.join(user.current_tools)} 进阶路径",
            description=f"深化 {', '.join(user.current_tools)} 使用技巧",
            steps=steps,
            total_time=f"{len(steps) * 15}min",
            difficulty="intermediate",
            prerequisites=[f"已使用 {', '.join(user.current_tools)}"],
        )

    def _get_difficulty(self, experience: str) -> str:
        """Get difficulty level based on experience."""
        if not experience:
            return "beginner"

        # Extract years
        import re

        match = re.search(r"(\d+)", experience)
        if match:
            years = int(match.group(1))
            if years <= 1:
                return "beginner"
            elif years <= 3:
                return "intermediate"
            else:
                return "advanced"

        return "intermediate"


def create_recommender(repo_root: str) -> PathRecommender:
    """Create a path recommender from repo root."""
    from .knowledge_index import IndexBuilder

    builder = IndexBuilder(repo_root)
    index = builder.build()
    return PathRecommender(index)


if __name__ == "__main__":
    import sys

    repo_root = sys.argv[1] if len(sys.argv) > 1 else "."
    recommender = create_recommender(repo_root)

    print("AI Navigation - Learning Path Recommender")
    print("=" * 50)

    # Example user profile
    user = UserProfile(
        role="前端工程师",
        experience="2年",
        current_tools=["Cursor", "Copilot"],
        goals=["提升效率", "学习 RAG"],
        interests=["Web 开发", "AI 应用"],
    )

    print("\n用户画像:")
    print(f"  角色: {user.role}")
    print(f"  经验: {user.experience}")
    print(f"  工具: {', '.join(user.current_tools)}")
    print(f"  目标: {', '.join(user.goals)}")

    paths = recommender.recommend(user)

    print(f"\n推荐学习路径: {len(paths)} 个")
    print("-" * 50)

    for path in paths:
        print(f"\n📚 {path.name}")
        print(f"   {path.description}")
        print(f"   难度: {path.difficulty} | 预计时间: {path.total_time}")
        print(f"   前置条件: {', '.join(path.prerequisites)}")
        print("   学习步骤:")
        for step in path.steps:
            print(f"     {step.step_number}. [{step.doc_type}] {step.title}")
            print(f"        原因: {step.reason} | 时间: {step.estimated_time}")
