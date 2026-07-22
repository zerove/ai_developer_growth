# Jcode Skills 使用指南
使用 `.jcode/scripts/` 下的 5 个可执行脚本以及新增的 enforcement 脚本。

## 概览

| Skill | 功能 | 版本 | 命令 |
|-------|------|------|------|
| knowledge-curator | 知识库维护 | v1.0 | `python .jcode/scripts/knowledge-curator.py <action>` |
| governance-auditor | 治理审计 | v1.2 | `python .jcode/scripts/governance-auditor.py <action>` |
| governance-docs-validator | 治理文档验证 | v1.0 | `python .jcode/scripts/governance-docs-validator.py <action>` |
| workflow-optimizer | 工作流优化 | v1.0 | `python .jcode/scripts/workflow-optimizer.py <action>` |
| community-catalyst | 社区催化 | v1.0 | `python .jcode/scripts/community-catalyst.py <action>` |

---

## Enforcement 脚本 (新增)

### validate_agent_definition.py

验证 Agent 定 规范。

```bash
# 验证所有 Agent 定义
python tools/scripts/validate_agent_definition.py --path agents

# 验证单个文件
python tools/scripts/validate_agent_definition.py --file agents/knowledge-curator.md
```

检查项:
- 命名规范 (kebab-case)
- 必需字段 (描述、工具、约束、指令)
- 工具权限最小化
- 约束完整性

### check_ai_annotation.py

检查 AI 生成的代码是否包含 [AI-GEN] 标注。

```bash
# 检查所有 Python 文件
python tools/scripts/check_ai_annotation.py

# 检查指定目录
python tools/scripts/check_ai_annotation.py --path tools/scripts

# 自动添加标注
python tools/scripts/check_ai_annotation.py --fix --model "Claude-4"
```

### ai_quality_gate.py

集成所有 AI 代码质量检查的统一入口。

```bash
# 运行所有检查
python tools/scripts/ai_quality_gate.py --full

# 只检查标注
python tools/scripts/ai_quality_gate.py --check-annotation

# 只检查安全模式
python tools/scripts/ai_quality_gate.py --check-security

# 只检查反模式
python tools/scripts/ai_quality_gate.py --check-patterns
```

检查项:
- AI 代码标注 ([AI-GEN])
- 安全模式检查 (SQL 拼接、硬编码密钥等)
- 类型安全检查 (unwrap/as any)
- 错误处理检查
- 代码结构检查

---

## 1. Knowledge Curator (知识策展人)

维护知识库结构完整性、审核文档质量。

### 命令

```bash
# 扫描所有案例格式完整性
python .jcode/scripts/knowledge-curator.py scan

# 检查文档断链
python .jcode/scripts/knowledge-curator.py audit

# 验证新提交案例
python .jcode/scripts/knowledge-curator.py validate

# 同步工具矩阵
python .jcode/scripts/knowledge-curator.py sync

# 更新知识图谱
python .jcode/scripts/knowledge-curator.py update-moc
```

---

## 2. Governance Auditor (治理审计员 v1.2)

自动化审计漏洞、治理标准合规性。

### 命令

```bash
# 运行 ruff lint 检查
python .jcode/scripts/governance-auditor.py lint

# 运行 ruff format 检查
python .jcode/scripts/governance-auditor.py format

# 运行 mypy 类型检查
python .jcode/scripts/governance-auditor.py typecheck

# 运行 pytest 测试
python .jcode/scripts/governance-auditor.py test

# 运行安全扫描
python .jcode/scripts/governance-auditor.py security

# 验证治理文档
python .jcode/scripts/governance-auditor.py validate-governance-docs

# 检查 AI-SDLC 合规性
python .jcode/scripts/governance-auditor.py check-ai-sdlc-compliance

# 审计幻觉风险
python .jcode/scripts/governance-auditor.py audit-hallucination-risks

# 验证 Agent 定义
python .jcode/scripts/governance-auditor.py validate-agent-definition

# 检查 AI 代码标注
python .jcode/scripts/governance-auditor.py check-ai-annotation

# 运行 AI 代码质量门禁
python .jcode/scripts/governance-auditor.py ai-quality-gate

# 运行完整审计
python .jcode/scripts/governance-auditor.py full
```

