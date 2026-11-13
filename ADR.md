# 架构决策记录 (ADR)

> **权威索引**: [docs/adr/ADR.md](docs/adr/ADR.md)
>
> 该索引由 `tools/scripts/generate_adr_index.py` 从 `docs/adr/ADR-*.md`
> 自动生成，提交时由 pre-commit 钩子 `validate-adr-index` 校验一致性
> （`python -m tools.scripts.generate_adr_index --check`）。
>
> 本文件此前手工维护了一份重复的索引表，并自 2026-10-02（ADR-061）后
> 再未更新，累积缺失 ADR-062 至 ADR-078 共 17 条记录。手工表必然持续
> 漂移 —— 这正是 `generate_adr_index.py` 被引入要解决的问题，因此改为
> 单一数据源，本文件仅保留指针。

---

## 索引

见 [docs/adr/ADR.md](docs/adr/ADR.md)。

## 格式约定

单篇 ADR 文件（`docs/adr/ADR-XXX-<slug>.md`）的结构：

- 标题: ADR-XXX: 简短描述
- 状态: 接受 / 废弃 / 替代
- 背景: 决策背景
- 决策: 具体决策
- 后果: 正面 / 负面影响

## 历史注记

- ADR 编号 006 为历史空号（已删除但未复用）。
- ADR 编号 040 为 2026-10-02 追补（33a-2 工作已完成，决策记录当时未落盘）。

---

相关文档: [CONTEXT.md](CONTEXT.md) · [GOVERNANCE.md](GOVERNANCE.md) ·
[docs/agent-dev/context-management.md](docs/agent-dev/context-management.md)
