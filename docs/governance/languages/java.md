---
title: Java Governance Rules
description: > 适用于 Java 项目的 AI Agent 开发规范。
category: 治理层
tags: ['AI', 'REST', 'API', '测试', 'SQL']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# Java Governance Rules

> 适用于 Java 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: Google Java Format 或 Spotless
- **缩进**: 2 空格
- **行宽**: 100 字符
- **花括号**: K&R 风格

### Linting

- **工具**: Checkstyle + PMD + SpotBugs
- **规则**: 启用 Google/Sun 编码规范
- **静态分析**: SonarQube

### 命名规范

```java
// ✅ 正确
public class UserService { ... }
public void getUser(String id) { ... }
private static final int MAX_RETRIES = 3;

// ❌ 禁止
public class userService { ... }  // 应为 PascalCase
public void GetUser(String id) { ... }  // 应为 camelCase
```

---

## 2. 错误处理

### 自定义异常层次

```java
// 基础异常
public class AppException extends Exception {
    private final String code;

    public AppException(String message, String code) {
        super(message);
        this.code = code;
    }

    public String getCode() { return code; }
}

// 业务异常
public class BusinessException extends AppException {
    public BusinessException(String message, String code) {
        super(message, code);
    }
}

// 验证异常
public class ValidationException extends BusinessException {
    private final String field;

    public ValidationException(String field, String message) {
        super(message, "VALIDATION_ERROR");
        this.field = field;
    }

    public String getField() { return field; }
}

// 资源未找到
public class NotFoundException extends BusinessException {
    public NotFoundException(String resource, String id) {
        super(resource + " with id " + id + " not found", "NOT_FOUND");
    }
}
```

### 禁止行为

```java
// ❌ 禁止: 空 catch
try {
    doSomething();
} catch (Exception e) {
    // 忽略
}

// ❌ 禁止: 使用异常控制流
try {
    return map.get(key);
} catch (NullPointerException e) {
    return defaultValue;
}

// ✅ 正确
Optional<Value> value = Optional.ofNullable(map.get(key));
return value.orElse(defaultValue);
```

---

## 3. 现代 Java 特性

### Optional 使用

```java
// ❌ 禁止: null 检查
if (user != null) {
    if (user.getEmail() != null) {
        return user.getEmail();
    }
}
return "unknown";

// ✅ 正确
return Optional.ofNullable(user)
    .map(User::getEmail)
    .orElse("unknown");
```

### Stream API

```java
// ❌ 禁止: 手动循环
List<String> result = new ArrayList<>();
for (User user : users) {
    if (user.isActive()) {
        result.add(user.getName());
    }
}

// ✅ 正确
List<String> result = users.stream()
    .filter(User::isActive)
    .map(User::getName)
    .collect(Collectors.toList());
```

### Records (Java 16+)

```java
// ✅ 正确: 使用 record 代替 DTO 类
public record UserDTO(String id, String name, String email) {}

// ❌ 禁止: 手动编写 DTO
public class UserDTO {
    private String id;
    private String name;
    private String email;
    // getters, setters, equals, hashCode, toString...
}
```

---

## 4. 并发编程

### 线程安全

```java
// ❌ 禁止: 共享可变状态
public class Counter {
    private int count = 0;  // 非线程安全!

    public void increment() { count++; }
}

// ✅ 正确: 使用 synchronized 或原子类
public class Counter {
    private final AtomicInteger count = new AtomicInteger(0);

    public void increment() { count.incrementAndGet(); }
}
```

### 并发集合

```java
// ❌ 禁止: HashMap 在多线程环境
Map<String, User> userMap = new HashMap<>();

// ✅ 正确: ConcurrentHashMap
ConcurrentHashMap<String, User> userMap = new ConcurrentHashMap<>();
```

### Virtual Threads (Java 21+)

```java
// ✅ 正确: 使用虚拟线程
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    IntStream.range(0, 10_000).forEach(i -> {
        executor.submit(() -> {
            Thread.sleep(Duration.ofSeconds(1));
            return i;
        });
    });
}
```

---

## 5. 测试规范

### JUnit 5 结构

```java
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import static org.junit.jupiter.api.Assertions.*;

class UserServiceTest {
    private UserService service;

    @BeforeEach
    void setUp() {
        service = new UserService();
    }

    @Test
    void shouldGetUserWhenFound() {
        User user = service.getUser("123");
        assertEquals("123", user.getId());
    }

    @Test
    void shouldThrowWhenNotFound() {
        assertThrows(NotFoundException.class, () -> {
            service.getUser("nonexistent");
        });
    }
}
```

### Mock 框架

```java
import org.mockito.Mock;
import org.mockito.InjectMocks;
import static org.mockito.Mockito.*;

class UserServiceTest {
    @Mock
    private UserRepository repository;

    @InjectMocks
    private UserService service;

    @Test
    void shouldGetUser() {
        when(repository.findById("123")).thenReturn(Optional.of(new User("123")));

        User user = service.getUser("123");
        assertNotNull(user);
        verify(repository).findById("123");
    }
}
```

---

## 6. 项目结构

```
project/
├── src/main/java/
│   ├── com/example/
│   │   ├── Application.java
│   │   ├── controllers/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── models/
│   │   └── exceptions/
├── src/main/resources/
├── src/test/java/
├── pom.xml 或 build.gradle
└── README.md
```

---

## 7. 依赖管理

### Maven

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
</dependencies>
```

### Gradle

```kotlin
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
}
```

---

## 8. 安全规范

### SQL 注入防护

```java
// ❌ 禁止: 字符串拼接
String query = "SELECT * FROM users WHERE id = '" + userId + "'";

// ✅ 正确: 使用 PreparedStatement
PreparedStatement stmt = connection.prepareStatement(
    "SELECT * FROM users WHERE id = ?"
);
stmt.setString(1, userId);
```

### 密钥管理

```java
// ❌ 禁止
String apiKey = "YOUR_API_KEY_HERE";

// ✅ 正确
@Value("${api.key}")
private String apiKey;
```

---

## 9. 质量检查清单

### 代码质量

- [ ] Google Java Format 通过
- [ ] Checkstyle 无错误
- [ ] 无空 catch 块
- [ ] 无未处理的 checked exception
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] Mock 使用正确
- [ ] 无共享可变状态

### 文档质量

- [ ] 所有公开类有 Javadoc
- [ ] 复杂逻辑有注释
- [ ] README.md 已更新

---

*本规范随 Java 生态演进持续更新。最后更新: 2026-07-17*
