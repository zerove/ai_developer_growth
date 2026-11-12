---
title: "AI 代码审查专项清单 (AI Code Review Checklist)"
description: 针对 AI 生成代码的专项审查标准和检查项
category: 治理层
tags: ['AI', 'code-review', 'checklist', 'governance']
difficulty: 进阶
reading_time: 12 分钟
updated: 2026-07-22
---

# AI 代码审查专项清单 (AI Code Review Checklist)

> AI 生成的代码需要比人工代码更严格的审查。AI 的错误模式与人类不同。

---

## 1. 概述

AI 生成的代码具有独特的错误模式：**模式复制、过度简化、上下文误解本清单提供针对这些特有风险的专项审查检查项。

### 适用场景

- 所有 AI 生成或 AI 辅助修改的代码
- AI 自动补全的代码片段
- AI Agent 自主生成的模块
- AI 重构/迁移的代码

---

## 2. AI 特有审查项 (必查)

### 2.1 幻觉检测 (Hallucination Check)

| # | 检查项 | 检查方法 | 严重度 |
|---|--------|----------|--------|
| H1 | API 是否真实存在？ | 查文档/运行测试 | 🔴 高 |
| H2 | 函数参数是否正确？ | 查文档/类型检查 | 🔴 高 |
| H3 | 返回类型是否正确？ | 类型检查 + 测试 | 🔴 高 |
| H4 | 异常类型是否正确？ | 查文档 + 测试 | 🟡 中 |
| H5 | 库版本是否兼容？ | 依赖检查 | 🟡 中 |
| H6 | 配置项是否正确？ | 查文档 | 🟡 中 |

**检查方法**: 对 AI 生成的每个 API 调用，执行以下验证:
```bash
# 1. 类型检查 (捕获 API 幻觉)
mypy your_module.py
# 或
tsc --noEmit

# 2. 测试验证 (捕获逻辑幻觉)
pytest tests/ -v

# 3. 文档对比 (捕获参数幻觉)
# 对比 AI 生成的代码与官方文档
```

### 2.2 模式复制检测 (Pattern Replication)

| # | 检查项 | 检查方法 | 严重度 |
|---|--------|----------|--------|
| P1 | 是否复制了有漏洞的模式？ | 安全扫描 + 人工审查 | 🔴 高 |
| P2 | 是否复制了过时的模式？ | 对比最新文档 | 🟡 中 |
| P3 | 是否复制了不适用的模式？ | 人工审查 | 🟡 中 |
| P4 | 是否复制了项目中的反模式？ | Linter + 人工审查 | 🟡 中 |

**检查方法**:
```python
# AI 常见的模式复制问题:

# 1. 复制有漏洞的 SQL 拼接模式
# ❌ AI 可能生成:
query = f"SELECT * FROM users WHERE id = {user_id}"

# ✅ 应该是:
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))

# 2. 复制不安全的密码处理
# ❌ AI 可能生成:
password = hashlib.md5(password).hexdigest()

# ✅ 应该是:
password = bcrypt.hashpw(password, bcrypt.gensalt())
```

### 2.3 过度简化检测 (Oversimplification)

| # | 检查项 | 检查方法 | 严重度 |
|---|--------|----------|--------|
| S1 | 是否忽略了边界条件？ | 人工审查 | 🔴 高 |
| S2 | 是否忽略了错误处理？ | 人工审查 | 🔴 高 |
| S3 | 是否忽略了并发安全？ | 并发测试 | 🟡 中 |
| S4 | 是否忽略了资源释放？ | 代码审查 | 🟡 中 |
| S5 | 是否忽略了输入验证？ | 人工审查 | 🔴 高 |

**检查方法**: 对每个 AI 生成的函数，检查以下清单:
```markdown
## 函数审查清单

### 输入验证
- [ ] 空值/null 检查
- [ ] 类型检查
- [ ] 范围检查
- [ ] 长度限制
- [ ] 格式验证

### 错误处理
- [ ] 异常捕获
- [ ] 错误传播
- [ ] 资源清理
- [ ] 回滚逻辑
- [ ] 用户友好错误信息

### 边界条件
- [ ] 空集合处理
- [ ] 大数据量处理
- [ ] 并发访问
- [ ] 超时处理
- [ ] 重试逻辑
```

