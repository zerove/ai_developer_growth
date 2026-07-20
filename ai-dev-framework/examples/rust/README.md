# Rust 示例项目

这是一个最小化的 Rust 示例项目，展示如何使用 ai-dev-framework。

---

## 项目结构

```
rust-example/
├── src/
│   └── lib.rs            # 主模块
├── tests/
│   └── integration.rs    # 集成测试
├── CLAUDE.md             # 项目规范
├── AGENTS.md             # Agent 索引
├── CONTEXT.md            # 项目上下文
└── Cargo.toml            # 项目配置
```

---

## 快速开始

```bash
# 构建项目
cargo build

# 运行测试
cargo test

# 代码检查
cargo clippy -- -D warnings
```

---

## Agent 示例

### src/lib.rs

```rust
//! 主模块

/// 两个数相加。
///
/// # Arguments
///
/// * `a` - 第一个数
/// * `b` - 第二个数
///
/// # Returns
///
/// 两数之和
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_success() {
        assert_eq!(add(1, 2), 3);
    }

    #[test]
    fn test_add_negative() {
        assert_eq!(add(-1, 1), 0);
    }
}
```

---

## 质量门禁检查

```bash
# 检查代码质量
bash .ai-framework/quality-gates/scripts/check.sh rust
```

---

*这是一个最小化的 Rust 示例项目。*
