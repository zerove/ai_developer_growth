---
title: Go Governance Rules
description: > 适用于 Go 项目的 AI Agent 开发规范。
category: 治理层
tags: ['测试', 'AI', 'SQL', 'API']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# Go Governance Rules

> 适用于 Go 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: `gofmt` 或 `goimports`
- **配置**: 使用默认配置
- **行宽**: 无限制，但建议 < 100 字符

### Linting

- **工具**: `golangci-lint`
- **规则**: 启用所有默认规则
- **命令**: `golangci-lint run`

### 命名规范

```go
// ✅ 正确
type UserService struct { ... }
func GetUser(id string) (*User, error) { ... }
const MaxRetries = 3

// ❌ 禁止
type userService struct { ... }  // 应为 PascalCase
func GetUser(id string) { ... }  // 应为 Getuser (Go 简写规则)
```

---

## 2. 错误处理

### 自定义错误类型

```go
package errors

import "fmt"

type AppError struct {
    Code    string
    Message string
    Err     error
}

func (e *AppError) Error() string {
    return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

func (e *AppError) Unwrap() error {
    return e.Err
}

func NewValidationError(field, message string) *AppError {
    return &AppError{
        Code:    "VALIDATION_ERROR",
        Message: fmt.Sprintf("%s: %s", field, message),
    }
}

func NewNotFoundError(resource, id string) *AppError {
    return &AppError{
        Code:    "NOT_FOUND",
        Message: fmt.Sprintf("%s with id %s not found", resource, id),
    }
}
```

### 禁止行为

```go
// ❌ 禁止: 忽略错误
result, _ := doSomething()

// ❌ 禁止: panic
func badExample() {
    panic("This should not happen")
}

// ✅ 正确
result, err := doSomething()
if err != nil {
    return nil, fmt.Errorf("failed to do something: %w", err)
}
```

### 错误传播

```go
// ✅ 正确: 使用 %w 包装错误
func processUser(id string) (*User, error) {
    user, err := getUser(id)
    if err != nil {
        return nil, fmt.Errorf("failed to get user: %w", err)
    }
    
    validated, err := validateUser(user)
    if err != nil {
        return nil, fmt.Errorf("failed to validate user: %w", err)
    }
    
    return validated, nil
}
```

---

## 3. 类型安全

### 使用类型系统

```go
// ❌ 禁止: 使用字符串代替类型
func processUser(userID string, role string) { ... }

// ✅ 正确: 使用类型
type UserID string
type Role string

func (r Role) IsValid() bool {
    return r == "admin" || r == "user"
}

func processUser(userID UserID, role Role) { ... }
```

### 避免空指针

```go
// ❌ 禁止: 未检查 nil
func process(user *User) string {
    return user.Name  // 可能 nil!
}

// ✅ 正确
func process(user *User) string {
    if user == nil {
        return ""
    }
    return user.Name
}
```

---

## 4. 并发编程

### Goroutines

```go
// ✅ 正确
func processConcurrently(items []Item) []Result {
    results := make([]Result, len(items))
    var wg sync.WaitGroup
    
    for i, item := range items {
        wg.Add(1)
        go func(i int, item Item) {
            defer wg.Done()
            results[i] = process(item)
        }(i, item)
    }
    
    wg.Wait()
    return results
}
```

### Channels

```go
// ✅ 正确
func producer(ch chan<- int) {
    for i := 0; i < 10; i++ {
        ch <- i
    }
    close(ch)
}

func consumer(ch <-chan int) {
    for value := range ch {
        fmt.Println(value)
    }
}
```

### 禁止行为

```go
// ❌ 禁止: 使用 time.Sleep 同步
func badExample() {
    go doSomething()
    time.Sleep(time.Second)  // 不可靠的同步!
}

// ✅ 正确: 使用 sync.WaitGroup 或 channel
func goodExample() {
    var wg sync.WaitGroup
    wg.Add(1)
    go func() {
        defer wg.Done()
        doSomething()
    }()
    wg.Wait()
}
```

---

## 5. 测试规范

### 单元测试

```go
package service

import (
    "testing"
)

func TestGetUserFound(t *testing.T) {
    user, err := GetUser("123")
    if err != nil {
        t.Fatalf("expected no error, got %v", err)
    }
    
    if user.ID != "123" {
        t.Errorf("expected user ID 123, got %s", user.ID)
    }
}

func TestGetUserNotFound(t *testing.T) {
    _, err := GetUser("nonexistent")
    if err == nil {
        t.Fatal("expected error, got nil")
    }
}
```

### 表驱动测试

