"""Capability Model Definition - Core data structures for the radar assessment."""

from dataclasses import dataclass, field
from enum import Enum


class Level(Enum):
    """Capability levels L0-L4."""
    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3
    L4 = 4

    @property
    def label(self) -> str:
        labels = {
            Level.L0: "L0: 代码搬运工",
            Level.L1: "L1: AI 辅助工程师",
            Level.L2: "L2: AI 原生工程师",
            Level.L3: "L3: AI 架构师/技术负责人",
            Level.L4: "L4: AI 时代技术领袖",
        }
        return labels[self]


class Dimension(Enum):
    """Five capability dimensions."""
    PRODUCT = "product"           # 问题定义与产品思维
    ARCHITECTURE = "architecture" # 架构决策与系统设计
    AI_COLLABORATION = "ai_collab" # AI 协作与提示工程
    ENGINEERING = "engineering"   # 工程严谨性与质量文化
    LEARNING = "learning"         # 学习与知识内化

    @property
    def label(self) -> str:
        labels = {
            Dimension.PRODUCT: "问题定义与产品思维",
            Dimension.ARCHITECTURE: "架构决策与系统设计",
            Dimension.AI_COLLABORATION: "AI 协作与提示工程",
            Dimension.ENGINEERING: "工程严谨性与质量文化",
            Dimension.LEARNING: "学习与知识内化",
        }
        return labels[self]

    @property
    def description(self) -> str:
        descs = {
            Dimension.PRODUCT: "从'实现需求'到'定义值得解决的问题'，包含需求澄清、问题发现、产品定义、战略洞察",
            Dimension.ARCHITECTURE: "从'无设计'到'平台化思维'，包含模块设计、系统设计、技术权衡、ADR 文化",
            Dimension.AI_COLLABORATION: "从'不用 AI'到'元能力构建'，包含结构化协作、工作流编排、工具/框架开发",
            Dimension.ENGINEERING: "从'能跑就行'到'文化塑造'，包含 TDD、质量内建、度量驱动、可观测性",
            Dimension.LEARNING: "从'依赖 AI'到'知识创造'，包含主动内化、模式识别、知识输出、避免依赖症",
        }
        return descs[self]


@dataclass
class LevelDescriptor:
    """Descriptor for a specific level in a dimension."""
    level: Level
    description: str
    typical_behaviors: list[str] = field(default_factory=list)
    key_transition: str = ""


