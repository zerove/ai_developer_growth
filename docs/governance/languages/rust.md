# Rust Governance Rules

> 适用于 Rust 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: `rustfmt`
- **配置**: 使用默认配置或项目 `rustfmt.toml`
- **行宽**: 100 字符

### Linting

- **工具**: `clippy`
- **规则**: 启用所有警告，禁止 `allow` 除非必要
- **命令**: `cargo clippy -- -D warnings`

### 命名规范

```rust
// ✅ 正确
struct UserService { ... }
fn get_user(id: &str) -> Result<User, Error> { ... }
const MAX_RETRIES: u32 = 3;

// ❌ 禁止
struct user_service { ... }  // 应为 PascalCase
fn GetUser(id: &str) { ... }  // 应为 snake_case
```

---

## 2. 错误处理

### 自定义错误类型

```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("Validation error: {field} - {message}")]
    Validation { field: String, message: String },
    
    #[error("{resource} with id {id} not found")]
    NotFound { resource: String, id: String },
    
    #[error("Internal error: {0}")]
    Internal(#[from] anyhow::Error),
}

impl AppError {
    pub fn validation(field: impl Into<String>, message: impl Into<String>) -> Self {
        Self::Validation {
            field: field.into(),
            message: message.into(),
        }
    }
    
    pub fn not_found(resource: impl Into<String>, id: impl Into<String>) -> Self {
        Self::NotFound {
            resource: resource.into(),
            id: id.into(),
        }
    }
}
```

### 禁止行为

```rust
// ❌ 禁止: unwrap()
fn get_user(id: &str) -> User {
    db.query(id).unwrap()  // 可能 panic!
}

// ❌ 禁止: expect()
fn process() {
    let data = fs::read_to_string("file.txt").expect("Failed to read file");
}

// ❌ 禁止: panic!()
fn bad_example() {
    panic!("This should not happen");
}

// ✅ 正确
fn get_user(id: &str) -> Result<User, AppError> {
    db.query(id)
        .map_err(|e| AppError::not_found("User", id))
}
```

### Result 传播

```rust
// ✅ 正确: 使用 ? 操作符
fn process_user(id: &str) -> Result<User, AppError> {
    let user = get_user(id)?;  // 自动传播错误
    let validated = validate_user(user)?;  // 自动传播错误
    Ok(validated)
}

// ❌ 禁止: 手动匹配所有情况
fn process_user(id: &str) -> Result<User, AppError> {
    match get_user(id) {
        Ok(user) => {
            match validate_user(user) {
                Ok(validated) => Ok(validated),
                Err(e) => Err(e),
            }
        }
        Err(e) => Err(e),
    }
}
```

---

## 3. 类型安全

### 使用类型系统

```rust
// ❌ 禁止: 使用字符串代替类型
fn process_user(user_id: &str, role: &str) { ... }

// ✅ 正确: 使用类型
struct UserId(String);
struct Role(String);

impl Role {
    pub fn admin() -> Self { Self("admin".to_string()) }
    pub fn user() -> Self { Self("user".to_string()) }
}

fn process_user(user_id: UserId, role: Role) { ... }
```

### 避免 as 转换

```rust
// ❌ 禁止
let x = value as u32;  // 可能溢出

// ✅ 正确
let x = u32::try_from(value)
    .map_err(|_| AppError::validation("value", "out of range"))?;
```

---

## 4. 生命周期

### 明确生命周期

```rust
// ❌ 禁止: 省略生命周期
fn first_word(s: &str) -> &str {
    let bytes = s.as_bytes();
    for (i, &item) in bytes.iter().enumerate() {
        if item == b' ' {
            return &s[0..i];
        }
    }
    &s[..]
}

// ✅ 正确: 明确生命周期
fn first_word<'a>(s: &'a str) -> &'a str {
    let bytes = s.as_bytes();
    for (i, &item) in bytes.iter().enumerate() {
        if item == b' ' {
            return &s[0..i];
        }
    }
    &s[..]
}
```

### 避免不必要的生命周期

```rust
// ❌ 禁止: 不必要的生命周期
fn process<'a>(data: &'a str) -> &'a str {
    data.to_uppercase().as_str()  // 生命周期不匹配
}

// ✅ 正确: 返回 owned 类型
fn process(data: &str) -> String {
    data.to_uppercase()
}
```

