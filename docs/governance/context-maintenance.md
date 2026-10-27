# CONTEXT.md 维护流程

## 概述

`CONTEXT.md` 用滚动窗口（默认最近 5 条更新记录）维护项目近期历史。固定头部（项目定位、状态、术语等）不参与裁剪。

## 为什么是 5 条

2026-10-25 实测 50 条 = 1507 行，其中固定头部 304 行，同步日志占 80%。单条记录约 24 行，50 条即约 1200 行重复的“Git 变更同步”。窗口收敛到 5 条后：

- **体积可控**：约 430 行，会话启动加载不再被日志淹没
- **近期上下文保留**：5 条覆盖最近若干次提交的变更摘要
- **历史不丢**：更早记录仍在 `git log`；关键决策必须迁移到 ADR 永久保留

超过 5 条会被 `context-sync` 自动裁剪，但**只在 on_commit hook 触发时**（手工 `git commit -m` 绕过 hook 会导致漂移）。

## 何时主动收敛

| 触发场景 | 动作 |
|----------|------|
| 累积 ~2 条新更新记录 | 跑 `python .jcode/scripts/context-sync.py sync` |
| 提交前发现 `grep -c "^## 更新记录:" CONTEXT.md` > 5 | 先收敛再 commit |
| 周一周报时 | 强制跑一次（合并多个小改动） |

## 步骤

```bash
# 1. 备份当前 CONTEXT (万一裁剪有意外)
cp CONTEXT.md /tmp/context.before.md

# 2. 跑 context-sync 收敛
python .jcode/scripts/context-sync.py sync --project-root .

# 3. 检查结果
head -3 CONTEXT.md                   # 固定头部仍在
grep -c "^## 更新记录:" CONTEXT.md  # 应 <= 5
git diff CONTEXT.md | head -30      # 应是合理裁剪, 不是整段丢失

# 4. 验证关键决策块未丢失 (按时间戳)
grep "^## 更新记录:" CONTEXT.md | tail -5

# 5. 提交
git add CONTEXT.md
git commit -m "chore(context): 触发 context-sync 收敛 (N → 5 条)"
```

## 保留 vs 裁剪规则

context-sync `_prune_update_entries()` 算法:
- **保留** 最近 `max_update_entries`（默认 5）条更新记录
- **裁剪** 更老的记录（头部 + 5 条最新 = 保留）
- **不动** 任何手动添加的章节（在第一条更新记录之前的内容）

如需临时保留更多，修改 `.jcode/scripts/context-sync.py` 的
`ContextConfig.max_update_entries`（0 = 不限制）。

## 注意事项

- `git commit -m` 绕过 on_commit hook → context-sync 不会自动跑
- 解决: 主动跑或接受 trade-off
- 不装 pre-commit 原因: 与 `.jcode/hooks_runner.py` 重复 + 引入第三方依赖（详见 ADR-025/026）
- 超过 5 条后会被裁剪，关键决策应迁移到 ADR（永久保留）

## 相关 ADR

- ADR-061: 固定头部必须独立于滚动窗口（2026-10-25 修订：默认窗口 50 → 5）
- ADR-022: Phase 28 空 except 治理 + .adg/rules.yml 恢复
- ADR-025: Phase 30 .adg/rules.yml 完整性 on_merge 双层防护
- ADR-026: Phase 30 .jcode/hooks.json fail-open 检测

## 实测统计

| 时点 | 条数 | 文件行数 | 触发原因 |
|------|------|----------|----------|
| 2026-09-01 22:14 | 50 | 1008 | Phase 30 主动收敛 |
| 2026-09-01 23:55 | 51 | 1023 | 本会话 +1 条未收敛 |
| 2026-09-02 00:15 | 52 | 1031 | pyproject version 同步 +1 |
| 2026-09-02 03:21 | 50 | 1024 | 主动收敛（本会话已用） |
| 2026-10-25 | 5 | 见 CONTEXT.md | 默认窗口 50 → 5，按新窗口裁剪 |

## 工具脚本

- `python .jcode/scripts/context-sync.py sync` - 主动收敛
- `python .jcode/scripts/context-sync.py validate` - 验证格式
- `python .jcode/scripts/context-sync.py audit` - 审计规范合规

## 工具位置

```bash
# 文件
ls .jcode/scripts/context-sync.py

# 验证
python -c "
content = open('CONTEXT.md').read()
records = [l for l in content.splitlines() if l.startswith('## 更新记录:')]
print(f'当前: {len(records)} 条')
assert len(records) <= 5, '需要收敛'
"
```
