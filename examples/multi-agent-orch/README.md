# Multi-Agent Orchestration

> 模拟团队开发：PM / Architect / Coder /Reviewer 四角色协作编排。

---

## 定位

验证 `docs/agent-dev/workflow-standards` 中的多 Agent 协作开发流程和 `AGENTS.md` 中的 Agent 定义标准。

## 核心能力

| 模式 | 描述 |
|------|------|
| **Waterfall** | 瀑布式：PM → Architect → Coder ↔ Reviewer (循环) |
| **Fan-Out** | 扇出式：并行分配任务给多个 Agent，汇总结果 |

### 四角色 Agent

| 角色 | 职责 | 输入/输出 |
|------|------|----------|
| PM | 需求分析，生成设计文档 | 需求 → PRD |
| Architect | 架构设计，技术选型 | PRD → 架构方案 |
| Coder | 代码实现 | 架构方案 → 代码 |
| Reviewer | 代码审查，质量把关 | 代码 → PASS/FAIL + 反馈 |

## 快速开始

```bash
pip install -e .

# 运行 demo
python demo.py --mode waterfall
python demo.py --mode fan-out
```

## 技术栈

- 结构化消息传递协议
- 共享上下文管理
- 迭代优化循环 (Coder ↔ Reviewer)

## 测试

```bash
python -m pytest tests/ -v
```

## 相关文档

- [[docs/agent-dev/workflow-standards|开发流程规范]]
- [[AGENTS|Agent 定义索引]]
