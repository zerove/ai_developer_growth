---
title: Prompt 版本管理与迭代
description: ## 核心观点
category: 效率层
tags: ['AI', 'Python', '测试', 'GPT', 'versioning']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# Prompt 版本管理与迭代

## 核心观点

Prompt 是 AI 时代的新资产。不管理 Prompt，就像不管理代码一样危险。Prompt 需要版本控制、测试、文档化。

---

## 为什么需要版本管理

### 问题

1. **不可重复**: 同样的 Prompt，不同时间效果不同
2. **不可追溯**: 不知道 Prompt 为什么改了
3. **不可协作**: 团队无法共享和复用 Prompt
4. **不可评估**: 不知道哪个版本更好

### 解决方案

```
prompt-versioning/
├── prompts/                    # Prompt 定义
│   ├── code-review/
│   │   ├── v1.0.md            # 版本文件
│   │   ├── v1.1.md
│   │   └── latest.md -> v1.1.md  # 符号链接
│   └── test-generation/
│       ├── v1.0.md
│       └── latest.md
├── evaluations/                # 评估结果
│   ├── code-review-v1.0.json
│   └── code-review-v1.1.json
└── README.md                   # 使用说明
```

---

## Prompt 版本格式

### 基础格式

```yaml
---
version: 1.1.0
author: your-name
date: 2026-07-21
model: gpt-4
tags: [code-review, quality]
changes:
  - v1.0.0 -> v1.1.0: 添加安全检查维度
---

# 代码审查 Prompt

## 角色
你是一位资深的代码审查专家。

## 任务
审查以下代码，从以下维度评估：
1. 代码质量
2. 性能
3. 安全性

## 输入
```python
{code}
```

## 输出格式
请以 JSON 格式输出审查结果。
```

### 高级格式 (带评估)

```yaml
---
version: 1.1.0
model: gpt-4
evaluation:
  score: 8.5
  metrics:
    accuracy: 9.0
    completeness: 8.0
    clarity: 8.5
  test_cases:
    - input: "简单函数"
      expected: "基础审查"
      actual: "基础审查"
      pass: true
    - input: "复杂类"
      expected: "详细审查"
      actual: "详细审查"
      pass: true
---
```

---

## 迭代流程

```
┌─────────────┐
│  1. 设计    │ ← 定义 Prompt 目标和约束
└──────┬──────┘\n       ↓\n┌─────────────┐\n│  2. 编写    │ ← 编写初版 Prompt\n└──────┬──────┘\n       ↓\n┌─────────────┐\n│  3. 测试    │ ← 用测试用例验证\n└──────┬──────┘\n       ↓\n┌─────────────┐\n│  4. 评估    │ ← 量化评估效果\n└──────┬──────┘\n       ↓\n┌─────────────┐\n│  5. 迭代    │ ← 根据结果优化\n└──────┬──────┘\n       ↓\n┌─────────────┐\n│  6. 发布    │ ← 标记新版本\n└─────────────┘
```

---

## 最佳实践

### 1. 命名规范

- **语义化版本**: `v1.2.3` (主版本.次版本.修订)
- **有意义的变更日志**: 每个版本都要说明改了什么
- **标签分类**: 用标签组织 Prompt (如 `code-review`, `test-gen`)

### 2. 评估标准

| 维度 | 权重 | 评估方法 |
|------|------|----------|
| 准确性 | 40% | 与预期输出对比 |
| 完整性 | 30% | 是否覆盖所有要求 |
| 清晰度 | 20% | 输出是否清晰易懂 |
| 效率 | 10% | Token 使用量 |

### 3. 团队协作

- **共享 Prompt 库**: 建立团队 Prompt 仓库
- **代码审查**: Prompt 变更也需要审查
- **文档化**: 记录设计决策和迭代原因

---

## 工具推荐

| 工具 | 用途 | 优势 |
|------|------|------|
| Git | 版本控制 | 标准工具，集成好 |
| PromptFlow | Prompt 管理 | 微软出品，功能全 |
| LangSmith | Prompt 追踪 | 与 LangChain 集成 |
| 自建 YAML | 轻量管理 | 简单灵活 |

---

## 代码示例

```python
import yaml
from pathlib import Path\n\n\nclass PromptManager:\n    \"\"\"Prompt 版本管理器\"\"\"\n    \n    def __init__(self, prompts_dir: str = \"prompts\"):\n        self.prompts_dir = Path(prompts_dir)\n    \n    def load(self, name: str, version: str = \"latest\") -> dict:\n        \"\"\"加载 Prompt\"\"\"\n        prompt_file = self.prompts_dir / name / f\"{version}.md\"\n        if not prompt_file.exists():\n            raise FileNotFoundError(f\"Prompt not found: {name}/{version}\")\n        \n        content = prompt_file.read_text()\n        # 解析 YAML frontmatter\n        if content.startswith(\"---\"):\n            _, metadata, template = content.split(\"---\", 2)\n            return {\n                \"metadata\": yaml.safe_load(metadata),\n                \"template\": template.strip()\n            }\n        return {\"metadata\": {}, \"template\": content}\n    \n    def list_versions(self, name: str) -> list[str]:\n        \"\"\"列出所有版本\"\"\"\n        prompt_dir = self.prompts_dir / name\n        return sorted([\n            f.stem for f in prompt_dir.glob(\"v*.md\")\n        ])\n\n\n# 使用示例\nmanager = PromptManager()\nprompt = manager.load(\"code-review\", \"v1.1.0\")\nprint(prompt[\"metadata\"][\"version\"])  # 1.1.0\nprint(prompt[\"template\"])  # Prompt 内容\n```

---

## 相关资源

- [[docs/learning/prompt-engineering|Prompt 工程]] - Prompt 设计技巧
- [[docs/efficiency/full-cycle-workflow|全周期工作流]] - Prompt 在开发流程中的位置

---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]
