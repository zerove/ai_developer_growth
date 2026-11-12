---
title: AI 辅助 API 设计
description: 使用 AI 工具设计 RESTful API
category: 效率层
tags: [AI, API, RESTful]
difficulty: 进阶
reading_time: 10 分钟
updated: 2026-07-21
---

# AI 辅助 API 设计

## 核心原则

好 API = 清晰资源 + 统一规范 + 完整文档

## 设计规范

### 1. RESTful 资源设计

**原则:**
- 资源名词复数
- 使用 HTTP 方法表示操作
- 层级关系清晰

**示例:**
```
GET    /api/users          # 获取用户列表
POST   /api/users          # 创建用户
GET    /api/users/{id}     # 获取用户
PUT    /api/users/{id}     # 更新用户
DELETE /api/users/{id}     # 删除用户

GET    /api/users/{id}/orders  # 用户的订单
```

### 2. 请求/响应设计

**统一响应格式:**
```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

**错误响应:**
```json
{
  "code": 400,
  "message": "参数错误",
  "errors": [
    {"field": "email", "message": "格式不正确"}
  ]
}
```

### 3. 分页设计

```
GET /api/users?page=1&per_page=20
GET /api/users?offset=0&limit=20
```

**响应:**
```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

## Prompt 技巧

### 1. API 设计

```markdown
请设计用户管理 API:
- 注册、登录、信息管理
- JWT 认证
- RESTful 规范
```

### 2. 文档生成

```markdown
请生成 OpenAPI 文档:
- 完整端点定义
- 请求/响应示例
- 错误码说明
```

### 3. SDK 生成

```markdown
请根据 OpenAPI 生成 Python SDK:
- 类型提示
- 异步支持
- 错误处理
```

## 最佳实践

### 1. 版本控制

```
/api/v1/users
/api/v2/users
```

### 2. 认证授权

```
Bearer Token
OAuth 2.0
API Key
```

### 3. 限流设计

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1620000000
```

## 效率工具

### 1. Swagger/OpenAPI

```yaml
openapi: 3.0.0
info:
  title: User API
  version: 1.0.0
paths:
  /users:
    get:
      summary: 获取用户列表
      responses:
        '200':
          description: 成功
```

### 2. Postman

导出 OpenAPI 规范，生成集合。

### 3. 自动化测试

```python
import requests


def test_create_user():
    response = requests.post("http://localhost:8000/api/users", json={"name": "test", "email": "test@example.com"})
    assert response.status_code == 201
```

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 接口混乱 | 缺少规范 | 制定 API 规范 |
| 文档过时 | 手动维护 | 自动生成 |
| 版本冲突 | 缺少版本控制 | URL 版本管理 |

## 效率提升

### 1. 规范化

制定团队 API 规范，统一风格。

### 2. 自动化

代码即文档，自动生成 OpenAPI。

### 3. 测试化

API 测试自动化，持续验证。

---

*最后更新: 2026-07-21*

---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]


## 相关案例

- **相关案例**: [api-design-implementation](../case-studies/api-design-implementation.md)

- **相关案例**: [legacy-system-refactoring](../case-studies/legacy-system-refactoring.md)

- **相关案例**: [ml-model-deployment](../case-studies/ml-model-deployment.md)

- **相关案例**: [microservice-architecture](../case-studies/microservice-architecture.md)

- **相关案例**: [api-monitoring](../case-studies/api-monitoring.md)

- **相关案例**: [aiops-automation](../case-studies/aiops-automation.md)

- **相关案例**: [ai-native-coverage-governance](../case-studies/ai-native-coverage-governance.md)

- **相关案例**: [realtime-data-processing](../case-studies/realtime-data-processing.md)

- **相关案例**: [api-doc-generation](../case-studies/api-doc-generation.md)

- **相关案例**: [production-debugging](../case-studies/production-debugging.md)

- **相关案例**: [legacy-refactoring](../case-studies/legacy-refactoring.md)

- **相关案例**: [code-review-system](../case-studies/code-review-system.md)

- **相关案例**: [security-audit](../case-studies/security-audit.md)

- **相关案例**: [technical-documentation](../case-studies/technical-documentation.md)

- **相关案例**: [data-pipeline](../case-studies/data-pipeline.md)

- **相关案例**: [automated-testing-platform](../case-studies/automated-testing-platform.md)

- **相关案例**: [data-migration](../case-studies/data-migration.md)

- **相关案例**: [ai-context-sync-development](../case-studies/ai-context-sync-development.md)

- **相关案例**: [database-performance-optimization](../case-studies/database-performance-optimization.md)

- **相关案例**: [mobile-app-development](../case-studies/mobile-app-development.md)

- **相关案例**: [ai-task-prioritizer](../case-studies/ai-task-prioritizer.md)

- **相关案例**: [unit-testing](../case-studies/unit-testing.md)

- **相关案例**: [devops-pipeline](../case-studies/devops-pipeline.md)

- **相关案例**: [database-migration](../case-studies/database-migration.md)

- **相关案例**: [adg-dogfooding-search-pipeline](../case-studies/adg-dogfooding-search-pipeline.md)

- **相关案例**: [cli-tool-development](../case-studies/cli-tool-development.md)

- **相关案例**: [web-scraping-tool](../case-studies/web-scraping-tool.md)

- **相关案例**: [code-review](../case-studies/code-review.md)

- **相关案例**: [frontend-performance-optimization](../case-studies/frontend-performance-optimization.md)

- **相关案例**: [intelligent-customer-service](../case-studies/intelligent-customer-service.md)

- **相关案例**: [security-vulnerability-fix](../case-studies/security-vulnerability-fix.md)

- **相关案例**: [api-design](../case-studies/api-design.md)
