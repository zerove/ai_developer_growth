---
title: 重构策略
description: 代码重构的方法和最佳实践
category: 学习层
tags: [重构, 代码质量, 设计模式]
difficulty: 进阶
reading_time: 12 分钟
updated: 2026-07-21
---

# 重构策略

## 核心原则

重构 = 小步修改 + 保持功能 + 持续测试

## 重构流程

```
识别坏味道 → 设计重构方案 → 小步修改 → 测试验证 → 提交代码
```

## 代码坏味道

### 1. 代码重复

**识别:**
- 相同代码出现多次
- 相似逻辑不同实现

**重构:**
```python
# Before
def calculate_tax(price):
    return price * 0.1

def calculate_discount(price):
    return price * 0.05

# After
def calculate_percentage(price, percentage):
    return price * percentage

def calculate_tax(price):
    return calculate_percentage(price, 0.1)

def calculate_discount(price):
    return calculate_percentage(price, 0.05)
```

### 2. 过长函数

**识别:**
- 函数超过 30 行
- 多层嵌套

**重构:**
```python
# Before
def process_order(order):
    # 50 行代码...

# After
def process_order(order):
    validate_order(order)
    calculate_total(order)
    apply_discount(order)
    save_order(order)
    send_notification(order)
```

### 3. 过大类

**识别:**
- 类超过 300 行
- 职责过多

**重构:**
```python
# Before
class UserManager:
    # 500 行代码...

# After
class UserValidator:
    def validate(self, user): ...

class UserAuthenticator:
    def authenticate(self, user): ...

class UserRepository:
    def save(self, user): ...
```

### 4. 数据泥团

**识别:**
- 多个参数一起出现
- 参数在多处重复

**重构:**
```python
# Before
def create_user(name, email, phone, address):
    ...

# After
class UserInfo:
    def __init__(self, name, email, phone, address):
        self.name = name
        self.email = email
        self.phone = phone
        self.address = address

def create_user(user_info: UserInfo):
    ...
```

## 重构技术

### 1. 提取函数

**原则:**
- 函数只做一件事
- 函数名清晰表达
- 参数不超过 3 个

### 2. 提取类

**原则:**
- 单一职责
- 高内聚低耦合
- 接口清晰

### 3. 内联函数

**适用场景:**
- 函数名不清晰
- 函数只被调用一次
- 函数过于简单

### 4. 移动字段/函数

**原则:**
- 字段/函数应该在正确的位置
- 减少类间依赖

## 重构计划

### 1. 识别重构点

**检查清单:**
- [ ] 代码重复
- [ ] 过长函数
- [ ] 过大类
- [ ] 数据泥团
- [ ] 循环依赖

### 2. 评估优先级

**优先级矩阵:**

| 重构点 | 影响 | 成本 | 优先级 |
|--------|------|------|--------|
| 重复代码 | 高 | 低 | 高 |
| 过长函数 | 中 | 低 | 中 |
| 过大类 | 高 | 高 | 中 |

### 3. 执行重构

**执行原则:**
- 小步修改
- 每步都测试
- 保持功能不变

## AI 辅助重构

```markdown
请帮我重构这段代码:

1. 识别坏味道
2. 设计重构方案
3. 执行重构
4. 验证结果
```

## 案例: 重构实践

### 背景
- 代码重复率: 20%
- 函数平均长度: 50 行
- 测试覆盖率: 60%

### 重构过程
1. 提取重复代码
2. 分解过长函数
3. 优化类结构

### 结果
- 代码重复率: 5%
- 函数平均长度: 20 行
- 测试覆盖率: 85%

---

*最后更新: 2026-07-21*
