---
title: 通用治理框架
description: 可复用的 AI 时代项目治理标准和工具
category: 效率层
tags: ['AI', 'Python', 'governance', 'framework']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# 通用治理框架

> 任何项目可直接复制使用的治理标准。

---

## 核心理念

治理框架 = 质量门禁 + 自动化检查 + 渐进式采用。

**设计原则**:
1. **最小化**: 只规定必须的，不强制可选的
2. **可渐进**: 从 L0 到 L3 逐步采用
3. **自动化**: 所有检查都有脚本支持
4. **语言无关**: 适用于任何编程语言

---

## 治理等级

### L0: 基础 (任何项目都应有)
- [x] README.md
- [x] LICENSE
- [x] .gitignore
- [x] 基础 CI (lint + test)

### L1: 标准 (团队项目)
- [x] 代码规范 (linter/formatter)
- [x] 测试覆盖率 ≥70%
- [x] Code Review 流程
- [x] 分支策略

### L2: 专业 (开源/产品)
- [x] 类型检查 (mypy/pyright)
- [x] 安全扫描
- [x] ADR 记录
- [x] 贡献指南

### L3: 卓越 (大型项目)
- [x] 混沌工程
- [x] 性能基线
- [x] 合规审计
- [x] 架构评审

---

## 质量门禁清单

### 代码质量
```yaml
门禁:
  - ruff check (lint)
  - ruff format (format)
  - mypy (type check)
  - pytest --cov≥70% (test)
```

### 安全质量
```yaml
门禁:
  - bandit (安全扫描)
  - pip-audit (依赖审计)
  - secret-scan (密钥检测)
```

### 文档质量
```yaml
门禁:
  - link-audit (断链检测)
  - metadata-check (元数据验证)
  - case-study-validation (案例验证)
```

---

## 快速开始

```bash
# 1. 复制治理文件到你的项目
cp -r ai-dev-framework/.ai-framework/ your-project/

# 2. 运行初始化
python .ai-framework/jcode_init.py

# 3. 选择治理等级
# 按照提示选择 L0-L3
```

---

## 工具清单

| 工具 | 用途 | 集成方式 |
|------|------|----------|
| ruff | Python lint/format | pre-commit |
| mypy | 类型检查 | pre-commit |
| pytest | 测试 | CI |
| bandit | 安全扫描 | CI |
| linkinator | 断链检测 | CI |

---

## 相关资源

- [[../../GOVERNANCE|治理标准]]
- [[../../GOVERNANCE|通用框架]]
- [[../../agents/governance-auditor|审计 Agent]]

---

*Last Updated: 2026-07-21*

---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]
