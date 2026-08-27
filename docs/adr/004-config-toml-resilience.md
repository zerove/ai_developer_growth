# ADR-004: pyproject.toml 配置加载的链式调用容错

**状态**: 接受
**日期**: 2026-08-27
**影响范围**: `tools/scripts/app_config.py` — 所有依赖 `[tool.adg]` 段的工具

## 背景

`app_config._load_toml_config()` 通过链式 `.get()` 解析 `pyproject.toml`：

```python
section = data.get("tool", {}).get("adg", {})
```

当 `pyproject.toml` 中 `tool` 被定义为非表结构时（例如 `tool = "flat"`），`data.get("tool", {})` 返回字符串 `"flat"`，而字符串没有 `.get()` 方法，抛 `AttributeError`。

异常捕获清单 `except (tomllib.TOMLDecodeError, OSError)` 不含 `AttributeError`，因此**用户自定义的合法 pyproject.toml 可能让配置加载直接崩溃**。

### 触发场景

```toml
# 用户在自己项目的 pyproject.toml 里这样写
tool = "flat"  # 或者 tool = ["a", "b"]
```

后续任何调用 `get_settings()` / `get_setting("...")` 的工具脚本（如 `hooks_runner.py`）都会失败，**整个 adg 工作流停摆**。

### 发现过程

v2.12.0 覆盖率攻坚中，给 `app_config` 补测试时构造了非表结构的 pyproject.toml 作为边界用例，**首跑即崩溃**，立即定位为真 bug（非统计偏差、非测试环境问题）。

## 决策

加 `isinstance` 防御性检查，**任何中间层节点非字典时返回空配置**：

```python
tool_section = data.get("tool", {})
if not isinstance(tool_section, dict):
    return {}
section = tool_section.get("adg", {})
return section if isinstance(section, dict) else {}
```

捕获范围不变（`TOMLDecodeError` + `OSError`），但通过防御性编程避免 `AttributeError` 进入。

## 后果

- ✅ `pyproject.toml` 中 `tool` 为字符串/列表/数字时优雅降级，返回空配置
- ✅ `app_config` 覆盖率 64%→97%
- ✅ 现有调用方语义不变（`_load_toml_config` 本来就允许返回 `{}`）
- ⚠️ 静默降级可能掩盖配置错误 — 但 `get_setting(key, default=...)` 的 `default` 参数让用户能感知到
- 💡 启示：防御性编程的异常清单**不能只列"预期异常"**，要用 `isinstance` 显式校验数据结构

## 相关

- 提交 `737849f` fix(config): app_config tool 段非字典时崩溃 + 64%→97% 覆盖补齐
- 测试 `tests/test_app_config_full.py::TestLoadToml::test_non_dict_section_returns_empty`
