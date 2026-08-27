---
title: AI 代码审查指南 (Code Review Guide)
description: > AI 生成代码的审查清单与最佳实践。
category: 效率层
tags: ['AI', 'API', '测试', '安全', '性能']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# AI 代码审查指南 (Code Review Guide)

> AI 生成代码的审查清单与最佳实践。

---

## 1. 审查原则

**AI 代码审查 ≠ 信任 AI**，而是**验证 AI 输出**。

核心理念：
- AI 生成的代码必须经过人工审查
- 关键路径代码需要更严格的审查
- 审查是为了理解，而非批准

---

## 2. 审查清单

### 2.1 功能正确性

- [ ] 代码是否实现了预期功能？
- [ ] 边界情况是否处理？
- [ ] 错误处理是否完善？
- [ ] 业务逻辑是否正确？

### 2.2 代码质量

- [ ] 代码是否可读？
- [ ] 命名是否清晰？
- [ ] 函数是否职责单一？
- [ ] 是否有重复代码？

### 2.3 安全性

- [ ] 是否有安全漏洞？
- [ ] 输入是否验证？
- [ ] 敏感信息是否保护？
- [ ] 权限检查是否完整？

### 2.4 性能

- [ ] 是否有性能问题？
- [ ] 数据库查询是否优化？
- [ ] 内存使用是否合理？
- [ ] 是否有 N+1 查询？

### 2.5 可维护性

- [ ] 代码是否易于修改？
- [ ] 是否有文档注释？
- [ ] 是否遵循项目规范？
- [ ] 测试是否完整？

---

## 3. 审查流程

```
提交 PR → 自动检查 → 人工审查 → 反馈 → 修正 → 合并
    ↓           ↓          ↓       ↓      ↓      ↓
  AI 生成   Lint/Test   审查者   讨论   修复   CI 通过
```

### 3.1 自动检查

```bash
# 提交前自动检查
npm run lint          # 代码风格
npm run type-check    # 类型检查
npm test              # 单元测试
npm run build         # 构建检查
```

### 3.2 人工审查重点

**高优先级**:
- 安全相关代码
- 核心业务逻辑
- 数据库操作
- API 接口

**中优先级**:
- 性能关键代码
- 复杂算法
- 状态管理

**低优先级**:
- 简单工具函数
- 文档更新
- 测试代码

---

## 4. AI 审查辅助

### 4.1 使用 AI 审查工具

```bash
# CodeRabbit - AI PR 审查
# 配置 .coderabbit.yaml
review:
  request_changes_workflow: true
  path_instructions:
    - path: "src/**"
      instructions: "Focus on security and performance"
```

### 4.2 AI 审查 Prompt

```
审查这段代码，关注：
1. 安全漏洞
2. 性能问题
3. 代码规范
4. 边界情况

提供具体的改进建议。
```

---

## 5. 审查反馈模板

```markdown
## 审查结果

### 优点
- [具体优点]

### 需要修改
- [具体问题 + 建议]

### 建议
- [可选改进]
```

---

**📂 导航**
- [[../MOC|⬅️ 返回知识地图]]
- **相关**: [[efficiency/anti-patterns|反模式]] | [[efficiency/ai-security-review|安全审查]]
---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]
