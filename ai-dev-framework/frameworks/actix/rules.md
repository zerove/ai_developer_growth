# Actix Web 开发规则

> 基于 Rust 的 Actix Web 开发标准

---

## 核心约定

### 文件组织

```
src/
├── api/
│   ├── handlers/    # 请求处理
│   ├── middleware/   # 中间件
│   └── mod.rs
├── models/          # 数据模型
├── services/        # 业务逻辑
├── db/              # 数据库
├── config/          # 配置
├── errors/          # 错误类型
├── main.rs          # 入口
└── lib.rs
```

### 命名规范

- **文件**: `snake_case.rs`
- **结构体/枚举**: `PascalCase`
- **函数**: `snake_case`
- **模块**: `snake_case`
- **Handler 函数**: `snake_case`

---

## API 规范

```rust
use actix_web::{web, HttpResponse, Responder};
use serde::Deserialize;
use crate::services::UserService;

#[derive(Deserialize)]
pub struct UserQuery {
    pub page: Option<u32>,
    pub limit: Option<u32>,
}

// ✅ 推荐的 handler 结构
pub async fn list_users(
    query: web::Query<UserQuery>,
    service: web::Data<UserService>,
) -> impl Responder {
    let users = service.find_all(query.page.unwrap_or(1)).await;
    HttpResponse::Ok().json(users)
}

pub async fn create_user(
    body: web::Json<CreateUserRequest>,
    service: web::Data<UserService>,
) -> impl Responder {
    let user = service.create(body.into_inner()).await;
    HttpResponse::Created().json(user)
}
```

---

## 质量门禁

```bash
# Lint
cargo clippy -- -D warnings

# 测试
cargo test -- --nocapture

# 安全
cargo audit
```

---

## 错误处理

```rust
use actix_web::{HttpResponse, ResponseError};
use std::fmt;

// ✅ 统一的错误类型
#[derive(Debug)]
pub enum AppError {
    NotFound(String),
    BadRequest(String),
    Internal(String),
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AppError::NotFound(msg) => write!(f, "Not found: {}", msg),
            AppError::BadRequest(msg) => write!(f, "Bad request: {}", msg),
            AppError::Internal(msg) => write!(f, "Internal error: {}", msg),
        }
    }
}

impl ResponseError for AppError {
    fn error_response(&self) -> HttpResponse {
        match self {
            AppError::NotFound(msg) => HttpResponse::NotFound().json(ErrorResponse {
                code: "NOT_FOUND".into(),
                message: msg.clone(),
            }),
            AppError::BadRequest(msg) => HttpResponse::BadRequest().json(ErrorResponse {
                code: "BAD_REQUEST".into(),
                message: msg.clone(),
            }),
            AppError::Internal(_) => HttpResponse::InternalServerError().finish(),
        }
    }
}
```

---

## 路由配置

```rust
// ✅ 清晰的路由组织
use actix_web::web;

pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::scope("/api/v1/users")
            .route("", web::get().to(handlers::user::list_users))
            .route("", web::post().to(handlers::user::create_user))
            .route("/{id}", web::get().to(handlers::user::get_user))
            .route("/{id}", web::put().to(handlers::user::update_user))
            .route("/{id}", web::delete().to(handlers::user::delete_user)),
    );
}
```

---

## 常用依赖

| 用途 | 推荐包 |
|------|--------|
| ORM | sqlx / diesel |
| 序列化 | serde + serde_json |
| 认证 | actix-identity / jsonwebtoken |
| 验证 | validator |
| 日志 | tracing / log |
| 测试 | actix-test + rstest |
