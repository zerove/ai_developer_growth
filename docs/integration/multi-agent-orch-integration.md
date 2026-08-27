---
title: 多 Agent 编排集成
description: 如何使用 multi-agent-orch 模拟团队协作开发
category: 工具层
tags: ['AI', 'agent', 'orchestration']
difficulty: 高级
reading_time: 8 分钟
updated: 2026-07-21
---

# 多 Agent 编排集成

> 模拟 PM / Architect / Coder /Reviewer 四角色协作。

---

## 工作模式

### Waterfall 模式
```
PM → Architect → Coder ↔ Reviewer (循环)
```

### Fan-Out 模式
```
并行分配任务给多个 Agent，汇总结果
```

## 四角色 Agent

| 角色 | 职责 | 输入/输出 |
|------|------|----------|
| PM | 需求分析 | 需求 → PRD |
| Architect | 架构设计 | PRD → 架构方案 |
| Coder | 代码实现 | 架构方案 → 代码 |
| Reviewer | 代码审查 | 代码 → PASS/FAIL |

## 快速开始

```bash
cd examples/multi-agent-orch
pip install -e .

# 运行 demo
python demo.py --mode waterfall
python demo.py --mode fan-out
```

## 与知识库集成

- 从 `docs/agent-dev/` 读取 Agent 定义标准
- 从 `AGENTS.md` 读取角色配置
- 输出审查结果到 PR 评论

## 相关资源

- [[../../examples/multi-agent-orch/README|示例代码]]
- [[../agent-dev/workflow-standards|开发流程规范]]

---

*Last Updated: 2026-07-21*
