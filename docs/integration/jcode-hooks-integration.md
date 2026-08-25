# ADG × Jcode Agent：生命周期钩子集成

> 把 ADG 治理能力挂进 Jcode agent 的工具调用生命周期，在合适的节点自动触发对应检查。

## 钩子节点与功能映射

| Jcode 事件 | 时机 | 集成功能 | 行为 |
|-----------|------|---------|------|
| `pre_tool` | Edit/Write 等写文件工具**执行前** | ADG error 级语义检查 | 检出硬编码密钥/eval 注入等 → **阻断写入**，规则反馈回传给模型自行修正（fail-open，钩子异常不阻塞） |
| `post_tool` | 写文件工具执行后 | ADG 快速检查 | 异步记录检查结果到目标项目 `.adg-hook.log`，不阻塞 |
| `turn_end` | 一轮对话结束 | （可扩展）质量摘要 | 预留 |
| git pre-commit/pre-push | 提交/推送时 | hooks_runner 全链门禁 | 已有，见 `.jcode/hooks.json` |

## 安装

```bash
# 脚本已装至 ~/bin/jcode-adg-{pre,post}-tool
# ~/.jcode/config.toml
[hooks]
pre_tool = "~/bin/jcode-adg-pre-tool"
post_tool = "~/bin/jcode-adg-post-tool"
pre_tool_timeout_ms = 5000
```

## 工作原理

- **pre_tool 门禁**：stdin 收到工具输入 JSON → 提取 `file_path` → 只查受管语言
  （py/go/rs/java/ts/js/rb/kt/cs）→ 单文件 error 级检查（4s 上限）→
  exit 2 阻断并把规则名+行号+建议写到 stderr，Jcode 将其作为工具错误回传给模型。
- **post_tool 观察者**：fire-and-forget，只对被改的单个文件跑检查（20s 超时），
  结果追加到项目根 `.adg-hook.log`。
- **ADG 定位**：优先用会话 cwd 内的治理设施，回退 `~/dev/ai_developer_growth`；
  都没有则静默跳过。

## 与其他集成的关系

- 项目级 `.jcode/hooks.json`（hooks_runner）：管 git 提交/PR 门禁。
- 本文档的 `~/.jcode/config.toml`：管 agent 工具调用实时门禁。
- 两者互补：前者保证入库质量，后者把问题拦截在"写盘之前"。


## turn_end 会话质量摘要钩子 (2026-08-25)

`~/bin/jcode-adg-turn-end`：观察者钩子（fire-and-forget，永不阻断）。

| 项 | 值 |
|---|---|
| 触发 | 每次 turn_end 事件 |
| 输出 | `~/.local/state/adg/turn-summaries.jsonl` |
| 字段 | ts/session/project/status/duration_ms/model/assistant_chars/last_reply_head |
| 用途 | N3 门禁观察调优的数据源之一；按项目聚合会话质量趋势 |

配置（`~/.jcode/config.toml` `[hooks]` 段）：

```toml
turn_end = "~/bin/jcode-adg-turn-end"
```

实测：turn_end 事件正确落盘 JSONL；session_start/post_tool 事件被过滤零写入。
