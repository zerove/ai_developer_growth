---
title: OWASP Top 10 Governance Rules
description: > 适用于 OWASP Top 10 安全风险的 AI Agent 开发规范。
category: 治理层
tags: ['AI', 'Python', 'SQL', '安全', '部署']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# OWASP Top 10 Governance Rules

> 适用于 OWASP Top 10 安全风险的 AI Agent 开发规范。

---

## 1. A01:2021 - Broken Access Control

### 前端强制

```javascript
// ❌ 禁止: 仅前端检查
if (user.role === 'admin') {
  showAdminPanel();
}

// ✅ 正确: 后端强制检查
@router.get('/admin')
@require_role('admin')
async def admin_endpoint():
    # 后端强制验证权限
    pass
```

### 对象级授权

```python
# ❌ 禁止: 水平越权
@router.get('/users/{id}')
async def get_user(id: str):
    user = await db.find_user(id)  # 未检查当前用户是否有权访问
    return user

# ✅ 正确: 对象级授权
@router.get('/users/{id}')
async def get_user(id: str, current_user: User = Depends(get_current_user)):
    if current_user.id != id and current_user.role != 'admin':
        raise HTTPException(403, 'Forbidden')
    
    user = await db.find_user(id)
    return user
```

---

## 2. A02:2021 - Cryptographic Failures

### 数据加密

```python
# ✅ 正确: 使用 AES-256-GCM
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_data(data: bytes, key: bytes) -> bytes:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    return nonce + aesgcm.encrypt(nonce, data, None)

def decrypt_data(encrypted: bytes, key: bytes) -> bytes:
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)

# ❌ 禁止: 使用 ECB 模式
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
cipher = Cipher(algorithms.AES(key), modes.ECB())  # 不安全
```

### 传输加密

```python
# ✅ 正确: 强制 HTTPS
@app.before_request
def force_https():
    if not request.is_secure:
        url = request.url.replace('http://', 'https://')
        return redirect(url, code=301)

# ❌ 禁止: 允许 HTTP
ALLOWED_HOSTS = ['*']  # 不安全
```

---

## 3. A03:2021 - Injection

### SQL 注入防护

```python
# ❌ 禁止: 字符串拼接
query = f"SELECT * FROM users WHERE id = '{user_id}'"

# ✅ 正确: 参数化查询
query = "SELECT * FROM users WHERE id = %s"
cursor.execute(query, (user_id,))
```

### XSS 防护

```python
# ❌ 禁止: 直接输出
return f"<div>{user_input}</div>"

# ✅ 正确: 转义输出
from markupsafe import escape
return f"<div>{escape(user_input)}</div>"
```

### 命令注入防护

```python
# ❌ 禁止: 使用 os.system
os.system(f"ping {host}")

# ✅ 正确: 使用 subprocess.run
import subprocess
subprocess.run(['ping', host], capture_output=True)
```

---

## 4. A04:2021 - Insecure Design

### 威胁建模

```markdown
# ✅ 正确: 记录威胁模型
## 支付流程威胁分析

### 威胁 1: 金额篡改
- 风险: 高
- 缓解: 服务端验证金额，不信任客户端输入

### 威胁 2: 重复支付
- 风险: 中
- 缓解: 幂等键 + 事务
```

### 最小权限

```python
# ✅ 正确: 最小权限原则
# 数据库用户只授予必要权限
GRANT SELECT, INSERT, UPDATE ON orders TO app_user;
# 不授予 DROP, ALTER 权限
```

---

## 5. A05:2021 - Security Misconfiguration

### 安全头配置

```python
# ✅ 正确: 设置安全头
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response
```

### 错误处理

```python
# ❌ 禁止: 暴露堆栈信息
@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': str(error)}), 500  # 不安全

# ✅ 正确: 隐藏敏感信息
@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'Internal error: {error}')
    return jsonify({'error': 'Internal server error'}), 500
```

---

## 6. A06:2021 - Vulnerable and Outdated Components

### 依赖扫描

```bash
# ✅ 正确: 定期扫描依赖
npm audit
pip audit
bundle audit

# ✅ 正确: 使用 Dependabot
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
```

---

## 7. A07:2021 - Identification and Authentication Failures

### 密码存储

```python
# ✅ 正确: 使用 bcrypt
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

# ❌ 禁止: 明文存储
password_hash = password  # 不安全
```

### 会话管理

```python
# ✅ 正确: 会话安全
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
```

---

## 8. A08:2021 - Software and Data Integrity Failures

### 依赖验证

```bash
# ✅ 正确: 使用 lockfile
npm ci  # 使用 package-lock.json
pip install -r requirements.txt --require-hashes
```

### CI/CD 安全

```yaml
# ✅ 正确: 保护 CI/CD 流程
jobs:
  deploy:
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Verify commit signature
        run: git verify-commit HEAD
```

---

## 9. A09:2021 - Security Logging and Monitoring Failures

### 安全日志

```python
# ✅ 正确: 记录安全事件
import logging

security_logger = logging.getLogger('security')

def log_login_attempt(email: str, success: bool, ip: str):
    security_logger.info(
        f'Login attempt: email={email}, success={success}, ip={ip}'
    )

def log_permission_denied(user_id: str, resource: str):
    security_logger.warning(
        f'Permission denied: user={user_id}, resource={resource}'
    )
```

### 敏感数据脱敏

```python
# ❌ 禁止: 日志中包含敏感信息
logger.info(f'User login: {email}, password: {password}')

# ✅ 正确: 脱敏处理
logger.info(f'User login: {email}, password: ***')
```

---

## 10. A10:2021 - Server-Side Request Forgery (SSRF)

### URL 验证

```python
# ❌ 禁止: 未验证的 URL
async def fetch_url(url: str):
    response = await httpx.get(url)  # 可能访问内部服务

# ✅ 正确: 验证 URL
from urllib.parse import urlparse

def is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
        return False
    if parsed.scheme not in ['https']:
        return False
    return True

async def fetch_url(url: str):
    if not is_allowed_url(url):
        raise ValueError('URL not allowed')
    response = await httpx.get(url)
    return response
```

---

## 11. 质量检查清单

### 访问控制

- [ ] 后端强制权限检查
- [ ] 对象级授权验证
- [ ] 最小权限原则

### 加密

- [ ] 强制 HTTPS
- [ ] 安全的加密算法
- [ ] 密钥管理

### 注入防护

- [ ] 参数化查询
- [ ] 输入验证
- [ ] 输出编码

### 日志

- [ ] 安全事件记录
- [ ] 敏感数据脱敏
- [ ] 监控告警

---

*本规范随 OWASP Top 10 演进持续更新。最后更新: 2026-07-17*
