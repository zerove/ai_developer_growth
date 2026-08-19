---
title: Authorization Governance Rules
description: > 适用于授权模式的 AI Agent 开发规范。
category: 治理层
tags: ['AI', 'REST', 'API', 'Python', '安全']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# Authorization Governance Rules

> 适用于授权模式的 AI Agent 开发规范。

---

## 1. RBAC (基于角色的访问控制)

### 角色定义

```python
# ✅ 正确: 层级角色模型
from enum import Enum
from functools import wraps


class Role(Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


ROLE_HIERARCHY = {
    Role.ADMIN: {Role.EDITOR, Role.VIEWER},
    Role.EDITOR: {Role.VIEWER},
    Role.VIEWER: set(),
}


def has_role(user_role: Role, required: Role) -> bool:
    """检查用户角色是否满足要求（支持层级）"""
    return user_role == required or required in ROLE_HIERARCHY[user_role]


# ❌ 禁止: 硬编码角色判断
if user.role == "admin":
    pass
elif user.role == "editor":
    pass  # 无法扩展，层级关系隐含在逻辑中
```

### 装饰器模式

```python
# ✅ 正确: 声明式权限控制
def require_role(required: Role):
    def decorator(func):
        @wraps(func)
        def wrapper(current_user, *args, **kwargs):
            if not has_role(current_user.role, required):
                raise PermissionError(f"需要 {required.value} 权限")
            return func(current_user, *args, **kwargs)

        return wrapper

    return decorator


@require_role(Role.EDITOR)
def update_post(current_user, post_id, data): ...
```

---

## 2. ABAC (基于属性的访问控制)

### 属性评估

```python
# ✅ 正确: 基于属性的细粒度控制
from dataclasses import dataclass
from typing import Callable


@dataclass
class AuthContext:
    user: dict  # {role, department, clearance_level}
    resource: dict  # {owner_id, sensitivity, classification}
    action: str  # "read", "write", "delete"
    environment: dict  # {time, ip, device_type}


Policy = Callable[[AuthContext], bool]


def owner_or_admin_policy(ctx: AuthContext) -> bool:
    """资源所有者或管理员可操作"""
    return ctx.user["role"] == "admin" or ctx.resource["owner_id"] == ctx.user["id"]


def time_restricted_policy(ctx: AuthContext) -> bool:
    """工作时间内可访问"""
    return ctx.environment["time"].hour in range(9, 18)


class PolicyEngine:
    def __init__(self):
        self.policies: list[Policy] = []

    def add_policy(self, policy: Policy):
        self.policies.append(policy)
        return self

    def evaluate(self, ctx: AuthContext) -> bool:
        return all(p(ctx) for p in self.policies)


# 使用
engine = PolicyEngine()
engine.add_policy(owner_or_admin_policy).add_policy(time_restricted_policy)
allowed = engine.evaluate(ctx)
```

---

## 3. OAuth2 Scopes 与 JWT Claims

### Scope 设计

```
# ✅ 正确: 细粒度 scope
# 读写分离，资源粒度
read:users       # 读取用户信息
write:users      # 修改用户信息
delete:users     # 删除用户
read:posts       # 读取文章
admin:*          # 管理员全权限

# ❌ 禁止: 粗粒度 scope
read             # 能读什么？
admin            # 权限过大
```

### JWT Claims 中嵌入权限

```python
# ✅ 正确: 在 JWT 中携带最小权限集
def generate_token(user) -> str:
    claims = {
        "sub": user.id,
        "roles": [r.value for r in user.roles],
        "scope": compute_scopes(user),  # 基于角色计算具体 scope
        "permissions": [
            {"resource": "posts", "actions": ["read", "write"]},
            {"resource": "users", "actions": ["read"]},
        ],
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    return jwt.encode(claims, private_key, algorithm="RS256")
```

### Scope 验证中间件