---

## 3. Governance Docs Validator (治理文档验证器 v1.0)

验证治理层文档格式、索引引用、交叉引用同步。

### 命令

```bash
# 验证文档格式
python .jcode/scripts/governance-docs-validator.py validate

# 检查索引引用
python .jcode/scripts/governance-docs-validator.py check-index

# 同步交叉引用
python .jcode/scripts/governance-docs-validator.py sync-refs

# 运行完整验证
python .jcode/scripts/governance-docs-validator.py full
```

---

## 4. Workflow Optimizer (工作流优化师)

分析效率数据、优化工作流、推荐工具组合。

### 命令

```bash
# 分析案例效率数据
python .jcode/scripts/workflow-optimizer.py analyze

# 推荐工具组合
python .jcode/scripts/workflow-optimizer.py recommend

# 生成效率报告
python .jcode/scripts/workflow-optimizer.py report
```

---

## 5. Community Catalyst (社区催化剂)

管理社区案例、查看社区统计。

### 命令

```bash
# 查看可用 Issues/PRs
python .jcode/scripts/community-catalyst.py triage

# 验证
python .jcode/scripts/community-catalyst.py validate

# 查看社区统计
python .jcode/scripts/community-catalyst.py stats
```

---

## 自动触发 (Hooksjcode/hooks.json`，以下事件自动触发相应 skill:

| 事件 | 触发的 Skill | 动作 |
|------|-------------|------|
| commit (任何文件) | governance-auditor | lint |
| commit (docs/efficiency/ai-*.md) | governance-docs-validator | validate |
| commit (任何文件) | governance-auditor | ai-quality-gate |
| PR (任何文件) | governance-auditor | full |
| PR (agents/) | governance-auditor | validate-agent-definition |
| PR (任何文件) | governance-auditor | check-ai-annotation |
| PR (GOVERNANCE.md/INDEX.md/CLAUDE.md) | governance-docs-validator | check-index |
| merge (任何文件) | knowledge-curator | update-moc |
| 每周一 9:00 | governance-auditor | full |
| 每周一 10:00 | knowledge-curator | scan |
| 每月1日 9:00 | workflow-optimizer | report |
| 每月1日 9:00 | governance-auditor | ai-quality-gate |
| 每月15日 9:00 | governance-auditor | audit-hallucination-risks |

---

## 快速参考

### 开发新功能
```bash
python .jcode/scripts/governance-auditor.py lint
python .jcode/scripts/governance-auditor.py ai-quality-gate
python .jcode/scripts/governance-auditor.py test
git add . && git commit -m "feat: 新功能"
```

### 添加治理文档
```bash
# 创建文档后
python .jcode/scripts/governance-docs-validator.py validate
python .jcode/scripts/governance-docs-validator.py sync-refs
```

### 添加 Agent 定义
```bash
# 创建 Agent 定义后
python tools/scripts/validate_agent_definition.py --path agents
python tools/scripts/check_ai_annotation.py --path tools/scripts
```

### 发布前检查
```bash
python .jcode/scripts/governance-auditor.py full
python .jcode/scripts/governance-docs-validator.py full
python tools/scripts/ai_quality_gate.py --full
python .jcode/scripts/workflow-optimizer.py report
```

---

## 故障排除

### 常见问题

1. **模块未找到**: 确保在项目根目录运行
2. **权限错误**: 确保脚本有执行权限 (`chmod +x`)
3. **依赖缺失**: 运行 `pip install -r requirements.txt`
4. **Lint 错误**: 运行 `ruff check --fix .` 自动修复
5. **格式错误**: 运行 `ruff format .` 自动格式化
6python tools/scripts/check_ai_annotation.py --fix`
7**: 检查命名是否符合 kebab-case 规范
