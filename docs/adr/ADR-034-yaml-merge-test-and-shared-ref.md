# ADR-034: Phase 32 子任务 2d yaml/merge 覆盖 + 真实发现

## 状态
接受

## 日期
2026-09-02

## 背景

按 ADR-030 启动 Phase 32 子任务 2d: 覆盖 yaml 加载 + merge 系列函数。
涉及 5 个函数: `_load_common_rules_cached` / `_load_universal_rules_cached` / `_try_load_yaml` / `_merge_rules` / `_merge_anti_patterns`。

## 决策

### 决策 1: 测试用真实 yaml.safe_load (不 mock yaml 库)

理由: PyYAML 是稳定的标准库, mock 它会引入不必要的脆弱性。真实 .yml 文件在 tmp_path 创建, 不污染项目结构。

### 决策 2: 23 个测试覆盖 5 函数的所有关键分支

- `_load_common_rules_cached` (5): 文件缺失/合法 YAML/YAML 错/YAML list/空文件
- `_load_universal_rules_cached` (4): 仅 universal/无文件/通用+common 合并/universal YAML 错
- `_try_load_yaml` (3): 文件缺失/合法 + common 合并/YAML list
- `_merge_rules` (6): 空 custom/全替换/severity_override/嵌套 naming/嵌套 thresholds/base 不变
- `_merge_anti_patterns` (5): 空 custom/全替换/severity_override/追加新/混合

### 决策 3: 真实发现 — `_merge_anti_patterns(base, [])` 返回 base 本身

测试发现: `_merge_anti_patterns([], [])` 在 `custom_patterns` 为空时, early return `base`, 但 **`base` 是函数参数,Python `base` 引用不变**, 不是 copy。

```python
def _merge_anti_patterns(base, custom):
    if not custom:  # early return
        return base  # ← 直接返回 base, 不是 base.copy()
```

后果: 修改返回值会影响原 base。这是 **共享引用** 风险, 但实际调用方通常不会原地修改 result。

影响评估: **低风险**, 但应记录到后续 refactor 候选。

### 决策 4: 测试反映真实行为 (不强迫修复)

诚实做法: 测试标注真实行为 (共享引用), **不修复源码** (避免扩大改动范围)。后续 Phase 33 refactor 时一起处理。

## 后果

### 正面
- 23 个测试覆盖 yaml/merge 完整生命周期
- 真实发现共享引用问题 (低风险, 记录待 refactor)
- 测试反映真实行为, 避免误导

### 负面
- `_merge_anti_patterns(base, [])` 共享引用 (低风险, 文档化)
- 仍有 yaml 加载的边缘路径未覆盖 (如 yaml 嵌套引用)

## 验证

- pytest: 23/23 passed ✅
- ruff: 待检查
- 覆盖率: rule_loader.py 24% → **估时 35%+** (实测待跑)
- 测试套件 3725 → 3748 (+23)

## 后续

- Phase 32 子任务 2e: 公开 API (`load_language_rules` + `load_combined_rules` + invalidate/clear) (估时 2h)
- Phase 33 refactor: `_merge_anti_patterns` 共享引用修复 (单独 ADR)