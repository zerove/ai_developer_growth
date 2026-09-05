# ADR-043: Phase 33 子任务 33b-1 semantic_rules 纯函数覆盖

## 状态
接受

## 日期
2026-09-05

## 背景

按 ADR-036 Phase 33b 子任务分解启动 33b-1 (semantic_rules 纯函数)。

semantic_rules.py 现状:
- 250 行, 72% 覆盖率, 之前由其他测试间接触发
- 本次为首次专门测试覆盖
- 协议 + 注册表 + 内置规则三段结构

本子任务目标: 覆盖注册表/Protocol 纯函数层, 为后续 33b-2 (rule eval) 与 33b-3 (公开 API) 铺路。

## 决策

### 决策 1: autouse fixture 隔离注册表状态

`_SEMANTIC_RULES` 是模块全局可变状态, 测试间互相污染。
本文件采用 autouse fixture 在每个测试前后重置为内置规则, 保证隔离:

```python
@pytest.fixture(autouse=True)
def _restore_rules_after_test():
    _SEMANTIC_RULES.clear()
    for r in semantic_rules._BUILTIN_SEMANTIC_RULES:
        register_semantic_rule(r)
    yield
    _SEMANTIC_RULES.clear()
    for r in semantic_rules._BUILTIN_SEMANTIC_RULES:
        register_semantic_rule(r)
```

### 决策 2: Protocol 检查使用 hasattr 而非 isinstance

`SemanticRule` 是 `runtime_checkable` Protocol, 但 `isinstance(rule, SemanticRule)` 仅检查方法存在, 不检查类型注解.
用 `hasattr(rule, 'name/languages/check')` 验证协议成员.

### 决策 3: 真实行为测试 (不修复源码)

覆盖过程中未发现需修源码的行为. 测试反映真实的注册表语义:
- `unregister_semantic_rule` 不存在规则 → False (不抛)
- `register_semantic_rule` 同名覆盖 (last-write-wins)
- `list_semantic_rules` 返回 sorted list (稳定快照)

## 后果

### 正面
- 21 测试覆盖纯函数层 (Protocol/注册表/列表元数据)
- 注册表行为锁定, 防止未来重构破坏协议
- 为 33b-2/3 铺路 (rule eval 集成测试)
- autouse fixture 模式可被后续 33b-2/3 复用

### 负面
- semantic_rules.py 整体覆盖率仍 72% (未覆盖 rule eval + run_semantic_rules)
- Protocol runtime_checkable 在 dataclass 上有限制, 部分 isinstance 测试改用 hasattr

## 验证

- 21/21 测试通过 (`test_semantic_rules_pure.py`)
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题
- lint: All checks passed

## 累计状态

- 43+1=44 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3844+21=3865 tests passed
- 87.72% 总覆盖率
- **Phase 33b-1 完成** ✅
- Phase 33b-2 (rule eval) 未启动
- Phase 33b-3 (run_semantic_rules) 未启动