# 安全加固指南 (Security Hardening Guide)

> 全面的安全编码实践和加固标准。

---

## 1. 安全编码原则

### 1.1 核心原则

```yaml
security_principles:
  - 最小权限: 只授予必要的权限
  - 纵深防御: 多层安全控制
  - 安全默认: 默认配置应该是安全的
  - 失败安全: 错误时拒绝访问，不是允许
  - 纵深防御: 多层安全控制
```

### 1.2 安全开发生命周期

```
1. 需求阶段: 识别安全需求
2. 设计阶段: 威胁建模
3. 实现阶段: 安全编码
4. 测试阶段: 安全测试
5. 部署阶段: 安全配置
6. 运维阶段: 监控响应
```

---

## 2. 输入验证

### 2.1 验证原则

```yaml
input_validation:
  - 所有外部输入必须验证
  - 在服务器端验证（客户端可绕过）
  - 使用白名单，不用黑名单
  - 验证数据类型、长度、范围、格式
  - 规范化后再验证
```

### 2.2 验证规则

```yaml
validation_rules:
  email:
    pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
    max_length: 254
  url:
    pattern: "^https?://[^\\s/$.?#].[^\\s]*$"
    allowed_schemes: [http, https]
  username:
    pattern: "^[a-zA-Z0-9_-]{3,20}$"
    max_length: 20
  password:
    min_length: 12
    require_uppercase: true
    require_lowercase: true
    require_digit: true
    require_special: true
  phone:
    pattern: "^\\+?[1-9]\\d{1,14}$"
```

### 2.3 SQL 注入防护

```python
# ✅ 使用参数化查询
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# ❌ 字符串拼接（SQL 注入风险）
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### 2.4 XSS 防护

```yaml
xss_prevention:
  - 对所有输出进行 HTML 编码
  - 使用 Content Security Policy (CSP)
  - 不使用 innerHTML（使用 textContent）
  - 验证和清理用户输入
  - 使用安全的模板引擎（自动转义）
```

---

## 3. 认证与授权

### 3.1 密码存储

```yaml
password_storage:
  algorithm: bcrypt / argon2id
  cost_factor: 12+
  salt: 使用随机盐
  禁止: MD5, SHA1, SHA256（无盐）
```

### 3.2 会话管理

```yaml
session_management:
  session_timeout: 30 分钟（无活动）
  absolute_timeout: 24 小时
  cookie_flags:
    http_only: true
    secure: true
    same_site: strict
  会话 ID: 使用密码学安全随机数
```

### 3.3 JWT 安全

```yaml
jwt_security:
  algorithm: RS256 或 ES256（不用 HS256）
  expiration: 15 分钟（access token）
  refresh_token: 7 天
  验证:
    - 签名算法
    - 过期时间
    - issuer
    - audience
  禁止:
    - 在 payload
    - 使用 none 算法
    - 不验证签名
```

### 3.4 授权检查

```yaml
authorization:
  - 在每个端点检查权限
  - 使用 RBAC 或 ABAC
  - 记录授权失败
  - 默认拒绝（除非明确允许）
```

---

## 4. 数据保护

### 4.1 敏感数据分类

```yaml
data_classification:
  public: 公开信息
  internal: 内部信息，不对外公开
  confidential: 机密信息，需要授权访问
  secret: 密钥、密码、证书
```

### 4.2 数据加密

```yaml
encryption:
  at_rest:
    algorithm: AES-256-GCM
    key_management: 使用 KMS
  in_transit:
    protocol: TLS 1.3
    certificate: 使用有效证书
  application:
    algorithm: AES-256-GCM
    key_rotation: 每 90 天
```

### 4.3 日志安全

```yaml
logging_security:
  禁止记录:
    - 密码
    - 密钥/令牌
    - 信用卡号
    - 社会安全号码
    - 完整的堆栈跟踪（生产环境）
  必须记录:
    - 认证事件
    - 授权失败
    - 输入验证失败
    - 系统错误
```

---

## 5. API 安全

### 5.1 速率限制

```yaml
rate_limiting:
  global: 1000 requests/minute
  per_user: 100 requests/minute
  per_endpoint: varies
  response: 429 Too Many Requests
  headers:
    - X-RateLimit-Limit
    - X-RateLimit-Remaining
    - X-RateLimit-Reset
```

### 5.2 CORS 配置

```yaml
cors:
  allowed_origins: ["https://yourdomain.com"]
  allowed_methods: [GET, POST, PUT, DELETE]
  allowed_headers: [Authorization, Content-Type]
  allow_credentials: true
  max_age: 86400
```

### 5.3 请求验证

```yaml
request_validation:
  max_body_size: 10MB
  max_uri_length: 2048
  content_type: 验证 Content-Type
  timeout: 30 seconds
```

---

## 6. 依赖安全

### 6.1 依赖管理

```yaml
dependency_security:
  - 使用 lockfile
  - 定期更新依赖
  - 扫描已知漏洞
  - 验证包完整性
  - 使用私有仓库（如需要）
```

### 6.2 依赖扫描

```yaml
dependency_scanning:
  tools:
    - npm audit
    - pip-audit
    - cargo audit
    - snyk
  frequency: 每次构建
  severity_threshold: high
  auto_fix: 仅 patch 版本
```

---

## 7. 容器安全

### 7.1 Docker 安全

```yaml
docker_security非 root 用户
  - 使用最小基础镜像
  - 扫描镜像漏洞
  - 不安装不必要的包
  - 使用多阶段构建
  - 设置只读文件系统
  - 限制资源使用
```

### 7.2 Kubernetes 安全

```yaml
k8s_security:
  - 使用 Security Context
  - 限制容器权限
  - 使用 Network Policy
  - 使用 Pod Security Policy
  - 加密 Secrets
```

---

## 8. 安全测试

### 8.1 安全测试类型

```yaml
security_testing:
  sast: 静态应用安全测试
  dast: 动态应用安全测试
 分析
  pentest: 渗透测试
  fuzzing: 模糊测试
```

### 8.2 安全测试工具

```yaml
security_tools:
  sast:
    - bandit (Python)
    - eslint-security (JavaScript)
    - clippy (Rust)
  dast:
    - OWASP ZAP
    - Burp Suite
  sca:
    - snyk
    - safety
    - cargo-audit
```

---

## 9. 安全配置

### 9.1 HTTP 安全头

```yaml
security_headers:
  Content-Security-Policy: "default-src 'self'"
  X-Content-Type-Options: "nosniff"
  X-Frame-Options: "DENY"
  X-XSS-Protection: "1; mode=block"
  Strict-Transport-Security: "max-age=31536000; includeSubDomains"
  Referrer-Policy: "strict-origin-when-cross-origin"
  Permissions-Policy: "camera=(), microphone=(), geolocation=()"
```

### 9.2 错误处理

```yaml
error_security:
  - 不泄露内部实现细节
  - 使用通用错误消息
  - 记录详细错误（服务器端）
  - 返回适当的 HTTP 状态码
```

---

## 10. 安全事件响应

### 10.1 事件响应流程

```
1. 检测: 监控和告警
2. 响应: 隔离和遏制
3. 恢复: 修复和恢复服务
4. 事后: 分析和改进
```

### 10.2 日志和审计

```yaml
audit_logging:
  events:
    - 登录成功/失败
    - 权限变更
    - 数据访问
    - 配置变更
  retention: 1 年
  storage: 安全的日志服务
```
