# 集成/E2E 测试策略

> 覆盖服务间交互、数据库、消息队列、外部 API 的真实集成路径。

---

## 1. 测试金字塔定位

```
        /\
       /  \  E2E Tests (少、慢、贵)     ← 本文档
      /----\
     /      \  Integration Tests (中)   ← 本文档
    /--------\
   /          \ Unit Tests (多、快、廉价)  ← unit-testing.md
  /------------\
```

**原则**：集成测试只覆盖单元测试**无法验证**的交互路径。

---

## 2. 分类与边界

| 类型 | 范围 | 速度 | 典型场景 |
|------|------|------|----------|
| **组件集成** | 单服务 + 真实 DB/Redis | 中 | Repository + 真实 Postgres |
| **契约测试** | Consumer-Driven Contract | 快 | Provider/Consumer 兼容性 |
| **E2E 端到端** | 全链路 (UI → API → DB) | 慢 | 关键业务流程（下单、支付） |

---

## 3. 环境策略

| 环境 | 用途 | 数据隔离 |
|------|------|----------|
| **本地开发** | Testcontainers / Docker Compose | 每测试独立容器 |
| **CI** | 临时容器 + 事务回滚 | 并行安全 |
| **Staging** | 完整部署 + 真实数据子集 | 仅读、定期刷新 |

```yaml
# docker-compose.test.yml 示例
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: test_db
      POSTGRES_PASSWORD: test
    tmpfs: /var/lib/postgresql/data  # 内存加速
  redis:
    image: redis:7-alpine
```

---

## 4. 数据库集成测试

### Python (SQLAlchemy + pytest)
```python
# conftest.py
@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("postgresql://test:test@localhost/test_db")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.rollback()  # 关键：回滚而非 drop，保持 schema
    session.close()

# test_repository.py
def test_user_repository_crud(db_session):
    repo = UserRepository(db_session)
    user = repo.create(User(email="a@b.com"))
    assert repo.get(user.id).email == "a@b.com"
```

### 事务回滚模式（推荐）
- 每个测试开启事务
- 测试结束自动回滚
- 无需清理数据，**极快**

---

## 5. 消息队列集成测试

### Kafka (Testcontainers)
```python
@pytest.fixture
def kafka():
    with KafkaContainer() as kafka:
        yield kafka.get_bootstrap_server()

def test_producer_consumer(kafka):
    producer = Producer(bootstrap_servers=kafka)
    consumer = Consumer(bootstrap_servers=kafka, group_id="test")
    topic = "test-topic"

    producer.send(topic, {"key": "value"})
    producer.flush()

    consumer.subscribe([topic])
    msg = consumer.poll(timeout_ms=5000)
    assert msg.value() == b'{"key": "value"}'
```

### RabbitMQ
```python
# 使用内存模式或 Testcontainers
# 重点测试：死信队列、重试策略、消息确认
```

---

## 6. 外部 API 契约测试

### Pact (Consumer-Driven)
```python
# test_consumer.py
@pytest.fixture
def pact():
    return Pact(consumer="OrderService", provider="PaymentService")

def test_create_payment(pact):
    (pact
     .given("payment service is available")
     .upon_receiving("a request to create payment")
     .with_request("POST", "/payments", body={"amount": 100})
     .will_respond_with(201, body={"id": "pay_123", "status": "created"}))
    
    with pact:
        client = PaymentClient(pact.uri)
        result = client.create_payment(100)
        assert result["id"] == "pay_123"
```

**优势**：Provider 变更时自动检测破坏性变更。

---

## 7. E2E 测试（Playwright/Cypress）

```typescript
// tests/order-flow.spec.ts
test("完整下单流程", async ({ page }) => {
  await page.goto("/login");
  await page.fill("#email", "user@test.com");
  await page.click("button:has-text('登录')");
  
  await page.goto("/products/123");
  await page.click("button:has-text('加入购物车')");
  await page.click("a:has-text('结算')");
  
  await expect(page.locator(".order-confirmation")).toBeVisible();
});
```

**选择性运行**：仅核心 5-10 条关键路径，标记 `@e2e`。

---

## 8. Testcontainers 最佳实践

| 场景 | 推荐方式 |
|------|----------|
| 单元测试需 DB | `pytest` fixture + Testcontainers，function scope |
| 并行测试 | 每测试独立容器，或共享容器 + 事务隔离 |
| 启动慢 | 复用容器（session scope），配合 `tmpfs` 加速 |
| CI 缓存 | `docker layer caching` + 预拉取镜像 |

---

## 9. 常见坑与对策

| 坑 | 症状 | 解决 |
|----|------|------|
| 测试间数据泄漏 | 偶发失败 | 事务回滚 / 容器重建 / 唯一键前缀 |
| 容器启动超时 | CI 偶发挂起 | 增加 `start_timeout`、预热镜像 |
| 外部 API 依赖 | 网络抖动导致失败 | Mock Server (WireMock) / 契约测试 |
| 测试数据硬编码 | 并行冲突 | Factory 生成随机唯一数据 |

---

## 10. 执行策略

```yaml
# .github/workflows/integration.yml
jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: {POSTGRES_PASSWORD: test}
        ports: [5432:5432]
        options: >-
          --health-cmd="pg_isready"
          --health-interval=10s
    steps:
      - uses: actions/checkout@v4
      - name: Run integration tests
        run: pytest tests/integration -v --tb=short
```

---

## 11. 关键指标

| 指标 | 目标 | 备注 |
|------|------|------|
| 集成测试覆盖核心流程 | ≥80% | 关键用例全覆盖 |
| 测试执行时间 (CI) | <10 min | 并行化、分层执行 |
| 易失性测试率 | <1% | 定期清理、隔离 |

---

*集成测试验证"接口契约"，单元测试验证"内部逻辑"。最后更新: 2026-07-20*