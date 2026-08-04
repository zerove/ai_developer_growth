---
title: Mocking 策略与最佳实践
description: > 统一 Mock 原则，避免过度/不足 Mock 导致测试失效或虚假通过。
category: 工具层
tags: ['AI', 'API', 'Python', '测试', 'SQL']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# Mocking 策略与最佳实践

> 统一 Mock 原则，避免过度/不足 Mock 导致测试失效或虚假通过。

---

## 1. 核心原则

| 原则 | 说明 |
|------|------|
| **只 Mock 边界** | 外部 I/O (HTTP、DB、消息队列、文件系统、时间) |
| **不 Mock 内部** | 业务逻辑、私有方法、值对象 — 测试真实行为 |
| **验证契约而非实现** | 断言输入参数、调用次数，不断言内部调用顺序 |
| **真实优于 Mock** | 能用真实依赖（内存 DB、Testcontainers）就不用 Mock |

---

## 2. 决策流程

```
需要测试的代码依赖外部吗？
├── 否 → 直接测试，无需 Mock
└── 是 → 是外部 I/O 边界？
    ├── 否 (内部类/工具函数) → 重构为可测试的纯函数，直接测试
    └── 是 → 能用真实替代品吗？
        ├── 能 (SQLite、Testcontainers、内存队列) → 用真实替代品
        └── 不能 (第三方 API、硬件、耗时服务) → Mock
```

---

## 3. Mock 层级对比

| 层级 | 示例 | 推荐度 | 适用场景 |
|------|------|--------|----------|
| **L0: 真实依赖** | Testcontainers PostgreSQL、内存 Redis | ⭐⭐⭐⭐⭐ | 数据库、缓存、消息队列 |
| **L1: Fake/Stub** | 内存实现的 Repository 接口 | ⭐⭐⭐⭐ | 领域服务测试、Repository 契约 |
| **L2: Mock 框架** | `unittest.mock`, `pytest-mock`, `jest.fn()` | ⭐⭐⭐ | HTTP 客户端、第三方 SDK |
| **L3: 手写 Mock 类** | `class MockPaymentGateway implements PaymentGateway` | ⭐⭐ | 复杂状态交互、需模拟故障 |
| **L4: 部分 Mock (Spy)** | `jest.spyOn(obj, 'method')` | ⭐ | 仅需覆盖特定方法 |

---

## 4. 常见场景模板

### HTTP 客户端 (Python + respx / responses)
```python
# ✅ 推荐: respx (httpx 原生 mock)
import respx
import httpx

@respx.mock
def test_create_payment():
    respx.post("https://api.stripe.com/v1/payments").mock(
        return_value=httpx.Response(200, json={"id": "pi_123", "status": "succeeded"})
    )
    result = payment_service.charge(100, "usd")
    assert result.id == "pi_123"
```

### 数据库 Repository (Fake)
```python
# ✅ 推荐: 内存 Fake 实现接口
class InMemoryUserRepo(UserRepository):
    def __init__(self):
        self._users = {}
    
    def save(self, user):
        self._users[user.id] = user
    
    def find(self, id):
        return self._users.get(id)

def test_user_service_creates_user():
    repo = InMemoryUserRepo()
    service = UserService(repo)
    user = service.register("a@b.com")
    assert repo.find(user.id).email == "a@b.com"
```

### 时间依赖
```python
# ✅ 正确: 注入时间提供者
class TimeProvider:
    def now(self) -> datetime: ...

class SystemTimeProvider(TimeProvider):
    def now(self): return datetime.utcnow()

class FixedTimeProvider(TimeProvider):
    def __init__(self, fixed): self.fixed = fixed
    def now(self): return self.fixed

# 测试时注入 FixedTimeProvider
```

### 消息队列
```python
# ✅ Fake 消息总线
class InMemoryMessageBus(MessageBus):
    def __init__(self):
        self.published = []
    
    def publish(self, event):
        self.published.append(event)
    
    def subscribe(self, handler, event_type):
        self.handlers[event_type] = handler

# 测试验证
def test_order_created_emits_event():
    bus = InMemoryMessageBus()
    service = OrderService(bus)
    service.create_order(...)
    assert len(bus.published) == 1
    assert isinstance(bus.published[0], OrderCreated)
```