### 2.4 上下文误解检测 (Context Misunderstanding)

| # | 检查项 | 检查方法 | 严重度 |
|---|--------|----------|--------|
| C1 | 是否符合项目编码规范？ | Linter | 🟡 中 |
| C2 | 是否使用了正确的依赖？ | 依赖检查 | 🟡 中 |
| C3 | 是否遵循了项目架构？ | 人工审查 | 🟡 中 |
| C4 | 是否使用了正确的命名？ | 人工审查 | 🟢 低 |
| C5 | 是否保持了 API 一致性？ | 人工审查 | 🟡 中 |

---

## 3. 通用审查项 (标准审查)

### 3.1 代码质量

| # | 检查项 | 自动化 | 人工 | 严重度 |
|---|--------|--------|------|--------|
| Q1 | Linter 检查通过 | ✅ | - | 🔴 高 |
| Q2 | 类型检查通过 | ✅ | - | 🔴 高 |
| Q3 | 代码可读性 | - | ✅ | 🟡 中 |
| Q4 | 函数长度合理 (< 50 行) | ✅ | - | 🟡 中 |
| Q5 | 文件长度合理 (< 300 行) | ✅ | - | 🟡 中 |
| Q6 | 无重复代码 | ✅ | ✅ | 🟡 中 |
| Q7 | 无死代码 | ✅ | - | 🟢 低 |

### 3.2 安全性

|---|--------|--------|------|--------|
| SEC3 | 无 XSS 风险 | ✅ | ✅ | 🔴 高 |
| SEC4 | 输入验证完整 | - | ✅ | 🔴 高 |
| SEC5 | 输出编码正确 | - | ✅ | 🔴 高 |
| SEC6 | 认证/授权检查 | - | ✅ | 🔴 高 |
| SEC7 | 敏感数据脱敏 | - | ✅ | 🔴 高 |
| SEC8 | 依赖安全扫描 | ✅ | - | 🟡 中 |

### 3.3 测试

|---|--------|--------|------|--------|
| T1 | 单元测试通过 | ✅ | - | 🔴 高 |
| T2 | 集成测试通过 | ✅ | - | 🔴 高 |
| T3 | 测试覆盖率 ≥ 80% | ✅ | - | 🟡 中 |
| T4 | 边界条件已测试 | - | ✅ | 🟡 中 |
| T5 | 错误路径已测试 | - | ✅ | 🟡 中 |
| T6 | 无 flaky tests | ✅ | - | 🟡 中 |

---

## 4. AI 代码审查流程

```
  ├── 类型检查 → 修复类型错误
  ├── 安全扫描 → 修复安全问题
  ├── 幻觉检测 (H1-H6)
  ├── 模式复制检测 (P1-P4)
  ├── 过度简化检测 (S1-S5)
  └── 上下文误解检测 (C1-C5)

Step 3: 通用审查 (10 分钟)
  ├── 代码质量 (Q1-Q7)
  ├── 安全性 (SEC1-SEC8)
  └── 测试 (T1-T6)
  ├── 性能审查
  ├── 架构审查
  └── 业务逻辑审查
```

### 4.2 审查报告模板

```markdown
## AI 代码审查报告

**PR**: #123
**审查人**: @reviewer
**日期**: 2026-07-22
**AI 模型**: Claude 4

### 自动化检查结果
- Linter: ✅ 通过
- 类型检查: ✅ 通过
- 安全扫描: ⚠️ 1 warning
- 测试: ✅ 通过 (85% coverage)

### AI 专项检查结果
- 幻觉检测: ✅ 无幻觉
- 模式复制: ⚠️ 发现 1 个潜在问题
- 过度简化: ✅ 错误处理完整
### 通用检查结果
- 代码质量: ✅ 通过
- 安全性: ✅ 通过
- 测试: ✅ 通过

### 审查结论
✅ APPROVE (附带 1 个建议修改)

### 建议修改
1. Line 45: 将 `old_api()` 替换为 `new_api()`
```

