---
title: Testing Strategy Governance Rules
description: > 适用于测试策略的 AI Agent 开发规范。
category: 工具层
tags: ['AI', 'API', 'Python', '测试', 'SQL']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Testing Strategy Governance Rules

> 适用于测试策略的 AI Agent 开发规范。

---

## 1. 测试金字塔

### 测试层次

```
        E2E 测试 (少量)
           /  \
          /    \
     集成测试 (适量)
        /        \
       /          \
  单元测试 (大量)
```

### 测试比例

| 测试类型 | 比例 | 执行时间 | 成本 |
|----------|------|----------|------|
| 单元测试 | 70% | 毫秒 | 低 |
| 集成测试 | 20% | 秒 | 中 |
| E2E 测试 | 10% | 分钟 | 高 |

---

## 2. 单元测试规范

### AAA 模式

```python
# ✅ 正确: Arrange-Act-Assert
def test_calculate_total():
    # Arrange
    items = [
        {'price': 10, 'quantity': 2},
        {'price': 20, 'quantity': 1}
    ]
    
    # Act
    total = calculate_total(items)
    
    # Assert
    assert total == 40

# ❌ 禁止: 混乱的测试
def test_calculate_total():
    assert calculate_total([{'price': 10, 'quantity': 2}, {'price': 20, 'quantity': 1}]) == 40
```

### 测试命名

```python
# ✅ 正确: 清晰的测试命名
def test_calculate_total_returns_sum_of_prices():
    pass

def test_calculate_total_handles_empty_list():
    pass

def test_calculate_total_raises_error_for_negative_price():
    pass

# ❌ 禁止: 模糊的命名
def test_total():
    pass

def test_calculate():
    pass
```

### 测试覆盖

```python
# ✅ 正确: 覆盖边界情况
def test_divide():
    # 正常情况
    assert divide(10, 2) == 5
    
    # 边界情况
    assert divide(0, 1) == 0
    assert divide(1, 1) == 1
    
    # 异常情况
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
```

---

## 3. 集成测试规范

### 数据库测试

```python
# ✅ 正确: 使用测试数据库
@pytest.fixture
def db_session():
    engine = create_engine('postgresql://localhost/test_db')
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

def test_create_user(db_session):
    user = User(name='John', email='john@example.com')
    db_session.add(user)
    db_session.commit()
    
    result = db_session.query(User).filter_by(email='john@example.com').first()
    assert result is not None
    assert result.name == 'John'
```

### API 测试

```python
# ✅ 正确: 测试完整流程
@pytest.mark.asyncio
async def test_user_crud():
    # Create
    response = await client.post('/api/users', json={
        'name': 'John',
        'email': 'john@example.com'
    })
    assert response.status_code == 201
    user_id = response.json()['id']
    
    # Read
    response = await client.get(f'/api/users/{user_id}')
    assert response.status_code == 200
    assert response.json()['name'] == 'John'
    
    # Update
    response = await client.put(f'/api/users/{user_id}', json={
        'name': 'Jane'
    })
    assert response.status_code == 200
    
    # Delete
    response = await client.delete(f'/api/users/{user_id}')
    assert response.status_code == 204
```

---

## 4. E2E 测试规范

### Playwright 示例

```typescript
import { test, expect } from '@playwright/test';

test.describe('User Management', () => {
  test('should create and view user', async ({ page }) => {
    // Navigate to users page
    await page.goto('/users');
    
    // Click create button
    await page.click('button:text("Create User")');
    
    // Fill form
    await page.fill('input[name="name"]', 'John');
    await page.fill('input[name="email"]', 'john@example.com');
    
    // Submit form
    await page.click('button:text("Submit")');
    
    // Verify user is created
    await expect(page.locator('text=John')).toBeVisible();
  });
});
```

### 测试数据管理

```typescript
// ✅ 正确: 使用测试夹具
test.beforeEach(async ({ page }) => {
  // 创建测试数据
  await page.request.post('/api/test/seed', {
    data: { users: [{ name: 'Test User', email: 'test@example.com' }] }
  });
});

test.afterEach(async ({ page }) => {
  // 清理测试数据
  await page.request.post('/api/test/cleanup');
});
```

---

## 5. Mock 规范

### Mock 原则

```python
# ✅ 正确: Mock 外部依赖
@patch('app.services.user.UserRepository')
def test_create_user(mock_repo):
    mock_repo.create.return_value = User(id='123', name='John')
    
    service = UserService()
    user = service.create({'name': 'John'})
    
    assert user.id == '123'
    mock_repo.create.assert_called_once()

# ❌ 禁止: Mock 自己的代码
def test_create_user():
    with patch('app.services.user.UserService.create') as mock:
        mock.return_value = User(id='123')
        service = UserService()
        user = service.create({'name': 'John'})  # Mock 了被测试的代码
        assert user.id == '123'
```

### 测试替身

```python
# ✅ 正确: 使用测试替身
class FakeUserRepository:
    def __init__(self):
        self.users = {}
    
    def find_by_id(self, id):
        return self.users.get(id)
    
    def create(self, data):
        user = User(id=str(len(self.users) + 1), **data)
        self.users[user.id] = user
        return user

def test_get_user():
    repo = FakeUserRepository()
    repo.create({'name': 'John'})
    
    user = repo.find_by_id('1')
    assert user.name == 'John'
```

---

## 6. 性能测试规范

### 负载测试

```javascript
// k6 示例
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '1m', target: 20 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
  },
};

export default function () {
  const res = http.get('http://test.api/users');
  check(res, { 'status was 200': (r) => r.status === 200 });
  sleep(1);
}
```

### 基准测试

```python
# ✅ 正确: 使用 pytest-benchmark
def test_database_query(benchmark):
    def query():
        return db.query('SELECT * FROM users')
    
    result = benchmark(query)
    assert len(result) > 0
```

---

## 7. 测试配置

### pytest 配置

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    slow: marks tests as slow
    integration: marks tests as integration
    e2e: marks tests as e2e
```

### 测试环境

```python
# conftest.py
import pytest
from app import create_app

@pytest.fixture(scope='session')
def app():
    app = create_app('config.TestingConfig')
    yield app

@pytest.fixture(scope='session')
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def setup_test_database():
    # 设置测试数据库
    yield
    # 清理测试数据库
    pass
```

---

## 8. 质量检查清单

### 单元测试

- [ ] AAA 模式使用
- [ ] 清晰的测试命名
- [ ] 覆盖边界情况
- [ ] 无外部依赖

### 集成测试

- [ ] 测试完整流程
- [ ] 使用测试数据库
- [ ] 数据清理
- [ ] 错误场景覆盖

### E2E 测试

- [ ] 核心流程覆盖
- [ ] 测试数据管理
- [ ] 稳定性保证
- [ ] 执行时间控制

---

*本规范随测试最佳实践演进持续更新。最后更新: 2026-07-17*
