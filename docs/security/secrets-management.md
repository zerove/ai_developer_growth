---
title: 密钥管理最佳实践
description: > 覆盖密钥生成、存储、分发、轮换、撤销、审计的全生命周期管理。
category: 治理层
tags: ['AI', 'API', 'Kubernetes', 'Python', 'SQL']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# 密钥管理最佳实践

> 覆盖密钥生成、存储、分发、轮换、撤销、审计的全生命周期管理。

---

## 1. 密钥分类与保护级别

| 类型 | 示例 | 保护级别 | 存储位置 | 轮换频率 |
|------|------|----------|----------|----------|
| **根密钥/主密钥** | KMS Master Key、CA Root Key | 最高 (P0) | HSM / 云 KMS | 1-2 年 / 重大事件 |
| **数据加密密钥 (DEK)** | 磁盘加密、字段加密 | 高 (P1) | KMS 加密后存配置/DB | 90-180 天 |
| **API Key / Token** | Stripe Key、GitHub PAT、JWT Signing Key | 高 (P1) | Secret Manager / Vault | 30-90 天 |
| **数据库密码** | PostgreSQL、Redis 密码 | 高 (P1) | Secret Manager / Vault | 90 天 |
| **服务间 mTLS 证书** | Istio、Linkerd 证书 | 中 (P2) | cert-manager / Vault PKI | 24h-30 天 (自动) |
| **SSH/部署密钥** | CI/CD Deploy Key、GitHub Deploy Key | 中 (P2) | Secret Manager / Vault | 90 天 |
| **特权访问凭据** | 管理员 SSH、Break-glass 账号 | 最高 (P0) | PAM / Vault / 物理保管 | 按需 / 季度 |

---

## 2. 存储方案对比

| 方案 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| **云 Secret Manager** (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault) | 云原生应用、托管服务 | 托管、审计、自动轮换、IAM 集成 | 厂商锁定、成本 |
| **HashiCorp Vault** | 混合云、自建、动态凭据 | 动态秘钥、租约、PKI、多云 | 运维复杂、需高可用 |
| **Sealed Secrets / SOPS** | GitOps、声明式配置 | Git 友好、无额外基建 | 无自动轮换、轮换需重新封装 |
| **环境变量 + .env** | 本地开发、极简单场景 | 简单 | **生产禁用**、易泄露、无审计 |
| **Kubernetes Secrets** | K8s 原生工作负载 | 原生、RBAC | 默认 base64 非加密、需配合 External Secrets Operator |

**推荐架构**：
```
生产: 云 Secret Manager / Vault (源头)
     ↓ External Secrets Operator / CSI Driver
K8s:  Kubernetes Secrets (只读投影)
     ↓ 容器环境变量 / 文件挂载
应用: 运行时只读内存
```

---

## 3. 密钥全生命周期

### 3.1 生成
```bash
# ✅ 正确: 高熵、标准算法、KMS 生成
aws kms generate-data-key --key-id alias/app-data-key --key-spec AES_256

# ❌ 禁止: 低熵、自定义算法、硬编码
export API_KEY="my-super-secret-key-123"
```

### 3.2 存储与分发
```yaml
# Kubernetes: ExternalSecret 从 Vault 同步
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: app-secrets
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_PASSWORD
      remoteRef:
        key: secret/data/app/prod
        property: db_password
```

### 3.3 运行时注入
```dockerfile
# Docker: 运行时挂载，不构建进镜像
# docker run --mount=type=bind,source=/run/secrets,target=/secrets,readonly
ENV CONFIG_FILE=/secrets/app-config.yaml
```

```python
# Python: 运行时读取，不缓存全局
def get_db_password() -> str:
    with open("/secrets/db_password") as f:
        return f.read().strip()
```

### 3.4 轮换策略

