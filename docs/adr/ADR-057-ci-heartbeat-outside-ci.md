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

### 决策 4: 告警走 GitHub Issue，按固定标题去重

初版仅交付检测能力，推迟告警（理由：无稳定通知通道，不为未知接收端预建抽象）。经确认后选定 **GitHub Issue** 作为投递通道——项目本身已用 `sync_issues.py` 经 PyGithub 操作 issue，且 Issue 在 GitHub 侧有状态可查，不依赖外部接收端常驻在线。

去重锚点为固定标题 `CI 心跳: 门禁失效`（`ALERT_TITLE`）：

- 失效且无开放告警 → 新建 Issue
- 失效且已有开放告警 → **PATCH 更新正文，不新建**（否则每次心跳刷一条）
- 恢复且有开放告警 → 关闭 Issue，正文标记"已恢复"
- 恢复且无开放告警 → 不动作

告警仅在显式传入 `--alert` 时触发，默认关闭，避免无意间产生写操作。恢复后自动关闭，因此该 Issue 反映的是"当前是否失效"，而非历史事件。

## 影响

- 心跳默认仍是**主动查询式**；加 `--alert`（`make ci-alert`）后兼具被动告警，能做到"CI 死了自动留痕"
- 告警 Issue 的存续即代表失效状态，恢复即自动关闭，无需人工清理
- 私有仓库配额耗尽是**长期状态**而非瞬时抖动，恢复后可能积压失败，本心跳可立即确认恢复
- 补齐了治理项目最关键的缺口：机制可以自我质疑其有效性
- 告警通道本身**不受心跳保护**——若 GitHub API 不可用则无法告警，故仍需保留主动查询手段

## 修订记录

- 2026-11-12: 实测到配额耗尽的**第二种失效形态**并修正检测器。
  此前只判据 `total_count == 0`（run 完全没调度 job）。当天实测：run 会创建出
  **30~35 个 job**，但每个 job 的 `steps` 都是空数组、耗时 1~2 秒、结论 failure ——
  GitHub 在**分配 runner 之前**就拒绝了 run。只看 job 数量的旧检测器因此报
  "✅ CI 正常：最近一次 run 产出 35 个 job"，即**假绿灯**：门禁实际一次都没跑。
  现新增判据"所有 job 的 steps 为空 → 判失效"，并补两条契约测试
  （steps 全空 = 失效；steps 非空 = 存活，即使本次 run 因代码问题失败）。
  同日复核：分支保护 API 返回 `403 Upgrade to GitHub Pro or make this repository
  public to enable this feature.` —— 这是**仓库可见性/套餐限制**（private 仓库的
  分支保护需 GitHub Pro），不是 token 权限问题；在升级套餐或改为 public 之前，
  "required checks" 无法通过 API 配置，属**外部阻塞**，不再重复尝试。

## 相关

- `tools/scripts/ci_heartbeat.py` — 实现
- `tests/test_ci_heartbeat.py` — 测试
- ADR-038 复杂度治理、ADR-051 total_lines 契约（既有门禁设计）
