# ADR-063: tree-sitter 导入必须按语言粒度容错

## 状态

接受

## 日期

2026-10-02

## 上下文

Phase 38 做 ADR 索引自动生成时跑全量回归，发现 **62 个测试失败**，
而上一阶段记录的是"4507 passed / 全绿"。追查发现这些失败并非本次改动引入
（stash 后在干净 HEAD 上同样失败），而是**环境依赖缺失**：

1. `tree-sitter` 及 12 个语言包**从未在 `pyproject.toml` 中声明**
2. `httpx` 未声明，导致 starlette `TestClient` 不可用

但真正值得记录的不是"忘装依赖"，而是依赖装上之后仍然失败：

### 关键发现：全有全无式导入

`ast_parser.py` 原本把 12 个语言包写在**同一个 try 块**里：

```python
try:
    import tree_sitter_c_sharp
    import tree_sitter_cpp

    # ... 共 12 个
    from tree_sitter import Language, Parser

    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
```

只要缺**任意一个**语言包，`HAS_TREE_SITTER` 就是 `False`，而 `parse_file`
随即对**所有**语言返回 `None`：

```python
if language not in self._parsers:
    return None
```

实测：只安装 `tree-sitter` + `tree_sitter-python`（最自然的选择），
12 个语言全部不可用，AST 语义检查整体静默失效。实测证据：
`ASTParser()._parsers == {}`，`parse_file(...)` 恒返回 `NoneType`。

这是典型的 **fail-open**（失效开放）：调用方拿到 `None` 不报错，
语义检查"看起来在跑"，实际什么都没检查 —— 与 Phase 38 在
`context-sync.validate` 和 hook 检测器上修复的是同一类缺陷。

## 决策

1. **按语言逐个导入**，缺失只影响该语言，不连坐其他语言。
   用 `_LANGUAGE_MODULES: dict[str, tuple[str, str]]` 登记表，
   运行时 `importlib.import_module` 惰性导入。
2. **缺失必须留痕**：不可用的语言在 stderr 上明确告警，
   替换掉原先的 `except Exception: pass`（静默跳过）。
3. **补齐依赖声明**：13 个 tree-sitter 包 + `httpx` 写入 `pyproject.toml`
   的 `dev` extra，使全新环境不再出现"AST 检查静默不工作"。

## 后果

- **正面**：只装 `tree-sitter-python` 时 Python AST 检查照常工作；
  环境缺包不再静默降级，而是在日志里可见。
- **代价**：`SUPPORTED_LANGUAGES` 与 `_LANGUAGE_MODULES` 必须同步维护，
  漏登记会导致该语言不可用（比 fail-open 好，但仍是新的维护点）。
  已加测试 `test_every_supported_language_has_a_module_mapping` 兜住。
- **实测收益**：全量回归从 62 failed / 4325 passed 变为 **4393 passed / 0 failed**。
- **遗留**：AST 不可用时 `parse_file` 仍返回 `None`（而非抛异常），
  调用方的 fail-open 面依然存在，本 ADR 只收窄了触发条件，未改变返回契约。

## 相关 ADR

- ADR-061：CONTEXT.md 固定头部必须独立于滚动窗口，且校验不得 fail-open
- ADR-062：fail-open 检测器必须校验"可执行性"，而非匹配错误关键词

## 验证方式

`tests/test_ast_parser_partial_install.py`（5 用例）。关键用例在**子进程**中、
于导入 `ast_parser` **之前**屏蔽语言包 —— 这一点是变异测试暴露的：
若在导入之后才屏蔽，旧实现同样正常，测试就测不出真实缺陷。
变异验证：退回旧实现 → `test_missing_languages_do_not_disable_python` 失败。
