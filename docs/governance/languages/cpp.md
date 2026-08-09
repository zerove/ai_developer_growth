---
title: C/C++ Governance Rules
description: > 适用于 C/C++ 项目的 AI Agent 开发规范。
category: 治理层
tags: ['测试', 'AI', 'API']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# C/C++ Governance Rules

> 适用于 C/C++ 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: clang-format
- **配置**: 使用 LLVM 或 Google 风格
- **缩进**: 2 空格
- **行宽**: 100 字符

### Linting

- **工具**: clang-tidy
- **规则**: 启用所有现代检查
- **静态分析**: cppcheck, PVS-Studio

### 命名规范

```cpp
// ✅ 正确
class UserService { ... };
void getUser(const std::string& id);
constexpr int MAX_RETRIES = 3;

// ❌ 禁止
class userService { ... };  // 应为 PascalCase
void GetUser(const std::string& id);  // 应为 camelCase
```

---

## 2. 内存管理

### 智能指针

```cpp
// ✅ 正确: 使用智能指针
auto user = std::make_shared<User>("123");
auto config = std::make_unique<Config>();

// ❌ 禁止: 裸指针
User* user = new User("123");
delete user;  // 容易泄漏
```

### RAII

```cpp
// ✅ 正确: RAII 模式
class FileHandler {
    std::FILE* file;
public:
    FileHandler(const char* filename) : file(std::fopen(filename, "r")) {}
    ~FileHandler() { if (file) std::fclose(file); }

    // 禁止拷贝
    FileHandler(const FileHandler&) = delete;
    FileHandler& operator=(const FileHandler&) = delete;
};

// ❌ 禁止: 手动资源管理
void readFile(const char* filename) {
    FILE* file = fopen(filename, "r");
    // 可能忘记 fclose
}
```

---

## 3. 现代 C++ 特性

### 使用 auto

```cpp
// ✅ 正确
auto it = map.find(key);
auto value = static_cast<int>(raw);

// ❌ 禁止: 冗余类型
std::map<std::string, int>::iterator it = map.find(key);
```

### 使用 range-based for

```cpp
// ✅ 正确
for (const auto& item : items) {
    process(item);
}

// ❌ 禁止: 传统 for 循环
for (int i = 0; i < items.size(); i++) {
    process(items[i]);
}
```

### 使用 constexpr

```cpp
// ✅ 正确
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

// ❌ 禁止: 运行时常量
const int MAX_SIZE = 100;  // 应为 constexpr
```

---

## 4. 错误处理

### 异常 vs 错误码

```cpp
// ✅ 正确: 使用异常处理不可恢复错误
class UserNotFoundException : public std::runtime_error {
public:
    UserNotFoundException(const std::string& id)
        : std::runtime_error("User not found: " + id) {}
};

User getUser(const std::string& id) {
    auto user = db.find(id);
    if (!user) {
        throw UserNotFoundException(id);
    }
    return *user;
}

// ✅ 正确: 使用 std::expected (C++23) 或 std::optional
std::optional<User> getUser(const std::string& id) {
    return db.find(id);
}
```

### 禁止行为

```cpp
// ❌ 禁止: 使用 assert 处理运行时错误
assert(user != nullptr);  // Release 模式下无效

// ❌ 禁止: 空 catch
try {
    doSomething();
} catch (...) {
    // 忽略
}
```

---

## 5. 性能优化

### 移动语义

```cpp
// ✅ 正确: 使用移动语义
std::vector<int> createLargeVector() {
    std::vector<int> result(1000000);
    // 填充数据
    return result;  // 自动移动
}

// ✅ 正确: 使用 std::move
std::string process(std::string&& input) {
    return std::move(input);
}
```

### 避免不必要的拷贝

```cpp
// ❌ 禁止: 不必要的拷贝
void process(std::vector<int> data) { ... }

// ✅ 正确: 使用 const 引用
void process(const std::vector<int>& data) { ... }

// ✅ 正确: 使用 std::string_view
void process(std::string_view data) { ... }
```

---

## 6. 测试规范

### Google Test

```cpp
#include <gtest/gtest.h>

TEST(UserServiceTest, GetUserReturnsUser) {
    UserService service;
    auto user = service.getUser("123");
    EXPECT_EQ(user.getId(), "123");
}

TEST(UserServiceTest, GetUserThrowsWhenNotFound) {
    UserService service;
    EXPECT_THROW(service.getUser("nonexistent"), UserNotFoundException);
}
```

### Mock 框架

```cpp
#include <gmock/gmock.h>

class MockUserRepository : public UserRepository {
public:
    MOCK_METHOD(std::optional<User>, findById, (const std::string& id), (const));
};

TEST(UserServiceTest, GetUser) {
    MockUserRepository repo;
    EXPECT_CALL(repo, findById("123"))
        .WillOnce(testing::Return(User("123")));

    UserService service(repo);
    auto user = service.getUser("123");
    EXPECT_TRUE(user.has_value());
}
```

---

## 7. 安全规范

### 缓冲区溢出防护

```cpp
// ❌ 禁止: 不安全的字符串操作
char buffer[10];
strcpy(buffer, input);  // 可能溢出!

// ✅ 正确: 使用安全函数
std::string buffer(input);
```

### 密钥管理

```cpp
// ❌ 禁止
const char* API_KEY = "YOUR_API_KEY_HERE";

// ✅ 正确
const char* API_KEY = std::getenv("API_KEY");
if (!API_KEY) {
    throw std::runtime_error("API_KEY not set");
}
```

---

## 8. 质量检查清单

### 代码质量

- [ ] clang-format 通过
- [ ] clang-tidy 无错误
- [ ] 无内存泄漏 (使用 Valgrind/ASan)
- [ ] 无缓冲区溢出
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用智能指针
- [ ] 无裸指针

### 性能

- [ ] 使用移动语义
- [ ] 避免不必要的拷贝
- [ ] 使用 constexpr 计算常量

---

*本规范随 C++ 生态演进持续更新。最后更新: 2026-07-17*
