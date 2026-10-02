# ADR-060: adr_generator 必须能在非交互环境工作

## 状态
接受

## 日期
2026-10-01

## 背景

`community-catalyst` 的 `generate-adr` 动作在自动化下**必然失败**（退出码 1）。
链路如下：

1. `community-catalyst.generate_adr()` 调用 `adr_generator.py --pr <ref>`
2. `adr_generator.py` 此前**完全没有参数解析**——没有 `sys.argv`、没有 `add_argument`，
   `--pr` 被静默丢弃
3. `main()` 第一行就是 `input("选择模式 (1=交互, 2=LLM自动生成, 默认 2): ")`
4. hook / CI / 管道等非 TTY 环境下 `input()` 抛 `EOFError` → 退出码 1

同时发现两个相邻缺陷：

- `save_adr()` 用 `len(existing) + 1` 推导序号，序号有缺口时会撞名并**静默覆盖**
  （只有 `ADR-001` 与 `ADR-005` 时，`len=2` → 写出 `ADR-003`）
- 文件名 slug 用 `title.replace(' ', '_')`，标题含 `:` 时直接进文件名
  （Windows 与 zip 不接受该字符）

## 决策

**`adr_generator.py` 改为"交互可选"的 CLI：所有提问路径都经 `_prompt()`，
仅在 `sys.stdin.isatty()` 为真时才真正调用 `input()`。**

新增参数：`--pr` / `--title` / `--brief` / `--interactive` / `--dry-run` / `--adr-dir`。
非交互且缺少 `--title` 时**明确报错退出 1**，不再抛栈。

配套修正：

- 序号取**最大值 + 1**（`_next_adr_index`），而非数量 + 1
- 文件名只保留 `[A-Za-z0-9_-]`（`_slugify`），与仓库既有 `ADR-0xx-slug.md` 连字符命名一致
- 写文件用 `"x"` 模式并带后缀守卫，绝不覆盖既有文件
- `community-catalyst._resolve_title()` 从 PR 引用解析标题（`gh pr view` → `git log -1 --format=%s`
  → 通用标题），使 `--title` 始终可用

## 理由

1. **hook 与 CI 是非交互环境，交互式 CLI 在其中本就不该被调用。**
   正确做法不是"让 hook 绕开它"，而是让工具在被自动化调用时具备确定的非交互行为。
   这与 ADR-057 的结论一致：门禁自身要能在 CI 这种非交互环境里工作。

2. **静默丢弃 `--pr` 比报错更糟。** 传参传了却不生效，会让调用方以为 PR 上下文已带入，
   生成的 ADR 实际缺失关联变更——这是"看起来在工作"的一类缺陷。

3. **序号推导必须抗缺口。** ADR 编号会因删除/合并产生缺口，用数量推算等于假设
   编号连续，这个假设在真实仓库里不成立。

4. **文件名跨平台安全是硬要求。** 冒号进入文件名在 Windows 上直接非法，
   会让 ADR 生成在部分环境静默失败。

## 后果

- `adr_generator.py` 覆盖率 90%（131 语句 / 26 分支），34 个测试守护，
  关键行为均经变异验证
- 交互体验不变：真实终端下 `isatty()` 为真，提问照旧
- 既有 7 个测试因契约变更而更新（改为传显式 argv、强制 `_interactive` 为真、
  文件名断言改为连字符）——**未删除任何测试**
- LLM 不可用且无 TTY 时，工具**失败退出 1** 而非回退到交互，避免在 CI 中静默生成空 ADR

## 关联

- [[docs/adr/ADR-058-context-sync-dual-implementation|ADR-058]]（context-sync 双实现：无网络无 LLM 约束）
- [[docs/adr/ADR-057-ci-heartbeat-outside-ci|ADR-057]]（门禁自身须能在非交互环境自检）
- [[docs/adr/ADR-059-security-patterns-dual-implementation|ADR-059]]（安全模式双实现）