```python
# ✅ 正确: FastAPI scope 验证
from fastapi import Depends, HTTPException, Security
from fastapi.security import SecurityScopes


async def verify_scope(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
):
    payload = jwt.decode(token, public_key, algorithms=["RS256"])
    token_scopes = payload.get("scope", "").split()

    for required_scope in security_scopes.scopes:
        if required_scope not in token_scopes:
            raise HTTPException(
                status_code=403,
                detail=f"权限不足: 需要 {required_scope}",
            )
    return payload
```

---

## 4. Policy-Based Access Control (OPA/Rego)

### 策略定义

```python
# ✅ 正确: 使用 OPA 做策略引擎
import httpx


class OPAClient:
    def __init__(self, addr: str = "http://localhost:8181"):
        self.addr = addr

    async def check(self, input_data: dict) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.addr}/v1/data/authz/allow",
                json={"input": input_data},
            )
            return resp.json().get("result", False)


# 使用
async def authorize(user, resource, action):
    allowed = await opa_client.check(
        {
            "user": {"role": user.role, "department": user.dept},
            "resource": {"type": resource.type, "owner": resource.owner_id},
            "action": action,
        }
    )
    if not allowed:
        raise PermissionError("OPA 策略拒绝")
```

### Rego 策略示例

```python
# policy/authz.rego
# ✅ 正确: 清晰的策略规则
# package authz
#
# default allow = false
#
# allow {
#     input.user.role == "admin"
# }
#
# allow {
#     input.user.id == input.resource.owner
#     input.action == "read"
# }
#
# allow {
#     input.user.department == input.resource.department
#     input.action == "read"
# }
```

---

## 5. 模式对比

| 模式 | 复杂度 | 灵活性 | 适用场景 | 维护成本 |
|------|--------|--------|----------|----------|
| RBAC | 低 | 中 | 中小系统，角色固定 | 低 |
| ABAC | 高 | 高 | 多租户，细粒度权限 | 中 |
| OAuth2 Scopes | 中 | 中 | API 开放平台，第三方接入 | 低 |
| JWT Claims | 低 | 中 | 微服务间认证 | 中 |
| OPA/Rego | 高 | 极高 | 企业级，策略需版本控制 | 高 |

### 选型建议

- **初创项目 (3 人以下团队)**: RBAC + JWT Claims，够用且维护成本低
- **SaaS 多租户**: ABAC 或 OPA，租户级别权限隔离
- **开放 API**: OAuth2 Scopes，标准协议，第三方友好
- **微服务架构**: JWT Claims 传递身份 + OPA 做网关级策略

---

## 6. 常见错误

```python
# ❌ 禁止: 前端控制权限
{isAdmin && <DeleteButton />}  # 用户可绕过

# ✅ 正确: 后端必须独立验证
@app.route("/api/users/<id>", methods=["DELETE"])
@require_role(Role.ADMIN)
def delete_user(id):
    ...

# ❌ 禁止: 权限检查遗漏
@app.route("/api/users/<id>", methods=["PUT"])
def update_user(id):  # 任何用户都能改别人的数据
    ...

# ✅ 正确: 资源所有权验证
@app.route("/api/users/<id>", methods=["PUT"])
@require_role(Role.EDITOR)
def update_user(current_user, id):
    if current_user.id != id and not has_role(current_user.role, Role.ADMIN):
        raise PermissionError("不能修改其他用户的信息")
    ...
```

---

## 7. 质量检查清单

### RBAC

- [ ] 角色层级关系明确
- [ ] 默认拒绝所有访问
- [ ] 权限粒度适中（不过粗、不过细）
- [ ] 支持角色升级/降级

### OAuth2/JWT

- [ ] Scope 命名规范一致
- [ ] Token 过期时间合理
- [ ] 支持 Token 撤销
- [ ] Claims 不包含敏感信息

### 安全

- [ ] 后端强制验证权限
- [ ] 防止权限提升
- [ ] 审计日志记录授权决策
- [ ] 定期审查角色分配

---

*本规范随授权最佳实践演进持续更新。最后更新: 2026-07-20*
