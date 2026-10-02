# ADR-058: context-sync 双实现并存是刻意设计，不做合并

## 状态
接受

## 日期
2026-10-01

## 背景

治理资产审计发现 `context-sync` 存在两套独立实现，且被文档同时列为"权威"：

| 位置 | 规模 | 测试 | 外部依赖 |
|------|------|------|----------|
| `.jcode/scripts/context-sync.py` | 499 行 | **0 个** | 无（纯正则 + Git + subprocess） |
| `examples/ai-context-sync/src/` | 49 文件 / 4035 行 | 55 文件 / 7563 行 / 398 用例 | LLM、HTTP、MCP、向量检索 |

两者共享 6 个同名概念（`ContextSlicer`、`ArchitectureGuard`、`TestRunner`、
`ParallelExecutor`、`ContextSynthesizer`、`GitAnalyzer`），但**同名类的实现不同**：

- `ContextSynthesizer`：`.jcode` 版用正则裁剪 + `guard_no_diff_raw`；examples 版走 LLM 调用并带 `@retry_on_failure`
- `GitAnalyzer`：`.jcode` 版自行解析 diff；examples 版依赖 `unidiff` + `get_last_commit_diff`

审计一度把 `.jcode/scripts/context-sync.py`（499 行）判为"examples 版的副本，应删除"。

### 调用方约束

`.jcode` 版由 5 个 hook 直接驱动：

| 事件 | hook |
|------|------|
| `on_commit` | `context-sync` |
| `on_merge` | `context-sync-merge` |
| `on_pr` | `context-audit` |
| `scheduled` | `weekly-context-sync`、`monthly-spec-audit` |

即**每次提交、每次合并**都会执行。

## 决策

**保留两套实现，不合并。** `.jcode` 版与 examples 版是不同契约下的两个产品，不存在"谁是副本"的问题。

### 理由

1. **执行环境契约不同（决定性理由）**
   `.jcode` 版运行在 git hook 里：无 `OPENAI_API_KEY`、无网络、必须毫秒级且确定性可复现。
   examples 版的核心能力是 LLM 驱动的上下文合成与 MCP 服务。
   用 examples 版替换 `.jcode` 版，会让**每次 commit 都依赖 API key 并产生网络调用与费用**——这是能力回退，不是优化。

2. **测试覆盖完全倒挂**
   examples 版有 398 个用例；`.jcode` 版 0 个。
   在没有为 `.jcode` 版补测试之前合并，等于把有测试的实现换成没测试的薄封装，风险远大于收益。

3. **两者都在被真实使用**
   `.jcode` 版有 5 个 hook 调用方，examples 版是仓库旗舰示例项目（README 与 docs/adr 均引用）。删除任一方都会破坏真实功能。

### 后续要求（不在本 ADR 范围）

`.jcode` 版的**唯一真实缺陷是零测试覆盖**。正确治理动作是补测试，而非合并或删除。
在补测试之前，任何以"消除重复"为名的合并都会降低而非提升质量。

## 后果

- 审计规则更新：跨目录同名类**不自动判为重复**。判定重复需同时满足：无外部依赖差异、无测试覆盖差异、且一方无调用方。
- `agents/context-sync.md` 描述的是 `.jcode` 版 CLI 契约，`examples/ai-context-sync/README.md` 描述的是 examples 版，两者均有效，不得合并表述。

## 关联

- 审计发现来源：治理资产全面审计（2026-10-01）
- 同批次决策：[[docs/adr/ADR-057-ci-heartbeat-outside-ci|ADR-057]]（心跳检测器必须跑在 CI 之外）——同属"看似冗余实则必要的重复"