---

## 5. AI 代码审查红线


| 情况 | 原因 | 处理 |
|------|------|------|
| 发现 API 幻觉 | 代码无法运行 | 阻断 + 修复 |
| 发现安全漏洞 | 安全风险 | 阻断 + 修复 |
### 5.2 建议修改的情况

| 情况 | 原因 | 处理 |
|------|------|------|
| 风格不一致 | 可读性 | 建议修改 |
| 缺少注释 | 可维护性 | 建议修改 |

---

## 📂 导航

- [AI 代码生成质量标准](ai-code-generation-quality.md) - 质量验证框架
- [代码审查指南](code-review-guide.md) - 通用审查指南
---

---

## 导航

**分类**: 治理层

**相关文档
- [[../GOVERNANCE|通用治理标准]]
- [[../GOVERNANCE|通用治理标准]]**:

- [[docs/efficiency/ai-code-generation-quality|代码质量]]
- [[docs/efficiency/ai-model-selection|模型选型]]
- [[docs/efficiency/ai-sdlc|SDLC]]
- [[docs/efficiency/ai-nondeterministic-testing|非确定性测试]]
- [[docs/efficiency/ai-hallucination-mitigation|幻觉缓解]]


## 相关案例

- **相关案例**: [api-design-implementation](../case-studies/api-design-implementation.md)

- **相关案例**: [legacy-system-refactoring](../case-studies/legacy-system-refactoring.md)

- **相关案例**: [ml-model-deployment](../case-studies/ml-model-deployment.md)

- **相关案例**: [microservice-architecture](../case-studies/microservice-architecture.md)

- **相关案例**: [api-monitoring](../case-studies/api-monitoring.md)

- **相关案例**: [aiops-automation](../case-studies/aiops-automation.md)

- **相关案例**: [realtime-data-processing](../case-studies/realtime-data-processing.md)

- **相关案例**: [api-doc-generation](../case-studies/api-doc-generation.md)

- **相关案例**: [production-debugging](../case-studies/production-debugging.md)

- **相关案例**: [legacy-refactoring](../case-studies/legacy-refactoring.md)

- **相关案例**: [code-review-system](../case-studies/code-review-system.md)

- **相关案例**: [security-audit](../case-studies/security-audit.md)

- **相关案例**: [technical-documentation](../case-studies/technical-documentation.md)

- **相关案例**: [data-pipeline](../case-studies/data-pipeline.md)

- **相关案例**: [governance-self-audit](../case-studies/governance-self-audit.md)

- **相关案例**: [automated-testing-platform](../case-studies/automated-testing-platform.md)

- **相关案例**: [data-migration](../case-studies/data-migration.md)

- **相关案例**: [ai-context-sync-development](../case-studies/ai-context-sync-development.md)

- **相关案例**: [database-performance-optimization](../case-studies/database-performance-optimization.md)

- **相关案例**: [mobile-app-development](../case-studies/mobile-app-development.md)

- **相关案例**: [api-design](../case-studies/api-design.md)

- **相关案例**: [ai-task-prioritizer](../case-studies/ai-task-prioritizer.md)

- **相关案例**: [unit-testing](../case-studies/unit-testing.md)

- **相关案例**: [devops-pipeline](../case-studies/devops-pipeline.md)

- **相关案例**: [database-migration](../case-studies/database-migration.md)

- **相关案例**: [adg-dogfooding-search-pipeline](../case-studies/adg-dogfooding-search-pipeline.md)

- **相关案例**: [cli-tool-development](../case-studies/cli-tool-development.md)

- **相关案例**: [web-scraping-tool](../case-studies/web-scraping-tool.md)

- **相关案例**: [frontend-performance-optimization](../case-studies/frontend-performance-optimization.md)

- **相关案例**: [intelligent-customer-service](../case-studies/intelligent-customer-service.md)

- **相关案例**: [security-vulnerability-fix](../case-studies/security-vulnerability-fix.md)
