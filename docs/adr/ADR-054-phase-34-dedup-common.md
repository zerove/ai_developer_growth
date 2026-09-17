# ADR-054: Phase 34 跨文件重复函数抽取至 _common.py

## 状态
接受

## 日期
2026-09-15

## 背景

ADR-038 复盘指出 rules_engine 工具链存在**同构函数重复**（如 `_child_by_type`/`_find_first`/`_node_text`/`_load_cache`/`_merge_anti_patterns` 在多个文件中手抄拷贝），违反 DRY，且 bug 修复无法一次生效（如 ADR-034 的 `_merge_anti_patterns` 副本语义修复只落在 rule_loader，pipeline 仍是旧版）。

按 ADR 结构与背景对齐原则，采用 **Phase 33b 同款机器级流程**：TDD 先行 → 共享实现落入 `tools/scripts/_common.py` → 消费文件以 import 别名收敛（不动调用点）→ 每 Phase 收口验证。

## 决策

### 决策 1: 8 个共享函数 + 1 个 mixin 落入 `_common.py`

| 共享实现 | 消费方（删除的重复定义） |
|---|---|
| `child_by_type` | csharp/go/java/kotlin/php/ruby/rust/swift/typescript 9 个 parser |
| `find_first` | go/php/typescript parser |
| `find_first_at_depth` | rust/typescript parser |
| `node_text` | 9 个 parser（统一变体2 None-safe node + 变体3 None-safe text） |
| `merge_anti_patterns` | rule_loader / pipeline / cli |
| `load_cache` / `save_cache` | rule_loader / cli / validate_language_rules / update_ai_tool_matrix |
| `detect_language_from_file`（别名 = `detect_language`） | detect_language / pipeline |
| `SeverityCountsMixin`（error/warning/info count 属性） | rules/models.py + rules_engine/models.py 3 个类 |

消费文件全部改为 **`from tools.scripts._common import X` 或 `import X as _X` 别名**，函数签名与方法封装层保留，内部 1 行委托。

### 决策 2: `merge_anti_patterns` 以 ADR-034 修复版为准

rule_loader 的修复版（custom 为空时返回 `list(base)` 副本，防止调用方篡改基线规则）作为唯一规范实现；**pipeline 顺带获得该修复**（原为无早返回的旧版）。副本语义注释保留。

### 决策 3: `_file_hash` → `file_hash_full as _file_hash`

rule_loader 的 `_file_hash`（失败返回 `""`，成功 64 位 hex）与 `_common.file_hash_full` 语义等价，收敛为别名；`rules_engine/rules_hash.py` 的 `file_hash_full` 已是唯一真源。

### 决策 4: `detect_language_from_file` = `detect_language` 别名

detect_language.py / pipeline.py 的封装逻辑（`EXTENSION_MAP.get(filepath.suffix.lower())`）逐行一致，直接别名。pipeline 中的本地 `EXTENSION_MAP` dict 保留（其他函数仍引用，且与 _common 版键集一致）。

### 决策 5: `parse` 不抽取（参数化风险 > 收益）

7 个 parser 的 `parse` 变体含**各语言专属的 `_handled_methods`/`_handled_functions` 去重状态**与 `_walk` 签名差异，参数化需 5+ 个开关参数且行为分支交错，权衡后**不抽取**，仅 ADR 记录。

### 决策 6: `adg_cli/detect.py::_load_yaml` 保留本地

非跨文件重复（唯一含 PyYAML 可选依赖离线 fallback 的实现），不收敛，仅 ADR 记录。

### 决策 7: `save_cache` 统一 plain 版（有意微差）

统一为 `json.dumps(data)` + `FileIO` 写入：validate_language_rules 丢弃 `log.debug`（日志细节不属缓存契约）、update_ai_tool_matrix 丢弃 `indent=2`（缓存文件无需人工可读）。`load_cache` 统一捕获 `FileNotFoundError`/`JSONDecodeError` 返回 `{}`（update_ai_tool_matrix 额外容忍 OSError，语义超集，保留为消费方特性）。

### 决策 8: 显式 re-export 适配 `strict=true`

`pip` 迁移后 mypy `strict`（`no_implicit_reexport`）要求：pipeline.py 中 `detect_language_from_file` 以 **`as detect_language_from_file` 自体别名**显式 re-export（cli.py/__init__.py/validate_language_rules.py 均从 pipeline 导入此名）；rule_loader 的 re-export 别名加 `# noqa: F401`。

## 后果

### 正面
- **DRY**: 19 个消费文件净删 **240 行**重复实现（317 删 - 77 增），规范实现仅 132 行（`_common.py`）
- **修复一次生效**: 未来共享逻辑改动只需改 `_common.py`，不再有"修了 A 漏了 B"
- **pipeline 获得 ADR-034 副本语义修复**（旧版潜在基线篡改风险消除）
- **TDD 锁定**: test_common.py 新增 193 行 / 64 个测试覆盖全部共享实现及边界（空 custom、副本隔离、缓存损坏、None node/text、mixin 计数）
- **测试量**: 3997 passed（全量）

### 负面
- import 块变多（ruff isort 默认 `combine-as-imports=false` 拆分别名块），文件头部略冗余
- update_ai_tool_matrix `_save_cache` 丢失 `indent=2`（缓存为机器可读，可接受）
- validate_language_rules `_save_cache` 丢失 `log.debug`（有意）

## 验证

- `pytest tests/test_common.py`: **64 passed**
- mypy `tools/scripts/`: **0 issues / 192 files**（决策 8 修复后）
- ruff check / format: 本次改动文件全过；仅 3 个测试文件 I001/2 个 format 为 **HEAD 基线与本地 ruff 版本漂移**（`git show HEAD:file` 复现），非本次引入
- adg check: **0 issues / 192 files**
- 全量 pytest: **3997 passed, 4 failed — 全部预存/环境，非回归**：
  - `test_skips_skipped_results`: HEAD 基线即失败（ADR-053 改行为后断言未同步）
  - 3 个 link_auditor 测试: 工作区 `.opencode/session-state.md`（gitignore 运行时产物）被误认为断链，HEAD 基线通过
- 回归敏感抽查：rule_loader 41+223 / cli 61 / pipeline 204 / parsers 142+87 / 5 脚本 71+42 / models 7 全过

## 累计状态

- 54 ADR（含本 ADR）
- 64 个共享函数测试新增
- 240 行消费方重复净删
- 全量 3997 tests passed（4 预存失败待另行处理）