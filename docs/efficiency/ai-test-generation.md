---
title: AI 辅助测试生成
description: 使用 AI 工具自动生成测试用例
category: 效率层
tags: [AI, 测试, 单元测试]
difficulty: 进阶
reading_time: 10 分钟
updated: 2026-07-21
---

# AI 辅助测试生成

## 核心原则

AI 测试 = 代码 + 测试框架 + 智能覆盖

## 测试类型

### 1. 单元测试

**生成方法:**
```markdown
请为这个函数生成单元测试:
- 正常情况
- 边界条件
- 错误处理
- 覆盖率要求: 80%
```

### 2. 集成测试

**生成方法:**
```markdown
请生成集成测试:
- API 调用
- 数据库操作
- 外部服务
- 异步处理
```

### 3. E2E 测试

**生成方法:**
```markdown
请生成 E2E 测试:
- 用户流程
- 页面交互
- 数据验证
```

## Prompt 技巧

### 1. 提供代码

```markdown
请为以下代码生成测试:

```python
def calculate_discount(price: float, user_type: str) -> float:
    """计算折扣"""
    if user_type == "vip":
        return price * 0.8
    elif user_type == "normal":
        return price * 0.9
    return price
```

测试框架: pytest
```

### 2. 指定覆盖

```markdown
请确保测试覆盖:
- 所有分支
- 边界值
- 异常情况
- 并发场景
```

### 3. 风格要求

```markdown
测试风格:
- 使用 pytest
- 参数化测试
- Mock 外部依赖
- 清晰的断言
```

## 测试生成模式

### 1. 参数化测试

```python
import pytest


@pytest.mark.parametrize(
    "price,user_type,expected",
    [
        (100.0, "vip", 80.0),
        (100.0, "normal", 90.0),
        (100.0, "unknown", 100.0),
    ],
)
def test_calculate_discount(price, user_type, expected):
    assert calculate_discount(price, user_type) == expected
```

### 2. Mock 测试

```python
from unittest.mock import Mock, patch


def test_with_mock():
    with patch("module.external_api") as mock_api:
        mock_api.return_value = {"status": "ok"}
        result = call_external_api()
        assert result == {"status": "ok"}
```

### 3. 异步测试

```python
import pytest


@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

## 最佳实践

### 1. 测试结构

**AAA 模式:**
```python
def test_example():
    # Arrange
    input_data = [1, 2, 3]

    # Act
    result = process(input_data)

    # Assert
    assert result == [2, 3, 4]
```

### 2. 测试命名

**格式:**
```python
def test_[功能]_[条件]_[结果]():
    ...
```

**示例:**
```python
def test_calculate_discount_vip_returns_80_percent():
    assert calculate_discount(100.0, "vip") == 80.0
```

### 3. 测试维护

**原则:**
- 保持测试独立
- 避免测试依赖
- 定期重构测试

## 效率提升

### 1. 批量生成

**方法:**
- 分析代码结构
- 识别测试点
- 批量生成测试

### 2. 测试模板

**方法:**
- 建立测试模板库
- 标准化测试结构
- 复用测试代码

### 3. 持续集成

**方法:**
- 集成到 CI/CD
- 自动运行测试
- 生成覆盖率报告

## 案例: AI 测试生成

### 背景
- 项目: Python 库
- 函数数量: 30+
- 测试时间: 1 天 → 1 小时

### 过程
1. 提供代码
2. AI 生成测试草稿
3. 人工审核调整
4. 集成到 CI

### 结果
- 测试时间: 降低 90%
- 覆盖率: 85%
- 质量: 良好

---

*最后更新: 2026-07-21*

---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]


## 相关案例

- **相关案例**: [api-design-implementation](../case-studies/api-design-implementation.md)

- **相关案例**: [legacy-system-refactoring](../case-studies/legacy-system-refactoring.md)

- **相关案例**: [ml-model-deployment](../case-studies/ml-model-deployment.md)

- **相关案例**: [microservice-architecture](../case-studies/microservice-architecture.md)

- **相关案例**: [full-integration-test](../case-studies/full-integration-test.md)

- **相关案例**: [api-monitoring](../case-studies/api-monitoring.md)

- **相关案例**: [aiops-automation](../case-studies/aiops-automation.md)

- **相关案例**: [ai-native-coverage-governance](../case-studies/ai-native-coverage-governance.md)

- **相关案例**: [realtime-data-processing](../case-studies/realtime-data-processing.md)

- **相关案例**: [api-doc-generation](../case-studies/api-doc-generation.md)

- **相关案例**: [production-debugging](../case-studies/production-debugging.md)

- **相关案例**: [legacy-refactoring](../case-studies/legacy-refactoring.md)

- **相关案例**: [implement-robust-feature-with-full-dor-and-tdd-compliance](../case-studies/implement-robust-feature-with-full-dor-and-tdd-compliance.md)

- **相关案例**: [code-review-system](../case-studies/code-review-system.md)

- **相关案例**: [security-audit](../case-studies/security-audit.md)

- **相关案例**: [technical-documentation](../case-studies/technical-documentation.md)

- **相关案例**: [data-pipeline](../case-studies/data-pipeline.md)

- **相关案例**: [automated-testing-platform](../case-studies/automated-testing-platform.md)

- **相关案例**: [data-migration](../case-studies/data-migration.md)

- **相关案例**: [ai-context-sync-development](../case-studies/ai-context-sync-development.md)

- **相关案例**: [database-performance-optimization](../case-studies/database-performance-optimization.md)

- **相关案例**: [mobile-app-development](../case-studies/mobile-app-development.md)

- **相关案例**: [api-design](../case-studies/api-design.md)

- **相关案例**: [ai-task-prioritizer](../case-studies/ai-task-prioritizer.md)

- **相关案例**: [unit-testing](../case-studies/unit-testing.md)

- **相关案例**: [devops-pipeline](../case-studies/devops-pipeline.md)

- **相关案例**: [database-migration](../case-studies/database-migration.md)

- **相关案例**: [adg-dogfooding-search-pipeline](../case-studies/adg-dogfooding-search-pipeline.md)

- **相关案例**: [cli-tool-development](../case-studies/cli-tool-development.md)

- **相关案例**: [web-scraping-tool](../case-studies/web-scraping-tool.md)

- **相关案例**: [code-review](../case-studies/code-review.md)

- **相关案例**: [frontend-performance-optimization](../case-studies/frontend-performance-optimization.md)

- **相关案例**: [intelligent-customer-service](../case-studies/intelligent-customer-service.md)

- **相关案例**: [security-vulnerability-fix](../case-studies/security-vulnerability-fix.md)