| 轮换方式 | 适用密钥 | 停机时间 | 实现复杂度 |
|----------|----------|----------|------------|
| **蓝绿/双写** | API Key、DB 密码 | 零停机 | 中 (需应用支持双密钥) |
| **滚动更新** | K8s Secret、配置文件 | 秒级 (Pod 重启) | 低 (Operator 自动) |
| **版本化密钥** | JWT Signing Key、加密密钥 | 零停机 | 高 (应用需多版本解密) |
| **动态凭据** | DB 密码、云临时凭据 | 零停机 | 低 (Vault 原生) |

**双写轮换示例**：
```python
# 应用同时接受旧/新 Key，逐步迁移
def verify_jwt(token: str) -> Claims:
    for key in [current_signing_key, previous_signing_key]:
        try:
            return jwt.decode(token, key, algorithms=["RS256"])
        except jwt.InvalidTokenError:
            continue
    raise InvalidTokenError()
```

### 3.5 撤销与应急
```bash
# 1. 立即禁用泄露密钥
aws secretsmanager put-secret-value \
  --secret-id prod/stripe-key \
  --secret-string '{"revoked": true, "revoked_at": "2026-07-20T10:00:00Z"}'

# 2. 生成新密钥并部署 (自动化流水线)
# 3. 吊销证书 (如 mTLS)
# 4. 审计日志追踪使用范围
```

---

## 4. 代码层面防泄露

### 4.1 静态扫描
```yaml
# .github/workflows/secret-scan.yml
- uses: trufflesecurity/trufflehog@v3
  with:
    path: ./
    base: main
    head: HEAD
    extra_args: --only-verified --fail
```

### 4.2 预提交钩子
```yaml
# .pre-commit-config.yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
    - id: detect-secrets
      args: ['--force-use-all-plugins']
```

### 4.3 运行时防护
```python
# settings.py - 禁止硬编码
import os
from functools import lru_cache

@lru_cache()
def get_secret(name: str) -> str:
    value = os.getenv(name)
    if not value:
        # 从 Secret Manager 兜底读取
        value = secret_manager.access(name)
    if not value:
        raise RuntimeError(f"Secret {name} not configured")
    return value

# 使用
DATABASE_URL = get_secret("DATABASE_URL")  # 运行时读取
```

---

## 5. 审计与合规

| 审计项 | 频率 | 工具/方式 |
|--------|------|-----------|
| 密钥访问日志 | 实时 | CloudTrail / Vault Audit Log / SIEM |
| 密钥轮换合规性 | 周度 | 自动化检查：`last_rotated < now() - policy.max_age` |
| 最小权限审查 | 月度 | IAM Policy Analyzer / Vault ACL 审计 |
| 泄露扫描 | 每次 PR + 定时 | TruffleHog / GitGuardian / GitLeaks |
| 证书到期监控 | 持续 | cert-manager + Prometheus Alert |

---

## 6. 事件响应手册

| 场景 | 立即行动 (0-15min) | 短期行动 (1-4h) | 长期行动 |
|------|-------------------|----------------|----------|
| **API Key 泄露到 GitHub** | 1. 撤销 Key 2. 生成新 Key 3. 部署 | 扫描历史提交、轮换相关凭据 | 根因分析、加强预提交 |
| **数据库密码泄露** | 1. 修改密码 2. 重启连接池 | 审计异常访问、通知 DBA | 启用动态凭据 |
| **KMS Master Key 疑似泄露** | 1. 启用 Key Rotation 2. 重新加密所有 DEK | 全量重加密、验证完整性 | 评估 HSM 迁移 |
| **证书过期导致服务中断** | 1. 紧急续签 2. 重新部署 | 补全监控告警 | 自动化证书管理 |

---

## 7. 质量清单

- [ ] 无硬编码密钥（代码、镜像、配置、日志）
- [ ] 所有密钥有明确 Owner、分级、轮换策略
- [ ] 生产环境使用托管 Secret Manager / Vault
- [ ] 密钥访问有审计日志、告警
- [ ] 轮换自动化、验证自动化、回滚预案
- [ ] 应急手册演练过（每季度至少一次）
- [ ] 开发/测试环境使用独立密钥、无生产数据

---

*密钥管理是安全基石，自动化优于人工，审计优于信任。最后更新: 2026-07-20*