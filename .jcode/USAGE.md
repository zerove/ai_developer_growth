# Jcode Skills 使用指南

本文档介绍如何使用 `.jcode/scripts/` 下的 4 个可执行脚本。

## 概览

| Skill | 功能 | 命令 |
|-------|------|------|
| knowledge-curator | 知识库维护 | `python .jcode/scripts/knowledge-curator.py <action>` |
| governance-auditor | 治理审计 | `python .jcode/scripts/governance-auditor.py <action>` |
| workflow-optimizer | 工作流优化 | `python .jcode/scripts/workflow-optimizer.py <action>` |
| community-catalyst | 社区催化 | `python .jcode/scripts/community-catalyst.py <action>` |

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
python .jcode/scripts/knowledge-catalyst.py validate
```

### 输出示例

```
✅ 案例扫描完成: 15 个案例
✅ 文档审计完成: 0 个断链
```

---

## 2. Governance Auditor (治理审计员)

自动化审计代码质量、安全漏洞、治理标准合规性。

### 命令

```bash
# 运行 ruff lint 检查
python .jcode/scripts/governance-auditor.py lint

# 运行 pytest 测试
python .jcode/scripts/governance-auditor.py test

# 运行完整审计 (lint + test + security)
python .jcode/scripts/governance-auditor.py audit
```

### 审计内容

- **Lint**: 代码风格检查 (ruff)
- **Test**: 单元测试 (pytest)
- **Security**: 安全扫描 (bandit + pip-audit)

---

## 3. Workflow Optimizer (工作流优化师)

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
文档数量: 127
代码示例: 6
==================================================
```

---

## 4. Community Catalyst (社区催化剂)

管理贡献流程、验证社区案例、查看社区统计。

### 命令

```bash
# 查看可用标签和分流指南
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

| 事件 | 触发的 Skill |
|------|-------------|
| commit (case-studies/*.md) | knowledge-curator scan |
| commit (tools/scripts/*.py) | governance-auditor lint |
| push (master) | governance-auditor audit |

---

## 在 CI/CD 中使用

在 `.github/workflows/ci.yml` 中已集成:

```yaml
- name: Validate case studies
  run: python tools/scripts/validate_case_study.py --all

- name: Link audit
  run: python tools/scripts/link_auditor.py .
```

---

## 故障排除

### 常见问题

1. **模块未找到**: 确保在项目根目录运行
2. **权限错误**: 确保脚本有执行权限 (`chmod +x`)
3. **依赖缺失**: 运行 `pip install -r requirements-dev.txt`
