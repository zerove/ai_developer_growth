# AI Developer Growth - Swarm 配置

## Agent Roles

本项目支持多 Agent 协作，配置如下角色：

### Core Agents

| Agent | Role | Responsibilities |
|-------|------|------------------|
| knowledge-curator | 知识策展人 | 维护知识库、验证案例、更新索引 |
| governance-auditor | 治理审计员 | 代码质量、安全、合规审计 (v1.1) |
| governance-docs-validator | 治理文档验证器 | 验证治理文档、索引引用、交叉引用 |
| workflow-optimizer | 工作流优化师 | 效率分析、工具推荐、流程优化 |
| community-catalyst | 社区催化剂 | 贡献管理、案例验证、激励机制 |

### Collaboration Modes

#### 1. PR Review Workflow (PR 审查工作流)
```mermaid
graph LR
    A[PR 提交] --> B[governance-auditor]
    B --> C[governance-docs-validator]
    C --> D[knowledge-curator]
    D --> E[community-catalyst]
    E --> F[合并]
```

**执行顺序**:
1. governance-auditor: lint + format + typecheck + test
2. governance-docs-validator: 验证治理文档索引完整性
3. knowledge-curator: 验证案例格式、检查断链
4. community-catalyst: 分流 Issue/PR、生成 ADR

#### 2. Weekly Maintenance Workflow (每周维护工作流)
```mermaid
graph LR
    A[每周一 9:00] --> B[governance-auditor]
    B --> C[governance-docs-validator]
    C --> D[knowledge-curator]
    D --> E[workflow-optimizer]
    E --> F[生成报告]
```

**执行顺序**:
1. governance-auditor: 完整审计 (lint + format + typecheck + test)
2. governance-docs-validator: 验证 15 个治理文档
3. knowledge-curator: 扫描案例、检查断链、更新 MOC
4. workflow-optimizer: 生成效率报告

#### 3. Release Prep Workflow (发布准备工作流)
```mermaid
graph LR
    A[发布前] --> B[governance-auditor]
    B --> C[governance-docs-validator]
    C --> D[knowledge-curator]
    D --> E[workflow-optimizer]
    E --> F[community-catalyst]
    F --> G[发布]
```

**执行顺序**:
1. governance-auditor: 完整审计
2. governance-docs-validator: 验证治理文档
3. knowledge-curator: 扫描案例、检查断链
4. workflow-optimizer: 生成效率报告
5. community-catalyst: 贡献者排行榜

#### 4. Monthly Security Workflow (每月安全工作流)
```mermaid
graph LR
    A[每月15日] --> B[governance-auditor]
    B --> C[audit-hallucination-risks]
    C --> D[governance-docs-validator]
    D --> E[生成安全报告]
```

**执行顺序**:
1. governance-auditor: 审计幻觉风险
2. governance-docs-validator: 验证治理文档完整性

## Swarm Configuration

```yaml
agents:
  - name: knowledge-curator
    model: default
    tools: [python, bash, read, write, edit]

  - name: governance-auditor
    model: default
    tools: [python, bash, read, write]

  - name: governance-docs-validator
    model: default
    tools: [python, bash, read]

  - name: workflow-optimizer
    model: default
    tools: [python, bash, read, write]

  - name: community-catalyst
    model: default
    tools: [python, bash, read, write, edit]

concurrency: 5
timeout: 300
```

## Usage

```bash
# PR 审查工作流
python .jcode/scripts/governance-auditor.py full
python .jcode/scripts/governance-docs-validator.py check-index
python .jcode/scripts/knowledge-curator.py scan
python .jcode/scripts/community-catalyst.py leaderboard

# 每周维护工作流
python .jcode/scripts/governance-auditor.py full
python .jcode/scripts/governance-docs-validator.py validate
python .jcode/scripts/knowledge-curator.py audit
python .jcode/scripts/workflow-optimizer.py report

# 每月安全工作流
python .jcode/scripts/governance-auditor.py audit-hallucination-risks
python .jcode/scripts/governance-docs-validator.py full
```

## Quality Gates

### Gate 1: 代码质量
- Ruff lint 通过
- Ruff format 通过
- MyPy 类型检查通过

### Gate 2: 测试覆盖
- Pytest 测试通过
- 覆盖率 ≥ 80%

### Gate 3: 治理文档
- 15 个治理文档格式完整
- 索引引用完整
- 交叉引用同步

### Gate 4: 安全审计
- 无代码不安全模式
- 无文档绝对化声明
- AI-SDLC 合规
