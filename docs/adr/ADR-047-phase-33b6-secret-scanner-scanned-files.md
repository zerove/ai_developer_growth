# ADR-047: Phase 33b-6 secret_scanner scanned_files 字段修复

## 状态
接受

## 日期
2026-09-05

## 背景

`tools/scripts/secret_scanner.py:363` 长期标记 `# TODO: 统计`，`scanned_files` 字段在 `SecretScanResult` 中**硬编码为 0**。

影响:
- SARIF / JSON 报告 `scanned_files` 字段总是 0 (不可信)
- `test_secret_scanner_unit.py:64-70` 已建立契约预期 `scanned_files=10`，但实际 `to_json()` 输出 0
- `test_secret_scanner_round2.py:196` 是占位测试 `assert r.scanned_files == 0` (接受现状)

## 决策

### 决策 1: 基于 path + scan_workspace 计数 (而非外部工具输出)

**不依赖** gitleaks/trufflehog 输出（不可靠且依赖具体实现）。
**纯本地逻辑**:
- `scan_workspace=False` → 0 (其他模式涉及 git 状态，不计数)
- `path` 是文件 → 1
- `path` 是目录 → `rglob("*")` 计数文件数 (排除 `.git/`)

### 决策 2: 抽出 `_count_scanned_files(path, scan_workspace)` 模块级函数

按 V2.21 P5 系列约定: helper 函数模块级, 主函数仅委托.
避免在 `scan()` 主函数内做 glob 计算 (与 CC 治理一致).

### 决策 3: `.git/` 子目录排除

`.git/` 内文件不应被计为用户代码文件.
扫描工具 (gitleaks/trufflehog) 默认排除 `.git/`，本修复与它们语义一致.

## 后果

### 正面
- `scanned_files` 字段真实可信 (不再恒为 0)
- 5 个新测试覆盖边界:
  - 空目录 + tools=[] → 0
  - scan_workspace=False → 0
  - 真实目录 3 文件 → 3
  - `.git/` 排除 → 1 (而非 4)
  - 单文件 → 1
- 与现有 to_json roundtrip 测试契约一致 (test_secret_scanner_unit.py)
- 不破坏现有 `test_no_output_file_still_returns_result` (空目录 + tools=[] 仍 = 0)

### 负面
- 真实工具 (gitleaks/trufflehog/detect-secrets) 报告的扫描文件数可能与本计数器不一致
  (例如 gitleaks 实际扫描所有可读文件, 本计数器仅统计路径下的文件)
- 接受: 工具内部统计不在我们的统计责任范围内

## 验证

- 20/20 test_secret_scanner_round2.py 通过
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题
- lint: All checks passed

## 累计状态

- 47+1=48 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3914+5=3919 tests passed
- 88.03% 总覆盖率
- secret_scanner.py 长期 TODO 已关闭
