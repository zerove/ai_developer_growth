# ADR-025: Phase 30 .adg/rules.yml 完整性 on_merge 双层防护

## 状态
接受

## 日期
2026-09-01

## 背景

ROADMAP Phase 30 候选 3: "`check_rules_yml_integrity.sh` 接入 on_merge, 与 on_commit 双层防护"。

之前 Phase 29 P1 已把完整性脚本接入 on_commit (9959dc8),但 on_merge 仍无保护层。本会话内 .adg/rules.yml 再次被 mutmut 污染的事件(98c5584 之前)证明:单一防护层不够,合并阶段需要独立验证。

## 决策

### 决策 1: on_merge 增加 rules-yml-integrity-check-merge hook

`.jcode/hooks.json` 的 `on_merge` 块新增:
```json
{
  "name": "rules-yml-integrity-check-merge",
  "skill": "governance-auditor",
  "action": "check-rules-yml-integrity",
  "description": "合并后验证 .adg/rules.yml 完整性 (Phase 30, 与 on_commit 双层防护)",
  "command": "bash tools/scripts/check_rules_yml_integrity.sh",
  "enabled": true
}
```

### 决策 2: 双层防护覆盖以下场景

- on_commit 触发 → 提交前验证(Phase 28 事件预防)
- on_merge 触发 → 合并前再次验证(防 on_commit 失败/被跳过)
- 用户手工 git commit 绕过 on_commit → on_merge 是最后一道防线

### 决策 3: 不对 hooks.json 做更多修改

当前 4 个 on_merge hook (update-moc / sync-tools / context-sync-merge / rules-yml-integrity-check-merge) 已足够,不再扩张。

## 后果

### 正面
- 完整性检查覆盖 commit + merge 两个关键节点
- 即使用户绕过 on_commit (手工 git commit),merge 时仍会被 hooks_runner on_merge 阻断
- 真实事件验证: 98c5584 之前的 mutmut 污染就是合并阶段才能被捕获的典型

### 负面
- hooks.json 维护成本微增(现 4 个 on_merge)
- merge hook 跑完需 < 1s (check_rules_yml_integrity.sh 跑 grep 而已)

## 验证

- JSON 合法性: ✅ Python json.load 解析通过
- on_merge hooks 列表: ['update-moc', 'sync-tools', 'context-sync-merge', 'rules-yml-integrity-check-merge']
- 脚本本身: ✅ 18 规则完整
- 正向触发: ✅ `hooks_runner on_merge` 真触发新 hook 并通过

### 额外发现 (不属于本 ADR 范围, 记录待办)

正向触发 on_merge 时暴露另一个真实 bug:
- `update-moc` hook 调用 `tools/scripts/link_auditor.py --update-moc` 但 link_auditor.py 不支持该参数
- link_auditor.py 是只读审计器(只检查链接, 不更新 MOC)
- knowledge-curator 的 update_moc() 函数设计假设错误
- 影响: on_merge 一直 fail-open, 但被 sync-tools / context-sync-merge / 规则完整性检查覆盖
- 修复方向: 移除 update-moc hook (MOC 应有独立 update 脚本) 或修 link_auditor.py 支持 `--update-moc`
- 建议: 进入 Phase 31 候选, 本会话不修 (范围外)