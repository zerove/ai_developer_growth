---
title: 修正循环集成
description: 如何使用 self-correction-loop 实现 AI 自动修复
category: 集成
tags: ['AI', 'automation', 'bugfix']
difficulty: 中级
reading_time: 8 分钟
updated: 2026-07-21
---

# 修正循环集成

> 验证 → 重试 → 修正的 AI 代码质量保证闭环。

---

## 核心流程

```
1. 运行测试
   ↓ (失败)
2. 获取错误信息
   ↓
3. AI 分析错误原因
   ↓
4. 生成修复方案
   ↓
5. 应用修复
   ↓
6. 回到步骤 1
   ↓ (成功或达到最大重试次数)
7. 返回最终结果
```

## 组件

| 组件 | 描述 |
|------|------|
| `CorrectionLoop` | 主循环控制器 |
| `Strategies` | 修复策略 (语法/类型/逻辑/测试驱动) |
| `Runner` | 测试运行器 (unittest/pytest) |
| `Results` | 结果追踪和历史记录 |

## 使用方式

```python
from src.runner import CorrectionLoop
from src.strategies import SyntaxFixStrategy, TypeFixStrategy

loop = CorrectionLoop(
    strategies=[SyntaxFixStrategy(), TypeFixStrategy()],
    max_retries=5
)

result = loop.run("path/to/file.py")
print(f"成功: {result.succeeded}, 尝试次数: {result.attempts}")
```

## CLI 使用

```bash
cd examples/self-correction-loop
python runner.py <target_file> --max-retries 5
```

## 与知识库集成

- 参考 `efficiency/automated-bugfix` 方法论
- 集成到 CI/CD 工作流
- 修复历史记录到 `correction_history.json`

## 相关资源

- [[examples/self-correction-loop|示例代码]]
- [[efficiency/automated-bugfix|自动化 Bug 修复]]
- [[efficiency/full-cycle-workflow|全周期工作流]]

---

*Last Updated: 2026-07-21*
