---
title: Swift Governance Rules
description: > 适用于 Swift 项目的 AI Agent 开发规范。
category: 治理层
tags: ['AI', 'API', 'Python', '测试', '安全']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Swift Governance Rules

> 适用于 Swift 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: SwiftFormat
- **缩进**: 4 空格
- **行宽**: 120 字符
- **花括号**: K&R 风格

### Linting

- **工具**: SwiftLint
- **规则**: 启用所有规则
- **严格模式**: 启用 strict 模式

### 命名规范

```swift
// ✅ 正确
class UserService { ... }
func getUser(id: String) -> User? { ... }
let maxRetries = 3

// ❌ 禁止
class userService { ... }  // 应为 PascalCase
func GetUser(id: String) -> User? { ... }  // 应为 camelCase
```

---

## 2. 类型安全

### 使用 Optionals

```swift
// ❌ 禁止: 强制解包
let user = getUser(id)!  // 可能崩溃!

// ✅ 正确: 安全解包
if let user = getUser(id) {
    process(user)
}

// ✅ 正确: 使用 guard
guard let user = getUser(id) else {
    throw NotFoundError(id)
}

// ✅ 正确: 使用 nil 合并
let name = getUser(id)?.name ?? "Unknown"
```

### 使用 Enums

```swift
// ✅ 正确: 使用枚举表示状态
enum UserState {
    case idle
    case loading
    case success(User)
    case error(Error)
}

// ❌ 禁止: 使用布尔值代替
var isLoading = false
var isError = false
```

---

## 3. 协议与扩展

### 协议设计

```swift
// ✅ 正确: 小而专注的协议
protocol UserFetchable {
    func fetchUser(id: String) async throws -> User
}

protocol UserCacheable {
    func cacheUser(_ user: User) async
}

// ✅ 正确: 协议扩展
extension UserFetchable {
    func fetchUser(id: String) async throws -> User {
        // 默认实现
    }
}
```

### 禁止行为

```python
# ❌ 禁止: 大而全的协议
protocol UserServiceProtocol {
    func getUser(id: String) async throws -> User
    func createUser(user: User) async throws -> User
    func updateUser(id: String, user: User) async throws -> User
    func deleteUser(id: String) async throws
    func sendEmail(user: User, subject: String) async throws
    // ... 更多方法
}
```

---

## 4. 异步编程

### async/await

```swift
// ✅ 正确
func processUser(id: String) async throws -> User {
    let user = try await fetchUser(id)
    let validated = try validateUser(user)
    return validated
}

// ✅ 正确: 并发执行
func processConcurrently() async throws {
    async let user1 = processUser(id: "1")
    async let user2 = processUser(id: "2")
    let results = try await [user1, user2]
}
```

### 结构化并发

```swift
// ✅ 正确: 使用 TaskGroup
func processAll(ids: [String]) async throws -> [User] {
    try await withThrowingTaskGroup(of: User.self) { group in
        for id in ids {
            group.addTask {
                try await self.processUser(id: id)
            }
        }
        
        var users: [User] = []
        for try await user in group {
            users.append(user)
        }
        return users
    }
}
```

---

## 5. 测试规范

### XCTest

```swift
import XCTest
@testable import MyApp

final class UserServiceTests: XCTestCase {
    var service: UserService!
    
    override func setUp() {
        super.setUp()
        service = UserService()
    }
    
    func testGetUserReturnsUser() async throws {
        let user = try await service.getUser(id: "123")
        XCTAssertEqual(user.id, "123")
    }
    
    func testGetUserThrowsWhenNotFound() async {
        do {
            _ = try await service.getUser(id: "nonexistent")
            XCTFail("Expected error")
        } catch {
            XCTAssertTrue(error is NotFoundError)
        }
    }
}
```

### Mock 框架

```swift
final class MockUserRepository: UserFetchable {
    var users: [String: User] = [:]
    
    func fetchUser(id: String) async throws -> User {
        guard let user = users[id] else {
            throw NotFoundError(id)
        }
        return user
    }
}

final class UserServiceTests: XCTestCase {
    func testGetUser() async throws {
        let repo = MockUserRepository()
        repo.users["123"] = User(id: "123", name: "John")
        
        let service = UserService(repository: repo)
        let user = try await service.getUser(id: "123")
        XCTAssertEqual(user.name, "John")
    }
}
```

---

## 6. 项目结构

```
project/
├── Sources/
│   ├── Models/
│   ├── Services/
│   ├── Repositories/
│   └── Views/
├── Tests/
├── Package.swift
└── README.md
```

---

## 7. 安全规范

### 密钥管理

```swift
// ❌ 禁止
let apiKey = "YOUR_API_KEY_HERE"

// ✅ 正确
let apiKey = ProcessInfo.processInfo.environment["API_KEY"]
    ?? fatalError("API_KEY not set")
```

### Keychain 使用

```swift
// ✅ 正确: 使用 Keychain 存储敏感信息
import Security

func saveToken(_ token: String) {
    let data = token.data(using: .utf8)!
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "com.app.auth",
        kSecValueData as String: data
    ]
    SecItemAdd(query as CFDictionary, nil)
}
```

---

## 8. 质量检查清单

### 代码质量

- [ ] SwiftLint 通过
- [ ] SwiftFormat 通过
- [ ] 无强制解包 (!)
- [ ] 无硬编码密钥
- [ ] 使用 Optionals 安全处理

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] Mock 使用正确
- [ ] 异步测试完整

### 性能

- [ ] 使用值类型 (struct) 代替引用类型
- [ ] 避免不必要的内存分配
- [ ] 使用 lazy 属性延迟初始化

---

*本规范随 Swift 生态演进持续更新。最后更新: 2026-07-17*
