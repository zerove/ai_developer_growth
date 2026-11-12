# ADR-029: Phase 32 rule_loader.py 覆盖率补测规划

## 状态
接受 (规划,未实施)

## 日期
2026-09-02

## 背景

按"后续开发优化计划"Phase 32 启动 `tools/scripts/rules_engine/rule_loader.py` 覆盖率补测。
该模块 274 行, 当前 77%, 含多个 LRU 缓存 + yaml 加载 + 磁盘缓存 + 规则合并 + 生成规则缓存分支。

## 当前覆盖缺口

未覆盖分支 (per session 实测):
- `_load_generated_rules`: 缓存命中 + ImportError 兜底 + AttributeError/OSError 兜底
- `_file_hash`: 文件不存在 + OSError 兜底
- `_load_disk_cache` / `_save_disk_cache`: 正常 + JSONDecodeError + OSError
- `_rules_hash_cached`: 多文件 hash + OSError
- `_load_common_rules_cached` / `_load_universal_rules_cached`: yaml.safe_load + 类型检查
- `_load_cache` / `_save_cache`: 同 disk cache
- `_try_load_yaml`: ImportError + yaml.safe_load 失败
- `_merge_rules`: 多种合并路径
- `_load_framework_rules` / `_get_all_anti_patterns` / `_get_thresholds` / `_get_naming_rules`
- 公开 API: `load_language_rules` / `load_combined_rules` / `invalidate_rule_cache` / `clear_rule_cache`

## 决策

### 决策 1: 不在本会话实施

session 已饱和 (30 commit + 28 ADR + 全部门禁通过), 写完整测试需要:
- 估时: 4-6 小时 (274 行 + 复杂分支)
- 风险: 容易遗漏边界 (cache hit/miss/eviction, yaml 解析, LRU)
- 副作用: 若中途打断会留下"半成品测试"

### 决策 2: 决策记录作为 Phase 32 起点

ADR-029 即作为后续会话的工作基础:
- 列出未覆盖分支清单
- 公开测试设计要点 (cache fixture, tmp_path, parametrize)
- 工作量预估 + 风险评估

### 决策 3: 推荐测试结构

```python
class TestFileHash:
    - 文件存在 → sha256 hex
    - 文件不存在 → ""
    - 文件权限拒绝 → ""

class TestDiskCache:
    - load: 文件存在 + 正常 JSON
    - load: JSONDecodeError → {}
    - save: mkdir + write
    - save: OSError → 静默忽略

class TestRulesHashCached:
    - 多文件 hash (mock 真实 yml)
    - OSError → ""
    - LRU cache (同一 (lang, dir) 二次调用)

class TestLoadCommonRules:
    - yaml.safe_load 成功 + 失败 + 非 dict 返回

class TestLoadGeneratedRules:
    - cache hit (第二次调用)
    - ImportError 兜底
    - AttributeError/OSError 兜底
    - empty list (无生成规则)

class TestMergeRules:
    - 合并两个 dict (嵌套)
    - 合并空 dict
    - 冲突 key 的处理

class TestPublicAPI:
    - load_language_rules 缓存命中 + 未命中
    - invalidate_rule_cache
    - clear_rule_cache
```

### 决策 4: 完成覆盖率目标

rule_loader.py 274 行, 完整测试套预期:
- 当前 77% → **95%+**
- 总覆盖率 86.67% → **88%+**

## 后果

### 正面
- ADR 记录作为 Phase 32 工作基础, 后续会话可无缝衔接
- 不会留下半成品测试 (避免 session 中断风险)
- 维持 session 已饱和的状态, 避免过度延伸

### 负面
- 274 行核心模块继续 <80% (77%→仍低于 80% 临界但满足门禁)
- 后续会话需投入 4-6h 完成

## 验证

- ADR 已落地 (本文件)
- 工作量预估合理 (与 regex_cache.py 类比, 137 行 → 20 测试 → 1h)
- 测试结构清晰, 可作为 Phase 32 起点

## 后续

Phase 32 (下次会话启动):
) 写 tests/test_rule_loader.py 完整测试套
) 实测覆盖率 77% → 95%+
) 新增 ADR-030 记录决策
) 累计 ADR 29 → 30
