# Kotlin Governance Rules

> 适用于 Kotlin 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: ktlint 或 ktfmt
- **缩进**: 4 空格
- **行宽**: 120 字符
- **花括号**: K&R 风格

### Linting

- **工具**: detekt
- **规则**: 启用所有规则
- **静态分析**: SonarQube

### 命名规范

```kotlin
// ✅ 正确
class UserService { ... }
fun getUser(id: String): User { ... }
const val MAX_RETRIES = 3

// ❌ 禁止
class userService { ... }  // 应为 PascalCase
fun GetUser(id: String) { ... }  // 应为 camelCase
```

---

## 2. 错误处理

### Result 类型

```kotlin
sealed class AppError {
    data class Validation(val field: String, val message: String) : AppError()
    data class NotFound(val resource: String, val id: String) : AppError()
    data class Internal(val cause: Throwable) : AppError()
}

suspend fun <T> runCatchingSuspend(block: suspend () -> T): Result<T, AppError> {
    return try {
        Result.success(block())
    } catch (e: Exception) {
        Result.failure(e.toAppError())
    }
}

private fun Exception.toAppError(): AppError = when (this) {
    is ValidationException -> AppError.Validation(field, message)
    is NotFoundException -> AppError.NotFound(resource, id)
    else -> AppError.Internal(this)
}
```

### 禁止行为

```kotlin
// ❌ 禁止: 强制解包
val user = getUser(id)!!  // 可能 NPE!

// ❌ 禁止: 空 catch
try {
    doSomething()
} catch (e: Exception) {
    // 忽略
}

// ✅ 正确
val user = getUser(id) ?: throw NotFoundException("User", id)
```

---

## 3. 现代 Kotlin 特性

### 协程

```kotlin
// ✅ 正确
suspend fun processUser(id: String): Result<User, AppError> {
    return runCatchingSuspend {
        val user = userRepository.findById(id)
        validateUser(user)
    }
}

// ✅ 正确: 并发执行
suspend fun processConcurrently(): List<User> = coroutineScope {
    users.map { user ->
        async { processUser(user.id) }
    }.awaitAll().filterIsResult()
}
```

### Flow

```kotlin
// ✅ 正确
fun observeUsers(): Flow<User> = flow {
    while (true) {
        val users = fetchUsers()
        users.forEach { emit(it) }
        delay(1000)
    }
}

// ❌ 禁止: 在 Flow 中阻塞
fun observeUsers(): Flow<User> = flow {
    while (true) {
        val users = runBlocking { fetchUsers() }  // 阻塞!
        users.forEach { emit(it) }
    }
}
```

### 密封类

```kotlin
// ✅ 正确
sealed class UIState<out T> {
    object Loading : UIState<Nothing>()
    data class Success<T>(val data: T) : UIState<T>()
    data class Error(val message: String) : UIState<Nothing>()
}

// ❌ 禁止: 使用枚举代替密封类
enum class UIState {
    LOADING, SUCCESS, ERROR  // 无法携带数据
}
```

---

## 4. 空安全

### 可空类型

```kotlin
// ❌ 禁止: 使用 platform type
val user: User = getUser(id)  // Java 返回值可能 null

// ✅ 正确: 显式声明可空
val user: User? = getUser(id)
user?.let { processUser(it) } ?: throw NotFoundException("User", id)
```

### 安全调用链

```kotlin
// ❌ 禁止: 手动 null 检查
val email = if (user != null) {
    if (user.address != null) {
        user.address.email
    } else {
        null
    }
} else {
    null
}

// ✅ 正确
val email = user?.address?.email
```

---

## 5. 测试规范

### JUnit 5 + Kotlin

```kotlin
class UserServiceTest {
    private lateinit var service: UserService
    
    @BeforeEach
    fun setUp() {
        service = UserService()
    }
    
    @Test
    fun `should get user when found`() {
        val user = service.getUser("123")
        assertThat(user.id).isEqualTo("123")
    }
    
    @Test
    fun `should throw when not found`() {
        assertThrows<NotFoundException> {
            service.getUser("nonexistent")
        }
    }
}
```

### MockK

```kotlin
class UserServiceTest {
    private val repository = mockk<UserRepository>()
    private val service = UserService(repository)
    
    @Test
    fun `should get user`() = runTest {
        coEvery { repository.findById("123") } returns User("123")
        
        val user = service.getUser("123")
        assertThat(user).isNotNull()
        coVerify { repository.findById("123") }
    }
}
```

---

## 6. 项目结构

```
project/
├── src/
│   ├── main/kotlin/
│   │   └── com/example/
│   │       ├── Application.kt
│   │       ├── controllers/
│   │       ├── services/
│   │       ├── repositories/
│   │       └── models/
│   └── test/kotlin/
├── build.gradle.kts
└── README.md
```

---

## 7. 安全规范

### 密钥管理

```kotlin
// ❌ 禁止
val apiKey = "sk-1234567890"

// ✅ 正确
val apiKey = System.getenv("API_KEY")
    ?: throw IllegalStateException("API_KEY not set")
```

---

## 8. 质量检查清单

### 代码质量

- [ ] ktlint 通过
- [ ] detekt 无错误
- [ ] 无强制解包 (!!)
- [ ] 无空 catch 块
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 协程测试使用 runTest
- [ ] Mock 使用正确

### 文档质量

- [ ] 公开 API 有 KDoc
- [ ] 复杂逻辑有注释
- [ ] README.md 已更新

---

*本规范随 Kotlin 生态演进持续更新。最后更新: 2026-07-17*
