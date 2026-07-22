---
title: AI 辅助测试策略
description: ## 核心观点
category: 效率层
tags: ['AI', 'Python', '测试', 'testing', 'ai']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# AI 辅助测试策略

## 核心观点

AI 不是替代测试人员，而是**提升测试效率**。正确的策略是：人负责设计测试策略，AI 负责生成测试用例和执行测试。

---

## 测试策略分层

```
                    ┌─────────────────┐
                    │   E2E 测试      │ ← 人工设计关键场景
                    │   (10%)         │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   集成测试      │ ← AI 生成 + 人工审核
                    │   (30%)         │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   单元测试      │ ← AI 自动生成
                    │   (60%)         │
                    └─────────────────┘
```

---

## AI 测试应用场景

### 场景一：测试用例生成

**输入**: 函数代码 + 需求文档
**输出**: 测试用例集合

```python
# 原始函数
def calculate_discount(price: float, user_type: str) -> float:
    """计算折扣价格"""
    if user_type == "vip":
        return price * 0.8
    elif user_type == "member":
        return price * 0.9
    return price

# AI 生成的测试用例
def test_calculate_discount_vip():
    assert calculate_discount(100, "vip") == 80.0

def test_calculate_discount_member():
    assert calculate_discount(100, "member") == 90.0

def test_calculate_discount_regular():
    assert calculate_discount(100, "regular") == 100.0

def test_calculate_discount_edge_cases():
    assert calculate_discount(0, "vip") == 0.0
    assert calculate_discount(-100, "vip") == -80.0
    assert calculate_discount(100, "") == 100.0
```

### 场景二：边界条件发现

**AI 能力**: 识别代码中的边界条件和异常路径。

```python
# AI 提示的边界条件
# 1. 负数价格
# 2. 空字符串用户类型
# 3. 未知用户类型
# 4. 浮点数精度问题
# 5. 并发调用
```

### 场景三：测试数据生成

**应用**: 生成符合约束的测试数据。

```python
# AI 生成的测试数据
user_fixtures = [
    {"name": "张三", "age": 25, "email": "zhangsan@example.com"},
    {"name": "李四", "age": 0, "email": "lisi@example.com"},  # 边界: 最小年龄
    {"name": "王五", "age": 150, "email": "wangwu@example.com"},  # 边界: 最大年龄
    {"name": "", "age": 25, "email": ""},  # 边界: 空字符串
    {"name": "赵六", "age": -1, "email": "zhaoliu@example.com"},  # 边界: 负数
]
```

### 场景四：回归测试选择

**应用**: 根据代码变更选择需要运行的测试。

```python
# AI 分析代码变更，推荐测试范围
def select_tests_for_change(changed_files: list[str]) -> list[str]:
    """根据变更文件选择测试"""
    # AI 分析依赖关系，返回最小测试集
    pass
```

---

## 最佳实践

### 1. 分层测试策略

| 测试类型 | AI 角色 | 人工角色 | 覆盖率目标 |
|----------|---------|----------|------------|
| 单元测试 | 生成测试用例 | 审核和补充 | 80%+ |
| 集成测试 | 生成测试场景 | 设计测试策略 | 60%+ |
| E2E 测试 | 辅助脚本编写 | 设计关键路径 | 30%+ |

### 2. 测试质量保障

- **覆盖率**: 关注分支覆盖，不只行覆盖
- **变异测试**: 用 mutmut 检测测试有效性
- **代码审查**: AI 生成的测试也要人工审核

### 3. 测试维护

- **定期清理**: 删除过时的测试
- **重构测试**: 保持测试代码质量
- **文档化**: 记录测试策略和设计决策

---

## 工具推荐

| 工具 | 用途 | 优势 |
|------|------|------|
| GitHub Copilot | 测试生成 | 与 IDE 集成好 |
| Cursor | 测试生成 + 审查 | 上下文理解强 |
| pytest-cov | 覆盖率 | 与 pytest 集成 |
| mutmut | 变异测试 | 检测测试有效性 |
| hypothesis | 属性测试 | 自动发现边界条件 |

---

## 常见问题

### Q: AI 生成的测试能直接用吗？

**A**: 不能直接用，需要：
1. 审核测试逻辑是否正确
2. 补充边界条件和异常场景
3. 确保测试可重复执行
4. 添加有意义的断言

### Q: 如何衡量 AI 测试效率？

**A**: 关注指标：
- 测试生成速度 (测试用例/小时)
- 测试通过率 (首次生成)
- 缺陷发现率 (AI vs 人工)
- 维护成本 (测试更新频率)

---

## 相关资源

- [[docs/efficiency/full-cycle-workflow|全周期工作流]] - 测试在开发流程中的位置
- [[docs/learning/prompt-engineering|Prompt 工程]] - 写好测试生成的 Prompt

---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]
