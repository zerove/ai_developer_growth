# CLAUDE.md - AI Developer Growth Project

## 项目概览
这是一个开源知识库，专注于 AI 时代开发者成长方法论。包含 253 个方法论文档、43 个真实案例研究、10 个代码示例、10 个 ADR 决策记录，以及 4 个核心治理 Agent。新增 15

## 核心结构
```
ai_developer_growth/
├── AGENTS.md              # Agent 定义索引
├── GOVERNANCE.md          # 治理标准
├── CONTRIBUTING.md        # 贡献指南
├── ROADMAP.md             # 路线图
├── INDEX.md               # 文档索引
├── UBIQUITOUS_LANGUAGE.md # 领域术语表
├── agents/                # 4 个核心 Agent 定义
├── case-studies/          # 43 个真实案例研究
├── docs/                  # 253 个方法论文档
│   ├── efficiency/        # 效率相关
│   ├── learning/          # 学习相关
│   ├── tools/             # 工具相关
│   └── ...
├── examples/              # 10 个代码示例（可运行）
│   ├── ai-context-sync/   # 上下文同步工具
│   ├── multi-agent-orch/  # 多 Agent 编排
│   ├── self-correction-loop/ # 自我修正循环
│   ├── ai-task-prioritizer/  # 任务优先级工具
│   └── ...
├── tools/scripts/         # 自动化工具脚本
├── tests/                 # 测试套件
└── .github/workflows/     # CI/CD
```

## 核心 Agent (已定义在 agents/)
1. **knowledge-curator** - 知识策展人：维护知识库结构、案例收集、文档质量
2. **governance-auditor** - 治理审计员：代码质量、安全、治理合规自动化审计
3. **workflow-optimizer** - 工作流优化师：效率数据分析、工作流优化、工具推荐
4. **community-catalyst** - 社区催化剂：贡献流程管理、案例验证、激励机制

## jcode Skills (已注册)
本项目已注册 4 个 jcode skills，可通过斜杠命令调用：

| Skill | 命令 | 用途 |
|-------|------|------|
| knowledge-curator | `/knowledge-curator` | 案例扫描、断链检查、工具矩阵同步 |
| governance-auditor | `/governance-auditor` | lint、typecheck、test、security 审计 |
| workflow-optimizer | `/workflow-optimizer` | 效率分析、工具推荐、工作流优化 |
| community-catalyst | `/community-catalyst` | Issue 分流、案例验证、ADR 生成 |

配置文件位于 `.jcode/` 目录：
- `.jcode/PROJECT.md` - 项目配置
- `.jcode/SWARM.md` - 多 Agent 协作配置
- `.jcode/scripts/` - 4 个可执行脚本

## 已实现参考 Agent (examples/)
- **context-sync** - 自动维护 CONTEXT.md、ADR.md、项目状态同步
- **multi-agent-orch** - PM/Architect/Coder/Reviewer 协作模拟
- **self-correction-loop** - AI 代码质量保证：验证→重试→修正闭环
- **ai-task-prioritizer** - CLI 任务优先级排序，TDD + AI 驱动

## 开发命令
```bash
# 代码质量检查
ruff check .
ruff format --check .
mypy tools/scripts/ --ignore-missing-imports

# 测试
pytest tests/ -v

# 链接审计
python tools/scripts/link_auditor.py .

# 案例验证
python tools/scripts/validate_case_study.py --all

# 治理审计
python tools/scripts/audit_to_pr.py --check-all

# 工具矩阵更新
python tools/scripts/update_ai_tool_matrix.py --check

# 贡献者仪表板
python tools/scripts/contributor_dashboard.py --format markdown
```

## 质量门禁 (GOVERNANCE.md)
- ✅ Ruff lint + format 通过
- ✅ MyPy 类型检查通过
- ✅ Pytest 覆盖率 ≥ 70%
- ✅ 无 `unwrap()`/`expect()`/`as any`
- ✅ 链接审计通过
- ✅ 案例研究格式验证通过