---

## 5. Mock 反模式清单

| 反模式 | 代码示例 | 危害 | 修正 |
|--------|----------|------|------|
| **Mock 返回 Mock** | `mock.client.get.return_value.json.return_value = ...` | 脆弱、难读 | 用 `respx` / 手写 Fake |
| **Mock 私有方法** | `with patch.object(service, '_internal')` | 重构即破坏 | 重构为公共接口或测试公共行为 |
| **过度断言调用细节** | `mock.assert_called_with(arg1, arg2, arg3)` | 实现变动测试碎 | 只断言关键参数、调用次数 |
| **全局 Mock 污染** | `monkeypatch.setattr(module, 'func', mock)` 无作用域 | 测试间干扰 | 使用 fixture 自动清理 |
| **Mock 标准库** | `patch('json.dumps')` | 极度脆弱 | 不要 Mock 标准库 |

---

## 6. Python Mock 最佳实践

### `pytest-mock` (推荐)
```python
def test_external_api(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.json.return_value = {"token": "abc"}
    mock_post.return_value.raise_for_status = lambda: None
    
    result = auth_service.login("user", "pass")
    assert result.token == "abc"
    mock_post.assert_called_once()
```

### `unittest.mock.patch` 作为装饰器
```python
@patch("src.service.ExternalClient")
def test_service(mock_client_class):
    mock_client = mock_client_class.return_value
    mock_client.fetch.return_value = {"data": "ok"}
    
    result = MyService().do_work()
    assert result == "ok"
```

---

## 7. TypeScript/Jest Mock 最佳实践

### 模块级 Mock
```typescript
// __mocks__/api/client.ts
export const apiClient = {
  get: jest.fn(),
  post: jest.fn(),
};
```

```typescript
// test/service.test.ts
import { apiClient } from '@/api/client';
import { UserService } from '@/service';

jest.mock('@/api/client');

beforeEach(() => {
  jest.clearAllMocks();
});

test('fetches user', async () => {
  apiClient.get.mockResolvedValue({ id: 1, name: 'John' });
  
  const user = await UserService.getUser(1);
  
  expect(user.name).toBe('John');
  expect(apiClient.get).toHaveBeenCalledWith('/users/1');
});
```

### Mock 实现 vs Mock 返回值
```typescript
// ✅ 简单场景：mockResolvedValue
apiClient.get.mockResolvedValue({id: 1});

// ✅ 复杂场景：mockImplementation
apiClient.get.mockImplementation(async (url) => {
  if (url.includes('error')) throw new Error('Network');
  return {id: parseInt(url.split('/').pop()!)};
});
```

---

## 8. 契约测试替代 Mock

当 Mock 维护成本过高时，改用**契约测试**：

```python
# 使用 Pact
def test_consumer_pact(pact):
    (pact
     .given("user exists")
     .upon_receiving("request for user")
     .with_request("GET", "/users/1")
     .will_respond_with(200, body={"id": 1, "name": "John"}))
    
    with pact:
        client = UserClient(pact.uri)
        user = client.get_user(1)
        assert user.name == "John"
```

**优势**：Provider 变更自动检测破坏性变更，无需手动维护 Mock。

---

## 9. 质量清单

- [ ] 每个 Mock 有明确理由（文档化在测试注释）
- [ ] Mock 作用域最小化（function-scoped fixture）
- [ ] 验证**关键参数**，忽略非关键参数 (`ANY`, `mock.ANY`)
- [ ] 无 Mock 标准库、时间、随机数（注入抽象层）
- [ ] 集成测试用真实依赖，单元测试用 Fake/Mock
- [ ] 定期清理过期 Mock（随重构同步更新）

---

*Mock 是手段，契约验证才是目的。最后更新: 2026-07-20*