```go
func TestValidateUser(t *testing.T) {
    tests := []struct {
        name    string
        user    User
        wantErr bool
    }{
        {
            name:    "valid user",
            user:    User{Name: "John", Email: "john@example.com"},
            wantErr: false,
        },
        {
            name:    "invalid email",
            user:    User{Name: "John", Email: "invalid"},
            wantErr: true,
        },
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := ValidateUser(tt.user)
            if (err != nil) != tt.wantErr {
                t.Errorf("ValidateUser() error = %v, wantErr %v", err, tt.wantErr)
            }
        })
    }
}
```

### Mock 规范

```go
// 使用 gomock
//go:generate mockgen -source=repository.go -destination=mock_repository.go -package=service

type UserRepository interface {
    Get(id string) (*User, error)
    Create(user *User) error
}

func TestGetUser(t *testing.T) {
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()
    
    mockRepo := NewMockUserRepository(ctrl)
    mockRepo.EXPECT().Get("123").Return(&User{ID: "123"}, nil)
    
    service := NewUserService(mockRepo)
    user, err := service.GetUser("123")
    
    if err != nil {
        t.Fatalf("expected no error, got %v", err)
    }
    
    if user.ID != "123" {
        t.Errorf("expected user ID 123, got %s", user.ID)
    }
}
```

---

## 6. 项目结构

```
project/
├── cmd/
│   └── server/
│       └── main.go
├── internal/
│   ├── models/
│   ├── services/
│   ├── repositories/
│   └── utils/
├── pkg/
│   └── public/
├── tests/
│   └── integration/
├── go.mod
└── README.md
```

### 依赖管理

- **工具**: `go mod`
- **锁定**: 使用 `go.sum`
- **版本**: 使用语义化版本

---

## 7. 接口设计

### 小接口

```go
// ✅ 正确: 小而专注的接口
type Reader interface {
    Read(p []byte) (n int, err error)
}

type Writer interface {
    Write(p []byte) (n int, err error)
}

// ✅ 正确: 组合接口
type ReadWriter interface {
    Reader
    Writer
}
```

### 避免大接口

```go
// ❌ 禁止: 大而全的接口
type UserService interface {
    GetUser(id string) (*User, error)
    CreateUser(user *User) error
    UpdateUser(id string, user *User) error
    DeleteUser(id string) error
    ListUsers() ([]*User, error)
    ValidateUser(user *User) error
    SendEmail(user *User, subject string) error
    // ... 更多方法
}
```

---

## 8. 性能优化

### 使用缓冲

```go
// ❌ 禁止: 逐字符读取
func readAll(r io.Reader) ([]byte, error) {
    var result []byte
    buf := make([]byte, 1)
    for {
        n, err := r.Read(buf)
        if n > 0 {
            result = append(result, buf[0])
        }
        if err != nil {
            break
        }
    }
    return result, nil
}

// ✅ 正确: 使用 io.ReadAll
func readAll(r io.Reader) ([]byte, error) {
    return io.ReadAll(r)
}
```

### 避免不必要的分配

```go
// ❌ 禁止: 在循环中创建 slice
func processItems(items []Item) []Result {
    var results []Result  // 每次 append 可能重新分配
    for _, item := range items {
        results = append(results, process(item))
    }
    return results
}

// ✅ 正确: 预分配
func processItems(items []Item) []Result {
    results := make([]Result, 0, len(items))  // 预分配容量
    for _, item := range items {
        results = append(results, process(item))
    }
    return results
}
```

---

## 9. 安全规范

### SQL 注入防护

```go
// ❌ 禁止: 字符串拼接
query := fmt.Sprintf("SELECT * FROM users WHERE id = %s", userID)

// ✅ 正确: 参数化查询
query := "SELECT * FROM users WHERE id = ?"
row := db.QueryRow(query, userID)
```

### 密钥管理

```go
// ❌ 禁止
const APIKey = "sk-1234567890"

// ✅ 正确
func getAPIKey() (string, error) {
    key := os.Getenv("API_KEY")
    if key == "" {
        return "", errors.New("API_KEY environment variable not set")
    }
    return key, nil
}
```

---

## 10. 质量检查清单

### 代码质量

- [ ] `gofmt` 通过
- [ ] `golangci-lint` 无错误
- [ ] 无 `panic` 在生产代码
- [ ] 无忽略的错误
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用表驱动测试
- [ ] Mock 使用正确

### 文档质量

- [ ] 所有公开函数有注释
- [ ] 复杂逻辑有注释
- [ ] README.md 已更新
- [ ] 示例代码可运行

---

*本规范随 Go 生态演进持续更新。最后更新: 2026-07-17*
