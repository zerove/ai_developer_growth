# AI Developer Growth - Swarm Configuration

## Agent Roles

This project supports multi-agent collaboration with the following roles:

### Core Agents

| Agent | Role | Responsibilities |
|-------|------|------------------|
| knowledge-curator | 知识策展人 | 维护知识库、验证案例、更新索引 |
| governance-auditor | 治理审计员 | 代码质量、安全、合规审计 |
| workflow-optimizer | 工作流优化师 | 效率分析、工具推荐、流程优化 |
| community-catalyst | 社区催化剂 | 贡献管理、案例验证、激励机制 |

### Collaboration Modes

#### 1. Parallel Review
Multiple agents review different aspects simultaneously:
- governance-auditor: 代码质量
- knowledge-curator: 文档完整性
- workflow-optimizer: 效率影响

#### 2. Sequential Pipeline
Agents work in sequence:
1. knowledge-curator: 验证案例格式
2. governance-auditor: 代码审查
3. workflow-optimizer: 效率评估
4. community-catalyst: 发布准备

#### 3. Swarm Intelligence
All agents collaborate on complex tasks:
- 集体讨论架构决策
- 多角度评估方案
- 综合各方面意见

## Swarm Configuration

```yaml
agents:
  - name: knowledge-curator
    model: default
    tools: [python, bash, read, write, edit]
    
  - name: governance-auditor
    model: default
    tools: [python, bash, read, write]
    
  - name: workflow-optimizer
    model: default
    tools: [python, bash, read, write]
    
  - name: community-catalyst
    model: default
    tools: [python, bash, read, write, edit]

concurrency: 4
timeout: 300
```

## Usage

```bash
# 启动 swarm 进行案例验证
swarm run --agents knowledge-curator,governance-auditor --task "validate new case study"

# 并行审查
swarm run --mode parallel --task "review PR #123"

# 顺序流水线
swarm run --mode pipeline --task "prepare release"
```