# Dimension level descriptors - core of the model
DIMENSION_DESCRIPTORS: dict[Dimension, dict[Level, LevelDescriptor]] = {
    Dimension.PRODUCT: {
        Level.L0: LevelDescriptor(
            level=Level.L0,
            description="接收需求，直接开写代码",
            typical_behaviors=["收到'做个登录页'直接开写", "不问用户类型、边界条件、成功指标"],
            key_transition="开始提问：用户是谁？成功标准是什么？",
        ),
        Level.L1: LevelDescriptor(
            level=Level.L1,
            description="澄清需求，理解边界",
            typical_behaviors=["问清楚用户类型、边界情况、验收标准", "能拆解出用户故事和验收标准"],
            key_transition="从'问清楚'到'发现真问题'",
        ),
        Level.L2: LevelDescriptor(
            level=Level.L2,
            description="发现问题，定义产品",
            typical_behaviors=["从'要登录页'挖掘到'要降低注册流失 30%'", "能独立完成 MVP 范围、优先级、验收标准定义"],
            key_transition="建立 ADR 文化，决策可追溯",
        ),
        Level.L3: LevelDescriptor(
            level=Level.L3,
            description="独立完成 0→1 产品定义",
            typical_behaviors=["含 MVP 范围、优先级、成功指标、上线计划", "能说服利益相关者，推动跨团队协作"],
            key_transition="结合市场/商业判断决定'构建什么'",
        ),
        Level.L4: LevelDescriptor(
            level=Level.L4,
            description="战略洞察，决定构建什么",
            typical_behaviors=["基于市场趋势、竞品、商业模型做产品决策", "能定义新品类、创造新需求"],
            key_transition="影响组织级产品战略",
        ),
    },
    Dimension.ARCHITECTURE: {
        Level.L0: LevelDescriptor(
            level=Level.L0,
            description="无设计，直接开写，后期重构",
            typical_behaviors=["函数堆砌，无模块边界", "后期大规模重构"],
        ),
        Level.L1: LevelDescriptor(
            level=Level.L1,
            description="模块设计，理解 SOLID",
            typical_behaviors=["能画出模块图、定义接口", "理解单一职责、依赖倒置"],
        ),
        Level.L2: LevelDescriptor(
            level=Level.L2,
            description="系统设计，处理非功能性需求",
            typical_behaviors=["并发、一致性、可观测性、演进性", "能做技术选型权衡，文档化 ADR"],
        ),
        Level.L3: LevelDescriptor(
            level=Level.L3,
            description="技术选型权衡，指导团队",
            typical_behaviors=["在约束下做 Trade-off，输出 ADR", "建立团队架构评审机制"],
        ),
        Level.L4: LevelDescriptor(
            level=Level.L4,
            description="平台化思维，降低认知负荷",
            typical_behaviors=["设计可复用平台/框架", "建立架构治理体系"],
        ),
    },
    Dimension.AI_COLLABORATION: {
        Level.L0: LevelDescriptor(
            level=Level.L0,
            description="不使用 AI，纯手写代码",
            typical_behaviors=["拒绝或不信任 AI", "认为 AI 写不出好代码"],
        ),
        Level.L1: LevelDescriptor(
            level=Level.L1,
            description="问答式使用，逐行审查，低信任",
            typical_behaviors=["'帮我写个函数'", "逐行检查 AI 代码，效率未必提升"],
        ),
        Level.L2: LevelDescriptor(
            level=Level.L2,
            description="结构化协作，Prompt 模板、上下文管理、迭代优化",
            typical_behaviors=["有固定 Prompt 库、CONTEXT.md 管理", "AI 做 60%+ 代码，验证闭环跑通"],
        ),
        Level.L3: LevelDescriptor(
            level=Level.L3,
            description="工作流编排，Agent Workflow、自动化 Pipeline",
            typical_behaviors=["设计 Prompt Chain、Multi-Agent Workflow", "AI 做 80%+，自动化测试/修复/部署"],
        ),
        Level.L4: LevelDescriptor(
            level=Level.L4,
            description="元能力构建，开发 AI 工具/框架给团队用",
            typical_behaviors=["建立组织级 AI 协作标准", "输出可复用的 AI 工作流框架"],
        ),
    },
    Dimension.ENGINEERING: {
        Level.L0: LevelDescriptor(
            level=Level.L0,
            description="能跑就行，无测试、无 lint、直推主分支",
            typical_behaviors=["手动测试、无 CI、bug 上线常态"],
        ),
        Level.L1: LevelDescriptor(
            level=Level.L1,
            description="基础规范：有测试、CI 跑通、Code Review 走形式",
            typical_behaviors=["单元测试覆盖核心逻辑", "PR 模板、基础 lint"],
        ),
        Level.L2: LevelDescriptor(
            level=Level.L2,
            description="质量内建：TDD、契约测试、混沌工程、性能基线、安全扫描",
            typical_behaviors=["测试先行、契约测试保接口", "性能基线、安全扫描入 CI"],
        ),
        Level.L3: LevelDescriptor(
            level=Level.L3,
            description="度量驱动：追踪 DORA、缺陷逃逸率、技术债偿还率",
            typical_behaviors=["数据驱动工程效能改进", "建立质量门禁、自动化治理"],
        ),
        Level.L4: LevelDescriptor(
            level=Level.L4,
            description="文化塑造：建立工程文化、输出最佳实践规范",
            typical_behaviors=["指导团队、建立工程标准", "影响组织级工程效能"],
        ),
    },
    Dimension.LEARNING: {
        Level.L0: LevelDescriptor(
            level=Level.L0,
            description="依赖 AI，遇到不会就问，不记不练",
            typical_behaviors=["复制粘贴 AI 答案", "同一个问题问多次"],
        ),
        Level.L1: LevelDescriptor(
            level=Level.L1,
            description="速查式学习，文档/教程过目即忘，需要时再搜",
            typical_behaviors=["收藏夹吃灰", "学完即忘，无个人知识库"],
        ),
        Level.L2: LevelDescriptor(
            level=Level.L2,
            description="主动内化：费曼学习法、建立个人知识库、输出倒逼输入",
            typical_behaviors=["有 Obsidian/Notion 知识库", "每周产出至少 1 篇沉淀"],
        ),
        Level.L3: LevelDescriptor(
            level=Level.L3,
            description="模式识别：从杂乱信息提炼通用模式，形成心智模型",
            typical_behaviors=["能跨领域类比、抽象出通用框架", "产出原创洞察、开源工具、技术博客"],
        ),
        Level.L4: LevelDescriptor(
            level=Level.L4,
            description="知识创造：产出原创洞察、开源工具、影响社区",
            typical_behaviors=["开源项目/社区贡献", "大会分享、建立个人品牌"],
        ),
    },
}


def get_descriptor(dimension: Dimension, level: Level) -> LevelDescriptor:
    """Get level descriptor for a dimension."""
    return DIMENSION_DESCRIPTORS[dimension][level]


def get_all_descriptors(dimension: Dimension) -> dict[Level, LevelDescriptor]:
    """Get all level descriptors for a dimension."""
    return DIMENSION_DESCRIPTORS[dimension]