## Agent 定义格式 (GOVERNANCE.md 第 1 节)
Agent 定义必须包含：
- `## agent: <name> (<中文名>)` 标题
- 职责描述 (一句话)
- 作用域
- 核心指令 (具体、可验证、含工具名/文件路径/函数名)
- 工具列表 (最小权限，≤10 个)
- 约束 (明确禁止行为)

## 创建新 Agent 检查清单
- [ ] 命名: kebab-case (如 `feature-builder`)
- [ ] 描述: 一句话明确职责和作用域
- [ ] 指令: 具体、可验证，含工具/路径/函数名
- [ ] 工具: 最小权限，不超过 10 个
- [ ] 约束: 明确禁止行为
- [ ] Gate 1: Prompt 设计审查 (人工)
- [ ] Gate 2: 实现代码审查 (Linter + 类型检查 + 人工)
- [ ] Gate 3: 自动化审计 (CI/CD)
- [ ] Gate 4: 资产更新 (AGENTS.md、CONTEXT.md、ADR.md)
- [ ] 索引更新: 在 AGENTS.md 添加记录

## AI 开发流程规范 (新增 15 个标准文档)

### 治理层 (P0 - 核心流程)
1. **ai-code-generation-quality.md** - 代码生成质量标准 (幻觉检测、输出验证、代码标注)
2. **ai-model-selection.md** - 模型选型与评估标准 (选型矩阵、成本优化、多模型协作)
3. **ai-sdlc.md** - 开发全生命周期标准 (7阶段 SDLC、质量门禁、度量指标)
4. **ai-code-review-checklist.md** - 代码审查专项清单 (幻觉检测、模式复制、过度简化检查)
5. **ai-nondeterministic-testing.md** - 非确定性输出测试标准 (属性测试、模糊测试、契约测试)

### 治理层 (P1 - 工程实践)
6. **ai-hallucination-mitigation.md** - 幻觉检测与缓解标准
7. **ai-code-licensing.md** - 代码归属与许可证标准
8. **ai-dev-environment.md** - 开发环境配置标准
9. **ai-context-window-management.md** - 上下文窗口管理标准
10. **ai-performance-benchmarks.md** - 开发性能基准标准

### 效率层 (P2 - 补充完善)
11. **ai-debugging-standards.md** - 调试专项标准
12. **ai-version-control.md** - 代码版本控制标准
13. **ai-deployment-operations.md** - 部署与运维标准
14. **ai-developer-training.md** - 开发者培训标准
15. **ai-dev-toolchain.md** - 开发工具链标准

## 常用文档链接
- [[GOVERNANCE|通用治理标准]] - Agent 定义格式、5步闭环、4道门禁
- [[docs/agent-dev/prompt-standards|Prompt 编写规范]] - 高质量 Prompt 设计原则
- [[docs/agent-dev/workflow-standards|开发流程规范]] - Agent 开发全流程标准
- [[docs/agent-dev/quality-gates|质量门禁]] - 各阶段质量检查标准
- [[docs/agent-dev/context-management|上下文管理]] - CONTEXT/ADR/AGENTS 维护规范
- [[CONTRIBUTING|贡献指南]] - 案例提交、工具推荐、方法论改进流程

## 语言规则
- 默认使用中文（zh-CN），非必要不使用英文
- AI 回复使用中文，非必要不夹杂英文单词
- 注释、文档使用中文
- 仅在代码标识符、API 名称、技术术语等必须使用英文的场景下使用英文
- Git commit message 使用中文，如 `feat: 添加自动修复引擎`

## 注意事项
- 所有文档使用 Wikilink 格式：`[[../docs/...|显示文本]]`
- 案例研究必须包含：背景/过程/对比/洞察/场景五要素 + 效率对比表
- 新术语先在 `UBIQUITOUS_LANGUAGE.md` 定义
- 禁止硬编码路径，使用相对路径或环境变量
- 所有验证脚本必须在 CI/CD 中自动运行