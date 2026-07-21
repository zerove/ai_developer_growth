# Prompt 优化器

一个帮助开发者迭代和优化 Prompt 的工具。

## 功能

- Prompt 版本管理
- 自动评估 Prompt 效果
- 对比不同版本的性能
- 生成优化建议

## 使用方法

```python
from src.optimizer import PromptOptimizer, PromptVersion

# 创建优化器
optimizer = PromptOptimizer(prompts_dir="prompts")

# 保存 Prompt 版本
prompt = PromptVersion(
    version="1.0.0",
    template="你是一位代码审查专家。请审查以下代码：\n{code}",
    model="gpt-4",
    score=7.5,
    metadata={
        "examples": ["审查一个简单函数"],
        "constraints": ["输出 JSON 格式"]
    }
)
optimizer.save_prompt("code-review", prompt)

# 列出所有版本
versions = optimizer.list_versions("code-review")

# 对比版本
result = optimizer.compare_versions("code-review", "1.0.0", "2.0.0")

# 生成优化建议
suggestions = optimizer.generate_optimization_suggestions("code-review", "1.0.0")
```

## 测试

```bash
pip install pytest
PYTHONPATH=src pytest tests/ -v
```

## 依赖

- Python 3.10+
- pytest (测试)
