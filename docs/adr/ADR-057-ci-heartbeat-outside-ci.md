# ADR-057: CI 静默失效根因确认 + 心跳检测器必须跑在 CI 之外

## 状态
接受

## 日期
2026-09-29

## 背景

本项目以质量门禁为核心机制（pre-push 门禁、4021 个测试、26 语言规则引擎、38 个 GitHub Actions 工作流），但缺少对**门禁自身存活状态**的检测。

2026-09-29 排查工作流问题时发现：远端 `ci.yml` 自 **2026-09-05** 起即报 `This run likely failed because of a workflow file issue`，且 `jobs` 数量为 **0**，持续 **23 天无人发现**。

### 根因证据链

| 证据 | 观测值 | 推论 |
|------|--------|------|
| `actions/runs/<id>/jobs` | `total_count = 0` | run 存在但从未调度 job |
| `created_at` / `run_started_at` / `updated_at` | 三者同为 `13:55:27Z`（秒级） | 零执行时间，非代码执行失败 |
| `gh workflow list` | 18 个工作流全部 `active` | GitHub 能正常解析工作流文件 |
| actionlint（本地） | 6（9-05 基线）→ 82（修复前）→ **0**（当前） | 工作流文件本身无致命缺陷 |
| 仓库设置 | `enabled=true`, `allowed_actions=all` | 仓库级配置正常 |
| 历史提交 `cf9352f3`（9-05） | 同样 0 job | 症状**早于**本次全部改动 |

结论：仓库为 **private**（`private=true`, owner type `User`），私有仓库 GitHub Actions 消耗账户分钟配额。**配额耗尽时 run 被立即拒绝，不分配 runner、不产生 job**，与全部观测一致。

### 死锁约束

最直觉的方案是新增一个 scheduled GitHub Actions 工作流定期探测 CI 状态。**该方案不可行**：配额耗尽时，scheduled 工作流同样拿不到 runner，会与它要监测的门禁一起死亡，无法检测自身失效。

任何运行在 CI 内的检测器都受此约束。

## 决策

### 决策 1: 检测器必须运行在 CI 之外

心跳检测器以本地 CLI 形式提供（`hooks_runner.py ci-heartbeat`），由开发者手动执行或经 pre-push 门禁触发。pre-push 门禁已在本地运行、不消耗 GitHub 配额，因此它天然能在 CI 死亡时存活。

不将检测器注册为 scheduled workflow——那会制造一个与被检测对象同生共死的组件。

### 决策 2: 检测信号用"0 job + 零执行时间"，而非工作流文件解析

GitHub 对配额拒绝与工作流语法错误给出相同文案（`workflow file issue`），但后者会被 `active` 状态与本地 actionlint 检出。因此检测以 **`total_count == 0` 且 `updated_at == created_at`** 为失效判据，不依赖文案。

### 决策 3: 仅用标准库，不引入新依赖

项目核心依赖为 `pyyaml` + `loguru`，dev 依赖为 pytest/ruff/mypy。GitHub API 调用使用标准库 `urllib.request`，认证读取 `GITHUB_TOKEN` / `GH_TOKEN`；无 token 时降级为**只读本地检查**并明确提示，不静默失败。

### 决策 4: 不引入自动告警通道

告警需外部接收端（issue/邮件/webhook），本项目无稳定通知通道（勘察确认 `tools/scripts/` 下无 notifier 模块）。本次只交付**可执行的检测能力**，告警渠道由后续独立决策引入，避免为未知接收端预建抽象。

## 影响

- 心跳是**主动查询式**而非**被动告警式**：能回答"CI 现在活着吗"，不能做到"CI 死了自动通知你"
- 私有仓库配额耗尽是**长期状态**而非瞬时抖动，恢复后可能积压失败，本心跳可立即确认恢复
- 补齐了治理项目最关键的缺口：机制可以自我质疑其有效性

## 相关

- `tools/scripts/ci_heartbeat.py` — 实现
- `tests/test_ci_heartbeat.py` — 测试
- ADR-038 复杂度治理、ADR-051 total_lines 契约（既有门禁设计）
