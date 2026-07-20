# Rust 语言规则

> 适用于 Rust 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | snake_case | `my_module.rs` |
| 函数名 | snake_case | `my_function()` |
| 变量名 | snake_case | `my_variable` |
| 结构体 | PascalCase | `MyStruct` |
| 枚举 | PascalCase | `MyEnum` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SIZE` |
| 模块 | snake_case | `my_module` |

### 导入顺序

```rust
// 1. 标准库
use std::collections::HashMap;
use std::path::Path;

// 2. 第三方库
use serde::{Deserialize, Serialize};
use tokio::main;

// 3. 本地模块
use crate::my_module::my_function;
```

---

## 错误处理

### 惯用模式

```rust
// ✅ 正确
fn my_function() -> Result<String, Error> {
    let result = do_something()
        .map_err(|e| Error::from(e))?;
    Ok(result)
}

// ❌ 错误
fn my_function() -> String {
    let result = do_something().unwrap();
    result
}
```

---

## 测试

### 框架选择

| 框架 | 适用场景 |
|------|----------|
| 内置测试 | 通用测试 |
| proptest | 属性测试 |
| criterion | 基准测试 |

### 测试结构

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_my_function_success() {
        let result = my_function(1, 2);
        assert_eq!(result, 3);
    }

    #[test]
    fn test_my_function_error() {
        let result = my_function(None, 2);
        assert!(result.is_err());
    }
}
```

---

## 文档

### 文档注释

```rust
/// 一句话描述函数功能。
///
/// # Arguments
///
/// * `param1` - 参数1描述
/// * `param2` - 参数2描述
///
/// # Returns
///
/// 返回值描述
///
/// # Errors
///
/// 当参数无效时返回 `Error`
fn my_function(param1: i32, param2: &str) -> Result<bool, Error> {
    Ok(true)
}
```

---

## 工具配置

### Clippy

```toml
# .clippy.toml
msrv = "1.70"
```

### Cargo

```toml
# Cargo.toml
[lints.clippy]
all = { level = "warn", priority = -1 }
pedantic = { level = "warn", priority = -1 }
```

---

*本规则适用于 Rust 项目的 AI Agent 开发。*
