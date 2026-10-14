# AI Task Prioritizer

> CLI 任务优先级排序工具：TDD + AI 驱动开发。

---

## 定位

验证 `docs/learning/tdd|TDD 方法论` 和 `docs/learning/ai-learning-method|AI 驱动学习法`。

## 核心能力

| 功能 | 描述 |
|------|------|
| LLM 评分 | 调用 LLM 对任务打分 (Value / Effort) |
| 优先级排序 | 基于 Value/Effort 比计算优先级分数 |
| 四象限分类 | Quick Win / Major Project / Fill-ins / Thankless |
| CLI 入口 | 支持文件输入和 stdin |

### 四象限模型

```
         High Value
            │
   Major    │  Quick Win
   Project  │  (优先做)
            │
────────────┼────────────
            │
   Thankless│  Fill-ins
   (不做)   │  (有空再做)
            │
         Low Value
```

## 快速开始

```bash
pip install -e .

# 从文件读取任务
python main.py tasks.txt

# 从 stdin 读取
echo -e "任务A\n任务B\n任务C" | python main.py -
```

## LLM 配置

设置环境变量:
```bash
export LLM_API_KEY=your-api-key
export LLM_MODEL=gpt-4o-mini
```

## 测试

```bash
python -m pytest tests/ -v
# 12 tests passed
```

## 相关文档

- [TDD 方法论](../../docs/learning/test-driven-development.md)
- [AI 驱动学习法](../../docs/learning/ai-learning-method.md)
