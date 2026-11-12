# ADR-026: Phase 30 .jcode/hooks.json fail-open 检测脚本

## 状态
接受

## 日期
2026-09-01

## 背景

ADR-025 (52b5c64) 移除 fail-open 的 `update-moc` hook。但 hooks.json 里**仍可能**存在其他 fail-open hook,只是暂时未被触发。

为防止类似事件重演,需建立自动化检测机制。

## 决策

### 决策 1: 新增 check_hooks_json_integrity.sh

`tools/scripts/check_hooks_json_integrity.sh` 通过**真跑 hooks_runner** 来发现 fail-open hook:
- 跑 `python .jcode/scripts/hooks_runner.py on_commit --files .adg/rules.yml`
- 跑 `python .jcode/scripts/hooks_runner.py on_merge`
- 解析输出,若任何 hook 的 `[失败]` 行 + 同输出含 `unrecognized arguments` → fail-open 风险
- 退出码 0 (干净) / 1 (有 fail-open)

**设计权衡**: 这比单纯 `--help` 探测更可靠, 因为 `--bogus-arg` 探针会把**所有 argparse 脚本**都误判成 fail-open (实测发现此陷阱)。hooks_runner 真跑更准确。

### 决策 2: 接入 on_commit (条件触发)

`.jcode/hooks.json` 的 `on_commit` 块新增:
```json
{
  "name": "hooks-json-integrity-check",
  "skill": "governance-auditor",
  "action": "check-hooks-json-integrity",
  "description": "提交时验证 .jcode/hooks.json 无 fail-open hook (Phase 30)",
  "command": "bash tools/scripts/check_hooks_json_integrity.sh",
  "condition": "files_contain('.jcode/hooks.json')",
  "enabled": true
}
```

**条件触发** `files_contain('.jcode/hooks.json')` 避免每次 commit 都跑 (实测 ~17 秒), 仅在 hooks.json 改动时跑。

### 决策 3: 接入 on_pr (可选, 未实施)

on_pr 也可加入类似 hook, 但 PR 通常会改 hooks.json 才需验证, 优先级低于 on_commit。

## 后果

### 正面
- 自动化检测 fail-open hook, 防止 update-moc 类 bug 重演
- 反向测试通过: 注入 `link_auditor.py --update-moc` 类型 hook 立即被捕获
- 条件触发避免每次 commit 17 秒开销

### 负面
- hooks.json 改动时 +17 秒 commit 耗时 (可接受, 仅在配置变更时)
- 脚本依赖 hooks_runner 真跑, 改动 hooks_runner 可能影响检测

## 验证

- 干净状态: ✅ on_commit 5/5 通过 (含新 hook)
- 反向测试: 注入 link_auditor.py --update-moc 类 hook → 脚本退出 1 + 提示问题 hook 名
- on_commit 真触发: ✅ `hooks-json-integrity-check` 真跑通 (实测 17s)
