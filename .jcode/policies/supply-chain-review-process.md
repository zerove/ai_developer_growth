# Supply Chain License Review 周期盘点流程（可审计）

## 目标
- 对 `license_review` 待复核项进行持续跟踪与处置，避免“待复核债务”静默增长。
- 通过台账（ledger）+ 清单（checklist）+ 处置记录（dispositions）形成可审计证据链。

## 标准输入/产物
- 策略：`.jcode/policies/supply-chain-policy.yaml`
- 处置状态流转：`.jcode/policies/supply-chain-review-dispositions.yaml`（参考 `*.example.yaml`）
- 已知可接受豁免：`.jcode/policies/supply-chain-review-allowlist.json`（参考 `*.example.json`，可选）
- 基线台账：`artifacts/supply-chain/license-review-ledger.baseline.json`（建议周期归档）
- 本次产物（CI/本地归档）：
  - Ledger: `artifacts/supply-chain/license-review-ledger.json`
  - Checklist: `artifacts/supply-chain/license-review-checklist.md`

## 周期执行（建议）
- 频率：每周定时 + 依赖/策略变更时手动触发。
- CI 工作流：`.github/workflows/supply-chain-review.yml`（产出并上传 artifacts）。
- 本地执行示例：
  ```bash
  mkdir -p artifacts/supply-chain
  .venv/bin/python -m tools.scripts.hooks_runner supply-chain compliance \
    --path . --format json \
    --policy-file .jcode/policies/supply-chain-policy.yaml \
    --review-dispositions .jcode/policies/supply-chain-review-dispositions.yaml \
    --review-allowlist .jcode/policies/supply-chain-review-allowlist.json \
    --review-ledger-baseline artifacts/supply-chain/license-review-ledger.baseline.json \
    --review-ledger artifacts/supply-chain/license-review-ledger.json \
    --review-checklist artifacts/supply-chain/license-review-checklist.md \
    --fail-on-review-new
  ```

## 状态与 SLA/Owner 约束
- `status`：`pending` / `in_progress` / `waived` / `accepted` / `resolved`
- 约束（由 checklist/ledger `sla` 汇总可审计）：
  - `owner_missing`：待复核项未指定责任人
  - `sla_missing`：待复核项未指定 `due_at`
  - `sla_overdue`：`due_at` 已逾期（按 UTC 日期）
- 建议：所有非终态待复核项必须具备 `owner` 与 `due_at`，并关联 `ticket`。

## 审计与归档
- 每次周期盘点保留 ledger/checklist artifacts（含 diff 与状态汇总）。
- 基线更新需走评审：仅在待复核项经确认处置/豁免后更新 baseline，避免掩盖新增债务。
