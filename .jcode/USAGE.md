# Jcode Skills 使用指南

本文档介绍如何使用 `.jcode/scripts/` 下的 5 个可执行脚本。

## 概览

| Skill | 功能 | 版本 | 命令 |
|-------|------|------|------|
| knowledge-curator | 知识库维护 | v1.0 | `python .jcode/scripts/knowledge-curator.py <action>` |
| governance-auditor | 治理审计 | v1.1 | `python .jcode/scripts/governance-auditor.py <action>` |
| governance-docs-validator | 治理文档验证 | v1.0 | `python .jcode/scripts/governance-docs-validator.py <action>` |
| workflow-optimizer | 工作流优化 | v1.0 | `python .jcode/scripts/workflow-optimizer.py <action>` |
| community-catalyst | 社区催化 | v1.0 | `python .jcode/scripts/community-catalyst.py <action>` |

---

## 1. Knowledge Curator (知识策展人)

维护知识库结构完整性、收集真实案例、审核文档质量。

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

### 输出示例

```
✅ 案例扫描完成: 15 个案例
✅ 文档审计完成: 0 个断链
✅ 工具矩阵同步完成
✅ 知识图谱更新完成
```

---

## 2. Governance Auditor (治理审计员 v1.1)

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

# 运行完整审计
python .jcode/scripts/governance-auditor.py full
```

### 审计内容

- **Lint**: 代码风格检查 (ruff)
- **Format**: 格式检查 (ruff)
- **Typecheck**: 类型检查 (mypy)
- **Test**: 单元测试 (pytest)
- **Security**: 安全扫描 (bandit + pip-audit)
- **Validate Governance Docs**: 验证15个治理层文档格式完整性
- **Check AI-SDLC Compliance**: 检查 CI/CD、pre-commit 配置
- **Audit Hallucination Risks**: 扫描代码不安全模式和文档绝对化声明

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

### 验证内容

- **Frontmatter**: 检查 title、description、category、tags、difficulty 字段
- **标题格式**: 确保标题包含英文后缀
- **分类有效性**: 验证 category 在允许列表中
- **导航部分**: 确保存在 `## 导航` 或 `## Navigation`
- **相关文档**: 确保存在相关文档引用部分
- **索引引用**: 验证 GOVERNANCE.md、INDEX.md、CLAUDE.md 引用完整性

### 输出示例

```
📋 验证治理层文档格式完整性...
✅ 15 个治理文档验证通过

📑 验证治理层索引完整性...
✅ 所有索引引用完整
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

### 报告示例

```
==================================================
AI Developer Growth - 效率报告
==================================================
案例数量: 15
文档数量: 218
代码示例: 10
==================================================
```

---

## 5. Community Catalyst (社区催化剂)

管理社区案例、查看社区统计。

### 命令

```bash
# 查看可用
python .jcode/scripts/community-catalyst.py triage

# 验证社区提交的案例
python .jcode/scripts/community-catalyst.py validate

# 查看社区统计
python .jcode/scripts/community-catalyst.py stats
```

### 统计示例

```
📊 社区统计...
案例总数: 15
内部案例: 15
社区案例: 0
```

---

## 自动触发 (Hooks)

配置在 `.jcode/hooks.json`，以下事件自动触发相应 skill:

| 事件 | 触发的 Skill | 动作 |
|------|-------------|------|
| commit (docs/efficiency/ai-*.md) | governance-docs-validator | validate |
| commit (任何文件) | governance-auditor | lint |
| PR (任何文件) | governance-auditor | full |
| PR (GOVERNANCE.md/INDEX.md/CLAUDE.md) | governance-docs-validator | check-index |
| merge (任何文件) | knowledge-curator | update-moc |
| 每周一 9:00 | governance-auditor | full |
| 每周一 10:00 | knowledge-curator | scan |
| 每月1日 9:00 | workflow-optimizer | report |
| 每月15日 9:00 | governance-auditor | audit-hallucination-risks |

---

## 在 CI/CD 中使用

在 `.github/workflows/ci.yml` 中已集成:

```yaml
# 治理文档验证
governance-docs-check:
  name: Governance Docs Validation
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Validate governance docs
      run: python .jcode/scripts/governance-docs-validator.py check-index
    - name: Validate AI-SDLC compliance
      run: python .jcode/scripts/governance-auditor.py check-ai-sdlc-compliance
```

---

## 快速参考

### 开发新功能
```bash
python .jcode/scripts/governance-auditor.py lint
python .jcode/scripts/governance-auditor.py test
git add . && git commit -m "feat: 新功能"
```

### 添加治理文档
```bash
# 创建文档后
python .jcode/scripts/governance-docs-validator.py validate
python .jcode/scripts/governance-docs-validator.py sync-refs
```

### 发布前检查
```bash
python .jcode/scripts/governance-auditor.py full
python .jcode/scripts/governance-docs-validator.py full
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
