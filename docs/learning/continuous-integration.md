---
title: 持续集成实践
description: CI/CD 的原理和最佳实践
category: 学习层
tags: [CI/CD, DevOps, 自动化]
difficulty: 进阶
reading_time: 12 分钟
updated: 2026-07-21
---

# 持续集成实践

## 核心原则

CI = 频繁集成 + 自动化测试 + 快速反馈

## CI/CD 流程

```
代码提交 → 自动构建 → 自动测试 → 代码审查 → 部署
```

## CI 配置

### GitHub Actions 示例

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run tests
        run: pytest
      
      - name: Run linter
        run: ruff check .
```

## CI 最佳实践

### 1. 快速反馈

**原则:**
- 构建时间 < 10 分钟
- 测试时间 < 5 分钟
- 及时通知结果

**优化方法:**
- 并行执行
- 缓存依赖
- 增量构建

### 2. 自动化测试

**测试层级:**
```
单元测试 → 集成测试 → E2E 测试
```

**覆盖率要求:**
- 单元测试: 80%+
- 集成测试: 60%+
- E2E 测试: 核心流程

### 3. 代码质量

**检查项:**
- 代码风格 (Lint)
- 类型检查 (Type Check)
- 安全扫描 (Security Scan)

**工具:**
```yaml
- name: Lint
  run: ruff check .

- name: Type check
  run: mypy .

- name: Security scan
  run: bandit -r .
```

## CD 配置

### 部署流程

```yaml
deploy:
  needs: test
  runs-on: ubuntu-latest
  if: github.ref == 'refs/heads/main'
  steps:
    - name: Deploy to production
      run: |
        echo "Deploying..."
        # 部署脚本
```

### 环境管理

**环境矩阵:**
```yaml
strategy:
  matrix:
    environment: [staging, production]
```

## 监控告警

### CI 监控

**监控指标:**
- 构建成功率
- 构建时间
- 测试通过率

### 告警规则

```yaml
- name: Notify on failure
  if: failure()
  uses: actions/github-script@v6
  with:
    script: |
      github.rest.issues.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        title: 'Build Failed',
        body: 'Build failed on ${{ github.sha }}'
      })
```

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 构建太慢 | 未并行执行 | 并行测试 |
| 测试不稳定 | 环境依赖 | Mock 外部服务 |
| 部署失败 | 配置错误 | 环境隔离 |

## AI 辅助 CI/CD

```markdown
请帮我优化 CI/CD 流程:

1. 分析当前配置
2. 识别瓶颈
3. 建议优化方案
4. 生成配置文件
```

## 案例: CI/CD 实践

### 背景
- 项目: Python Web 应用
- 目标: 自动化测试和部署

### 配置
```yaml
name: CI/CD

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest
      - name: Deploy
        if: github.ref == 'refs/heads/main'
        run: ./deploy.sh
```

### 结果
- 构建时间: 5 分钟
- 测试覆盖率: 85%
- 部署频率: 每天

---

*最后更新: 2026-07-21*
