# Prompt Optimizer

> Prompt 版本管理和自动优化工具。

---

## 定位

验证 `docs/learning/prompt-engineering|Prompt 工程` 中的 Prompt 设计方法论和迭代优化流程。

## 核心能力

| 组件 | 描述 |
|------|------|
| `PromptOptimizer` | Prompt 优化器：模板生成、版本管理、A/B 测试 |
| `PromptVersion` | 版本管理：支持 diff 对比和历史追踪 |

### 优化流程

```
1. 定义 Prompt 模板
   ↓
2. 收集测试用例
   ↓
3. 运行评估 (score_function)
   ↓
4. 分析结果，生成优化建议
   ↓
5. 创建新版本
   ↓
6. A/B 测试对比
```

## 快速开始

```python
from optimizer import PromptOptimizer, PromptVersion

# 创建优化器
opt = PromptOptimizer("templates/")

# 创建初始版本
v1 = opt.create_version(
    template="你是一个{role}，请帮我{task}",
    context={"role": "Python 专家", "task": "review code"}
)

# 优化
v2 = opt.optimize(v1, feedback="更具体地指出问题")
```

## 测试

```bash
python -m pytest tests/ -v
# 6 tests passed
```

## 相关文档

- [[docs/learning/prompt-engineering|Prompt 工程]]
