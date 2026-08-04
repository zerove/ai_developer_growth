# Capability Radar

> 五维能力雷达图自评工具：基于 `mindset/capability-model` 能力模型。

---

## 定位

验证 `docs/mindset/capability-model|能力模型` 中的五维能力评估体系。

## 五个评估维度

| 维度 | 评估内容 |
|------|----------|
| 问题定义与产品思维 | 从 L0(接收需求) 到 L4(战略洞察) |
| 架构决策与系统设计 | 从 L0(无设计) 到 L4(平台化思维) |
| AI 协作与提示工程 | 从 L0(不用 AI) 到 L4(元能力构建) |
| 工程严谨性与质量 | 从 L0(能跑就行) 到 L4(文化塑造) |
| 学习与知识内化 | 从 L0(依赖 AI) 到 L4(知识创造) |

## 输出

| 格式 | 描述 |
|------|------|
| 终端可视化 | ASCII 雷达图 + 进度条 + 建议 |
| Markdown 报告 | 结构化报告，适合分享 |
| JSON 数据 | 原始分数，适合集成 |

## 快速开始

```bash
pip install -e .

# 交互式评估
python -m capability_radar

# 静默模式 (仅输出摘要)
python -m capability_radar --quiet

# 输出 Markdown 报告
python -m capability_radar --format markdown > report.md
```

## 测试

```bash
python -m pytest tests/ -v
# 10 tests passed
```

## 相关文档

- [[docs/mindset/capability-model|能力模型]]
- [[docs/capability-levels|能力等级定义]]