---

## 5. 异步编程

### async/await

```rust
use tokio;
use std::future::Future;

// ✅ 正确
async fn fetch_data(url: &str) -> Result<String, reqwest::Error> {
    let response = reqwest::get(url).await?;
    let body = response.text().await?;
    Ok(body)
}

// ✅ 正确: 使用 tokio::spawn
async fn process_concurrently() {
    let handles: Vec<_> = (0..10)
        .map(|i| {
            tokio::spawn(async move {
                process(i).await
            })
        })
        .collect();
    
    for handle in handles {
        handle.await.unwrap();
    }
}
```

### 禁止行为

```rust
// ❌ 禁止: 在 async 函数中阻塞
async fn bad_example() {
    std::thread::sleep(Duration::from_secs(1));  // 阻塞!
}

// ✅ 正确
async fn good_example() {
    tokio::time::sleep(Duration::from_secs(1)).await;
}
```

---

## 6. 测试规范

### 单元测试

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_get_user_found() {
        let user = get_user("123").unwrap();
        assert_eq!(user.id, "123");
    }
    
    #[test]
    fn test_get_user_not_found() {
        let result = get_user("nonexistent");
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), AppError::NotFound { .. }));
    }
    
    #[tokio::test]
    async fn test_async_operation() {
        let result = async_operation().await;
        assert!(result.is_ok());
    }
}
```

### 集成测试

```rust
// tests/integration_test.rs
use my_crate::{App, UserService};

#[tokio::test]
async fn test_full_workflow() {
    let app = App::new().await;
    let service = UserService::new(app.db());
    
    let user = service.create_user("test@example.com").await.unwrap();
    assert_eq!(user.email, "test@example.com");
}
```

---

## 7. 项目结构

```
project/
├── src/
│   ├── lib.rs
│   ├── main.rs
│   ├── models/
│   ├── services/
│   ├── repositories/
│   └── utils/
├── tests/
│   └── integration_test.rs
├── Cargo.toml
└── README.md
```

### 依赖管理

```toml
# Cargo.toml
[dependencies]
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
thiserror = "1"
anyhow = "1"

[dev-dependencies]
tokio-test = "0.4"
mockall = "0.11"
```

---

## 8. 内存安全

### 避免 unsafe

```rust
// ❌ 禁止: 除非绝对必要
unsafe {
    let raw_ptr = &mut data as *mut Data;
    (*raw_ptr).process();
}

// ✅ 正确: 使用安全抽象
data.process();
```

### 使用智能指针

```rust
// ❌ 禁止: 裸指针
let ptr: *const Data = &data;

// ✅ 正确: 使用 Box/Rc/Arc
let boxed: Box<Data> = Box::new(data);
let shared: Rc<Data> = Rc::new(data);
let atomic: Arc<Data> = Arc::new(data);
```

---

## 9. 性能优化

### 使用迭代器

```rust
// ❌ 禁止: 手动循环
let mut result = Vec::new();
for item in items {
    if item.is_valid() {
        result.push(process(item));
    }
}

// ✅ 正确: 使用迭代器
let result: Vec<_> = items
    .iter()
    .filter(|item| item.is_valid())
    .map(|item| process(item))
    .collect();
```

### 避免不必要的克隆

```rust
// ❌ 禁止: 不必要的 clone
fn process(data: Data) {
    let clone = data.clone();  // 不必要的克隆
    // ...
}

// ✅ 正确: 使用引用
fn process(data: &Data) {
    // 直接使用 data
}
```

---

## 10. 质量检查清单

### 代码质量

- [ ] `cargo fmt` 通过
- [ ] `cargo clippy` 无警告
- [ ] 无 `unwrap()`/`expect()` 在生产代码
- [ ] 无 `unsafe` 除非必要
- [ ] 无 `as` 转换

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 无 panic!() 在测试中
- [ ] Mock 使用正确

### 文档质量

- [ ] 所有公开项有 doc comment
- [ ] 复杂逻辑有注释
- [ ] README.md 已更新
- [ ] 示例代码可运行

---

*本规范随 Rust 生态演进持续更新。最后更新: 2026-07-17*
