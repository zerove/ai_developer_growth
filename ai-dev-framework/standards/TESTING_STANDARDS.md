# 测试标准 (Testing Standards)

> 系统化的测试策略、标准和最佳实践。

---

## 1. 测试金字塔

```
        /  E2E  \           少量，验证完整流程
       / 集成测试 \          适量，验证模块协作
      /   单元测试   \       大量，验证单个函数
```

```yaml
test_distribution:
  unit: 70%
  integration: 20%
  e2e: 10%
```

---

## 2. 测试命名规范

### 2.1 格式

```
test_<被测行为>_<条件>_>
```

### 2.2 示例

```python
# ✅ 好的命名
test_calculate_total_with_empty_cart_returns_zero()
test_fetch_user_when_network_timeout_raises_timeout_error()
test_validate_email_with_invalid_format_returns_false()

# ❌ 坏的命名
test_calculate()  # 没有条件和预期
test_works()  # 不知道测什么
test_1()  # 无意义
test_should_return_true()  # 没有被测行为
```

---

## 3. 测试结构 (AAA)

```python
def test_function():
    # Arrange - 准备测试数据和环境
    input_data = create_test_user()
    expected = "expected_result"

    # Act - 执行被测操作
    result = function_under_test(input_data)

    # Assert - 验证结果
    assert result == expected
```

---

## 4. 测试覆盖率

### 4.1 最低要求

```yaml
coverage_thresholds:
  overall: 80%
  new_code: 90%
  critical_paths: 95%
  branches: 75%
```

### 4.2 覆盖率类型

|低要求 |
|------|------|----------|
| 行覆盖率 | 每行代码被执行 | 80% |
| 分支覆盖率 | 每个 if/else 分支 | 75% |
| 函数覆盖率 |  85% |
| 突变覆盖率 | 代码变更被检测 | 60% |

### 4.3 不需要覆盖的代码

```yaml
excluded_from_coverage:
  - 自动生成的代码
  - 配置文件
  - 类型定义/接口
  - 日志语句
  - 简单的 getter/setter
```

---

## 5. Mock 策略

### 5.1 何时 Mock

```yaml
mock_rules:
  must_mock:
    - 外部网络请求
    - 数据库操作
    - 文件系统操作
    - 时间/日期
    - 随机数生成
    - 消息队列
  must_not_mock:
    - 被测对象本身
    - 纯函数
    - 简单数据结构
    - 值对象
```

### 5.2 Mock 最佳实践

```
- Mock 边界，不 Mock 核心逻辑
- 使用依赖注入，不用全局 Mock
- Mock 行为，不 Mock 状态
- 验证交互，不只是返回值
- 使用 Fake/Stub 代替 Mock（当可能时）
```

---

## 6. 测试数据管理

### 6.1 测试数据原则

```yaml
data_rules:
  - 使用工厂函数创建测试数据
  - 每个测试独立，不依赖其他测试的数据
  - 使用 fixtures 管理共享数据
  - 清理测试数据（teardown）
  - 使用有意义的测试数据
```

### 6.2 测试数据模式

```python
# 工厂模式
def create_user(name="test", email="test@example.com", role="user"):
    return User(name=name, email=email, role=role)


# Fixture 模式
@pytest.fixture
def sample_user():
    return User(name="Alice", email="alice@example.com", role="admin")


# Builder 模式
user = UserBuilder().with_name("Bob").with_role("admin").build()
```

---

## 7. 测试类型规范

### 7.1 单元测试

```yaml
unit_test_rules:
  - 测试单个函数/方法
  - 外部依赖全部 Mock
  - 每个测试 < 10ms<behavior>
```

### 7.2 集成测试

```yaml
integration_test_rules:
  - 测试模块间交互
  - 可使用真实数据库（测试专用）
  - 可使用 TestContainers
  - 每个测试 < 1s
  - 测试后清理数据
  - 命名: test_<module>_integration
```

### 7.3 E2E 测试

```yaml
e2e_test_rules:
  - 测试完整用户流程
  -staging）
  - 覆盖关键业务路径
  - 每个测试 < 30s<user_flow>_e2e
```

---

## 8. 测试反模式

### 8.1 禁止的反模式

```yaml
anti_patterns:
  - 测试间依赖: 测试执行顺序不应影响结果
  - 测试实现细节: 测试行为，不测试内部实现
  - 过度 Mock: Mock 所有东西会导致测试脆弱
  - 测试过于复杂: 一个测试只验证一个行为
  - 硬编码测试数据: 使用工厂/fixtures
  - 忽略边界条件: 测试极值
  - 测试太慢: 单元测试 < 10ms
```

### 8.2 测试代码质量

```
测试代码标准:
- 与生产代码同等质量
- 重构时同步更新测试
- 保持测试简洁
```

---

## 9. 测试自动化

### 9.1 CI/CD 集成

```yaml
ci_integration:
  pre_commit:
    - lint check
    - type check
    - unit tests (fast)
  pull_request:
    - all unit tests
    - integration tests
    - coverage report
  merge_to_main:
    - full test suite
    - coverage check (≥80%)
    - mutation testing (optional)
  release:
    - e2e tests
    - performance tests
    - security scan
```


```
```

---

### 10.1 测试债务管理

```yaml
maintenance_rules:
  - 失败的测试立即修复
  - 不跳过测试（除非有 ticket 跟踪）
  - 定期审查测试价值
  - 删除无用的测试

### 10.2 测试文档

- Mock 策略
- 已知限制
- 运行方式
```
