---
title: AI 辅助安全开发
description: 使用 AI 工具提升应用安全性
category: 效率层
tags: [AI, 安全, DevSecOps]
difficulty: 进阶
reading_time: 12 分钟
updated: 2026-07-21
---

# AI 辅助安全开发

## 核心原则

安全开发 = 左移安全 + 自动化检测 + 持续监控

## 安全实践

### 1. 代码安全

**常见漏洞:**
```
SQL 注入
XSS 攻击
CSRF 攻击
命令注入
```

### 2. 依赖安全

**工具:**
```
npm audit: JavaScript 依赖检查
safety: Python 依赖检查
Snyk: 多语言依赖扫描
```

### 3. 容器安全

**实践:**
```
镜像扫描 → 最小权限 → 运行时保护
```

## Prompt 技巧

### 1. 安全审查

```markdown
请审查代码安全性:
- 输入验证
- SQL 注入
- XSS 风险
- 认证授权
```

### 2. 安全修复

```markdown
请修复安全漏洞:
- 提供漏洞详情
- 生成修复代码
- 解释修复逻辑
```

### 3. 安全配置

```markdown
请生成安全配置:
- HTTPS 配置
- CORS 配置
- CSP 策略
```

## 安全工具

### 1. SAST (静态分析)

```
SonarQube: 代码质量 + 安全
Bandit: Python 安全扫描
ESLint Security: JavaScript 安全
```

### 2. DAST (动态分析)

```
OWASP ZAP: Web 应用安全扫描
Burp Suite: 专业安全测试
```

### 3. IAST (交互式)

```
结合 SAST 和 DAST
运行时安全分析
```

## 安全编码

### 1. 输入验证

```python
from pydantic import BaseModel, EmailStr


class UserInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
```

### 2. 参数化查询

```python
# 安全
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# 危险
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### 3. 认证授权

```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401)
    return user
```

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 注入攻击 | 未验证输入 | 参数化查询 |
| 权限绕过 | 未授权检查 | 鉴权中间件 |
| 数据泄露 | 未加密 | 加密存储 |

## 效率提升

### 1. 自动化扫描

集成安全扫描到 CI/CD。

### 2. 安全培训

团队安全意识培训。

### 3. 应急响应

建立安全事件响应流程。

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

- **相关案例**: [security-audit](../case-studies/security-audit.md)

- **相关案例**: [security-vulnerability-fix](../case-studies/security-vulnerability-fix.md)

