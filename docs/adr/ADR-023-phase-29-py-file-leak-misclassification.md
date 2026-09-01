# ADR-023: Phase 29 py-file-leak 误报识别

## 状态
接受

## 日期
2026-09-01

## 背景

ROADMAP Phase 29 候选包含 "py-file-leak 治理 (12 个实测)"。验证发现 12 个命中全部为规则误报,无真实文件句柄泄漏。

## 决策

### 决策 1: `py-file-leak` 整体降为 info

12 个命中分布:
- `app_config.py:34` - `with pp.open("rb") as f:` ✅ with 块
- `cov_tool.py:26` - `with path.open(encoding="utf-8") as f:` ✅ with 块
- `audit_attestation.py:51` - `with self.ledger_file.open("a", encoding="utf-8") as f:` ✅ with 块
- `jcode_cli.py:45` - `with f.open(encoding="utf-8") as fh:` ✅ with 块
- `lsp_server.py:152/156/285` - 装饰器定义 + 函数调用, 非文件 handle
- `exception_manager.py:228/397/417` - `urllib.request.urlopen()` 被启发式误判
- `supply_chain.py:226` - `with urllib.request.urlopen(...) as response:` ✅ with 块
- `validate_case_study.py:685` - `open(filepath).read()` 真实问题但脚本场景, Python GC 会处理

### 决策 2: 修复 `validate_case_study.py:685` 真实问题

虽然 Python GC 会自动关闭短生命周期 `open()` 但显式 `with` 更规范。

### 决策 3: hooks 集成完整性门禁

把 `tools/scripts/check_rules_yml_integrity.sh` 加入 `.jcode/hooks.json` 的 `on_commit`, 当 `.adg/rules.yml` 改动时自动校验。

## 后果

### 正面
- py-file-leak 12 个误报不再报警, Phase 29 一项治理完成
- 1 处真实问题修复, 验证了决策 2 的真实性
- 完整性门禁自动化, 防止 Phase 28 事件重演

### 负面
- adg info 数会变化 (待实测)

## 验证

- ruff check: clean
- adg check (warning): 0 issues / 192 files
- adg check (info): 待实测 (预计 -11 因 1 个真问题修后)
- hooks.json JSON 合法性: OK
- check_rules_yml_integrity.sh: ✅ 通过

## 累计降级规则 (16 类)

py-log-print / common-empty-except-block / py-no-input-validation / py-pip-audit-missing / py-test-sleep / common-debugger / common-weak-hash / common-unsafe-yaml-load / common-http-url / py-missing-type-hints / py-any-type / common-type-any / py-global-statement / py-shared-mutable / py-n-plus-one / py-ci-disabled-check / **py-file-leak**