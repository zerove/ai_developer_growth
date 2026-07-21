---
title: Authentication Governance Rules
description: > 适用于认证模式的 AI Agent 开发规范。
category: 治理层
tags: ['测试', 'AI', 'API', 'Python']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# Authentication Governance Rules

> 适用于认证模式的 AI Agent 开发规范。

---

## 1. JWT 认证

### Token 结构

```json
// ✅ 正确: JWT 结构
{
  "header": {
    "alg": "RS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "user123",
    "iss": "https://auth.example.com",
    "aud": "https://api.example.com",
    "exp": 1704067200,
    "iat": 1704063600,
    "scope": "read write"
  }
}
```

### Token 生成

```python
# ✅ 正确: 使用 RS256
import jwt
from datetime import datetime, timedelta

def generate_token(user_id: str) -> str:
    payload = {
        'sub': user_id,
        'iss': 'https://auth.example.com',
        'aud': 'https://api.example.com',
        'exp': datetime.utcnow() + timedelta(hours=1),
        'iat': datetime.utcnow(),
        'scope': 'read write'
    }
    
    return jwt.encode(payload, private_key, algorithm='RS256')

# ❌ 禁止: 使用 HS256
return jwt.encode(payload, secret_key, algorithm='HS256')  # 不安全
```

### Token 验证

```python
# ✅ 正确: 完整的验证
def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            issuer='https://auth.example.com',
            audience='https://api.example.com'
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError('Token expired')
    except jwt.InvalidTokenError:
        raise AuthError('Invalid token')
```

---

## 2. OAuth 2.0

### 授权码流程

```
# ✅ 正确: 授权码流程
1. 客户端重定向到授权服务器
   GET /authorize?
     response_type=code&
     client_id=client123&
     redirect_uri=https://app.example.com/callback&
     scope=openid profile email&
     state=xyz123

2. 用户授权后，授权服务器返回授权码
   GET /callback?code=auth_code_xyz&state=xyz123

3. 客户端用授权码换取 Token
   POST /token
   Content-Type: application/x-www-form-urlencoded
   
   grant_type=authorization_code&
   code=auth_code_xyz&
   redirect_uri=https://app.example.com/callback&
   client_id=client123&
   client_secret=secret123
```

### PKCE 扩展

```
# ✅ 正确: 使用 PKCE (移动端/SPA)
1. 生成 code_verifier 和 code_challenge
   code_verifier = random_string(43)
   code_challenge = base64(sha256(code_verifier))

2. 请求授权码时包含 code_challenge
   GET /authorize?
     response_type=code&
     code_challenge=xxx&
     code_challenge_method=S256

3. 换取 Token 时包含 code_verifier
   POST /token
   code_verifier=xxx
```

---

## 3. Session 认证

### Session 存储

```python
# ✅ 正确: 服务端 Session
from flask import session

@app.route('/login', methods=['POST'])
def login():
    user = authenticate(request.json)
    if user:
        session['user_id'] = user.id
        session.permanent = True
        return jsonify({'success': True})
    
    return jsonify({'error': 'Invalid credentials'}), 401

# ✅ 正确: 使用安全 Cookie
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

### Session 失效

```python
# ✅ 正确: 主动失效
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

# ✅ 正确: 被动失效 (超时)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
```

---

## 4. 密码安全

### 密码哈希

```python
# ✅ 正确: 使用 bcrypt
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ❌ 禁止: 使用 MD5/SHA1
import hashlib
hashed = hashlib.md5(password.encode()).hexdigest()  # 不安全
```

### 密码策略

```python
# ✅ 正确: 密码复杂度要求
def validate_password(password: str) -> bool:
    if len(password) < 12:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    if not re.search(r'[!@#$%^&*]', password):
        return False
    return True
```

---

## 5. 多因素认证 (MFA)

### TOTP 实现

```python
# ✅ 正确: TOTP 实现
import pyotp

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def generate_totp_url(secret: str, email: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(email, issuer_name='MyApp')

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
```

### 恢复码

```python
# ✅ 正确: 生成恢复码
import secrets

def generate_recovery_codes() -> list[str]:
    return [secrets.token_hex(8) for _ in range(10)]
```

---

## 6. API 密钥管理

### 密钥生成

```python
# ✅ 正确: 生成安全的 API 密钥
import secrets

def generate_api_key() -> str:
    return f"sk_{secrets.token_hex(32)}"

# ❌ 禁止: 使用可预测的密钥
api_key = f"api_{user_id}_{timestamp}"  # 可预测
```

### 密钥轮换

```python
# ✅ 正确: 支持密钥轮换
class APIKey:
    def __init__(self, key: str, expires_at: datetime):
        self.key = key
        self.expires_at = expires_at
        self.is_active = True
    
    def is_valid(self) -> bool:
        return self.is_active and datetime.utcnow() < self.expires_at
    
    def revoke(self):
        self.is_active = False
```

---

## 7. 测试规范

### 认证测试

```python
import pytest

@pytest.mark.asyncio
async def test_login_success():
    response = await client.post('/login', json={
        'email': 'test@example.com',
        'password': 'correct_password'
    })
    assert response.status_code == 200
    assert 'token' in response.json()

@pytest.mark.asyncio
async def test_login_failure():
    response = await client.post('/login', json={
        'email': 'test@example.com',
        'password': 'wrong_password'
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_protected_endpoint():
    token = generate_token('user123')
    response = await client.get(
        '/protected',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200
```

---

## 8. 质量检查清单

### JWT

- [ ] 使用 RS256 算法
- [ ] 设置合理的过期时间
- [ ] 验证 issuer 和 audience
- [ ] 实现 Token 刷新

### 密码

- [ ] 使用 bcrypt/argon2
- [ ] 密码复杂度要求
- [ ] 防止暴力破解
- [ ] 密码历史检查

### 安全

- [ ] HTTPS 强制
- [ ] Cookie 安全标志
- [ ] 速率限制
- [ ] 审计日志

---

*本规范随安全最佳实践演进持续更新。最后更新: 2026-07-17*
