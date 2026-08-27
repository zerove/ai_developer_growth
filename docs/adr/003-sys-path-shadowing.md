# ADR-003: 防范 sys.path 顺序导致的模块遮蔽

**状态**: 已废弃（v2.13.2 根因消除，扁平模块已删）
**日期**: 2026-08-27
**影响范围**: `tools/scripts/jcode_ai_native_workflow.py` + 跨测试文件状态隔离

## 背景

`test_context_sync_prune.py` 在模块顶层调用 `load_context_sync_module()`，该助手在首次调用时把 `.jcode/scripts` 永久插入 `sys.path[0]`。

`.jcode/scripts/multi_agent_orch.py` 是一个**扁平模块**（无 `__path__`），而 `examples/multi-agent-orch/multi_agent_orch/` 是**同名真包**。

测试运行时序：

1. pytest 收集所有测试模块，按字母序执行
2. `test_context_sync_prune.py` 顶层副作用 → `sys.path[0] = .jcode/scripts`
3. `test_ai_native_workflow.py` 在第 16 位执行
4. `_step3_adversarial_scope()` 内延迟导入 `from multi_agent_orch.orchestration import ...`
5. Python 在 `sys.path[0]` 先发现扁平 `.py` 文件 → 缓存为 `multi_agent_orch` 模块
6. 由于扁平模块**不是包**，`from multi_agent_orch.orchestration import ...` 立即抛 `ModuleNotFoundError: not a package`

### 表现

- 单独跑 `tests/test_ai_native_workflow.py` ✅ 11 passed
- 全量跑 `tests/` ❌ `test_step3_adversarial_scope` / `test_happy_path_end_to_end` 失败
- 跨段污染：1-40 个测试文件可复现，1-30 / 31-40 单独跑不可复现（依赖全局 `sys.path` 状态）

## 决策

`jcode_ai_native_workflow.py` 在 `sys.path` 注入**之后**立刻清理可能被遮蔽的 `sys.modules` 缓存，并预导入真包：

```python
sys.path.insert(0, str(get_project_root() / "examples" / "multi-agent-orch"))

# 防范 .jcode/scripts 中同名扁平模块遮蔽包
_cached = sys.modules.get("multi_agent_orch")
if _cached is not None and not hasattr(_cached, "__path__"):
    del sys.modules["multi_agent_orch"]
    for _name in list(sys.modules):
        if _name == "multi_agent_orch" or _name.startswith("multi_agent_orch."):
            del sys.modules[_name]
import multi_agent_orch  # noqa
```

**为什么不修测试助手**：助手的设计意图是支持对 `.jcode/scripts/context-sync.py` 的 `from _common import ...` 同级导入。如果改为局部 sys.path 注入，要重写 4 个测试文件，且助手的语义会变。

**为什么不删扁平模块**（历史决定，v2.13.2 已删）：`.jcode/scripts/multi_agent_orch.py` 曾是 jcode CLI 的子命令加载入口（hooks 体系用），删除会破坏 hooks.json 现有配置。

> **v2.13.2 更新**：经实测验证，`.jcode/scripts/hooks_runner.py` 的 skill 解析规则是 `f"{skill}.py"`，而 hooks.json 中 skill 为 `multi-agent-orch`（连字符），实际加载的是 `.jcode/scripts/multi-agent-orch.py`（44 行薄 wrapper，包装 examples 包 demo），**不是**下划线版 491 行扁平模块。491 行版 `multi_agent_orch.py` 实测无任何 hooks 调用、无 import 引用，是死代码且是 sys.path 遮蔽源。
>
> 修复：删除 491 行扁平模块 + 简化 `jcode_ai_native_workflow.py` 防遮蔽代码（27-33 行） + 更新 AGENTS.md 文档指向。

## 后果

- ✅ 1-40 文件复现路径已修复（945 passed）
- ✅ 全量回归 3493 passed in 547s, 0 failed
- ✅ 测试间状态隔离的鲁棒性提升
- ⚠️ 增加了 `jcode_ai_native_workflow` 模块级 import 的复杂度（但用 noqa 注释明示）
- 💡 启示：跨测试文件状态污染定位时，**`sys.meta_path` 探针**记录首次 `multi_agent_orch` 导入的调用栈是最高效手段

## 相关

- 提交 `a9e816a` fix(workflow): sys.path 顺序遮蔽 multi_agent_orch 包导入
- 全量回归验证：3493 passed
- 复现命令：`pytest tests/test_ai_native_workflow.py tests/test_context_sync_prune.py`（现已通过）
