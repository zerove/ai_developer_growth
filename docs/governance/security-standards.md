---
title: 安全开发标准
description: 安全编码和应用安全标准
category: 治理层
tags: [安全, DevSecOps, 合规]
difficulty: 进阶
reading_time: 10 分钟
updated: 2026-07-21
---

# 安全开发标准

## 核心原则

安全开发 = 左移安全 + 全程防护 + 持续监控

## 安全编码

### 1. 输入验证

**原则:**
- 验证所有输入
- 白名单优于黑名单
- 长度和类型限制

**示例:**
```python
from pydantic import BaseModel, Field, EmailStr


class UserInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(ge=0, le=150)
```

### 2. 参数化查询

**原则:**
- 永远不要拼接 SQL
- 使用参数化查询
- ORM 优先

**示例:**
```python
# 安全
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# 危险
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### 3. 认证授权

**原则:**
- 最小权限原则
- 定期审查权限
- 多因素认证

**示例:**
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

## 数据安全

### 1. 加密存储

```python
from cryptography.fernet import Fernet

# 加密
key = Fernet.generate_key()
f = Fernet(key)
encrypted = f.encrypt(b"sensitive data")

# 解密
decrypted = f.decrypt(encrypted)
```

### 2. 密钥管理

**原则:**
- 不要硬编码密钥
- 使用环境变量
- 使用密钥管理服务

**示例:**
```python
import os

# 使用环境变量
api_key = os.getenv("API_KEY")
```

### 3. 日志脱敏

```python
def mask_email(email: str) -> str:
    """邮箱脱敏"""
    local, domain = email.split("@")
    masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"
```

## 依赖安全

### 1. 依赖扫描

```bash
# Python
pip audit

# JavaScript
npm audit
```

### 2. 版本锁定

```
提交锁文件
定期更新
测试后升级
```

### 3. 漏洞处理

```
监控公告
评估影响
及时修复
```

## 安全测试

### 1. 静态分析

```
Bandit: Python 安全扫描
Semgrep: 多语言安全规则
```

### 2. 动态分析

```
OWASP ZAP: Web 安全扫描
Burp Suite: 专业安全测试
```

### 3. 依赖审计

```
Snyk: 依赖漏洞扫描
Dependabot: GitHub 自动更新
```

## 应急响应

### 1. 漏洞响应

```
发现 → 报告 → 修复 → 验证 → 复盘
```

### 2. 事件响应

```
检测 → 响应 → 恢复 → 复盘
```

### 3. 通知机制

```
内部通知
用户通知
监管报告
```

---

*最后更新: 2026-07-21*
