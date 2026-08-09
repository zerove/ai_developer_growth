---
title: 单元测试最佳实践
description: > 适用于 AI Agent 生成的测试代码，确保测试可靠、可维护、高覆盖。
category: 工具层
tags: ['AI', 'API', 'Python', '测试', 'unit']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# 单元测试最佳实践

> 适用于 AI Agent 生成的测试代码，确保测试可靠、可维护、高覆盖。

---

## 1. 测试结构 (AAA 模式)

```python
# ✅ 正确: Arrange-Act-Assert 清晰分离
def test_calculate_discount_vip():
    # Arrange
    user = User(id=1, tier="VIP")
    order = Order(total=1000, items=3)
    service = DiscountService()

    # Act
    discount = service.calculate(user, order)

    # Assert
    assert discount == 150  # VIP 15% off
```

```python
# ❌ 禁止: 混在一起，难以阅读
def test_calculate_discount():
    assert DiscountService().calculate(User("VIP"), Order(1000)) == 150
```

---

## 2. 命名约定

| 模式 | 示例 | 说明 |
|------|------|------|
| `test_<method>_<scenario>_<expected>` | `test_calculate_discount_vip_returns_15_percent` | 推荐 |
| `test_<method>_<edge_case>` | `test_calculate_discount_zero_total_returns_zero` | 边界情况 |

---

## 3. 核心原则

### 单一职责
- 每个测试**只验证一个行为**
- 一个测试函数 = 一个 Assert 逻辑点（可多个 assert 但服务于同一断言）

### 确定性
- **无随机性**：不依赖时间、随机数、外部网络
- **无状态依赖**：测试间不共享可变状态

### 隔离性
- 外部依赖必须 Mock
- 数据库测试用事务回滚或内存数据库

---

## 4. Mock 策略

```python
# ✅ 正确: 只 Mock 接口边界
@patch("src.service.external_api.call")
def test_service_calls_api(mock_call):
    mock_call.return_value = {"status": "ok"}
    service.do_work()
    mock_call.assert_called_once_with(expected_params)
```

```python
# ❌ 禁止: Mock 内部实现细节
@patch("src.service.internal_helper")
def test_service(mock_helper):
    ...
```

---

## 5. 参数化测试

```python
# ✅ 正确: 覆盖多组输入
@pytest.mark.parametrize("tier,total,expected", [
    ("VIP", 1000, 150),
    ("GOLD", 1000, 100),
    ("SILVER", 1000, 50),
    ("BRONZE", 1000, 0),
])
def test_discount_tiers(tier, total, expected):
    assert DiscountService().calculate(User(tier=tier), Order(total=total)) == expected
```

---

## 6. 常见反模式

| 反模式 | 问题 | 修正 |
|--------|------|------|
| 测试实现而非行为 | 重构即破坏 | 测试**输入输出契约** |
| 过度 Mock | 测试失去意义 | 只 Mock 外部 I/O |
| 测试数据硬编码 | 难维护 | 使用 Factory/Builder |
| 无清理的全局状态 | 测试污染 | fixture 自动清理 |

---

## 7. 覆盖率目标

| 层级 | 目标 | 说明 |
|------|------|------|
| 核心业务逻辑 | ≥90% | Domain Service, Entity |
| Application Service | ≥80% | Use Case 编排 |
| Infrastructure | ≥70% | Repository, Adapter |
| UI/Controller | ≥60% | 端到端由 E2E 覆盖 |

---

## 8. Python 实用片段

### Fixture 复用
```python
# conftest.py
@pytest.fixture
def sample_user():
    return UserFactory.create(tier="GOLD")

@pytest.fixture
def discount_service():
    return DiscountService()
```

### 自定义断言
```python
# test_assertions.py
def assert_discount_applied(result, expected_pct):
    assert result.discount_pct == expected_pct
    assert result.final_price == round(result.original * (1 - expected_pct/100), 2)
```

---

## 9. TypeScript/Jest 要点

```typescript
// ✅ 正确: 使用 jest.fn() 而非手写 Mock
const mockApi = { call: jest.fn().mockResolvedValue({data: "ok"}) };

// ✅ 正确: 测试异步
await expect(service.fetchData()).resolves.toEqual({data: "ok"});

// ✅ 正确: 快照测试用于稳定输出
expect(renderedComponent).toMatchSnapshot();
```

---

## 10. 质量清单

- [ ] 每个测试独立可运行（无顺序依赖）
- [ ] 测试名表达**业务意图**而非实现细节
- [ ] Edge cases 覆盖：空值、边界、异常、并发
- [ ] Mock 验证调用参数，而非仅返回值
- [ ] 无 `time.sleep`、`random`、真实网络调用
- [ ] CI 中 `pytest --cov-fail-under=70` 强制执行

---

*单元测试是重构的安全网。最后更新: 2026-07-20*
