# ADR-027: Phase 30 双层防护主动拦截 .adg/rules.yml 污染事件

## 状态
接受

## 日期
2026-09-02

## 背景

Phase 30 (52b5c64) 在 on_commit 和 on_merge 都接入了 `check_rules_yml_integrity.sh`, 形成双层防护。本次 session 内**真实触发**了一次防护: 后台跑 pytest + coverage 时, `.adg/rules.yml` 的 `severity_overrides` 段 (65 行) 被丢失, 17 个降级规则 key 全部消失。

## 事件时间线
1. session 期间后台跑 `pytest --cov` (10+ 分钟任务)
2. 期间某个时刻 `.adg/rules.yml` 被覆写丢失 severity_overrides 段
3. 本轮"继续处理"启动时 `git status` 显示 `modified: .adg/rules.yml`
4. `git diff` 确认段全部丢失
5. `bash tools/scripts/check_rules_yml_integrity.sh` 立即捕获并退出 1
6. `git checkout HEAD -- .adg/rules.yml` 恢复成功
7. check_rules_yml_integrity.sh 验证通过 (18 规则完整)

## 决策

### 决策 1: Phase 30 双层防护实测有效

本次事件**真实验证**了 ADR-025 的设计:
- 即使不在 on_commit hook 上下文 (手工 git commit 绕过)
- 即使 on_merge hook 未被调用 (无 PR/merge 操作)
- 只要 dev 跑 `check_rules_yml_integrity.sh`, 就能立即发现污染

### 决策 2: 加入 CHANGELOG/ADR 记录为"首次主动拦截"

这是 Phase 30 设计**首次真实生效**, 应该有正式记录:
- CHANGELOG v2.23.3 节点追加"首次拦截"章节
- ADR-027 即本文件
- ROADMAP Phase 30 收口块加备注 "✅ 已首次拦截污染"

### 决策 3: 推广方案 (待定)

考虑把 `check_rules_yml_integrity.sh` 加入更多触发点:
- pytest conftest.py 自动跑
- pre-commit 钩子(若引入)
- IDE 保存钩子(过重, 跳过)

## 后果

### 正面
- Phase 30 双层防护从"理论设计"变成"实测有效"
- 未来 dev 跑覆盖率/测试时如有污染, 立即被发现
- ADR 验证机制的价值得到证实

### 负面
- 仍需 dev 主动跑 `bash tools/scripts/check_rules_yml_integrity.sh`
- 不能完全自动化(除非 pre-commit 引入, ROI 低, 见 ADR-025)

## 验证

- 真实事件: ✅ `.adg/rules.yml` severity_overrides 段丢失被 check_rules_yml_integrity.sh 立即捕获
- 恢复: ✅ git checkout HEAD -- .adg/rules.yml 一次成功
- 防误判: ✅ 干净状态下脚本通过, 不阻断 workflow

## 推广

新增案例: Phase 30 双层防护在 session 内首次主动拦截, 可作为 ADR 设计决策验证的标准案例。
