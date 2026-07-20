# Spring Boot 开发规则

> 基于 Java 17+ 的 Spring Boot 开发标准

---

## 核心约定

### 包结构

```
com.example.project
├── config/         # 配置类 (@Configuration)
├── controller/     # REST 控制器 (@RestController)
├── service/        # 业务逻辑 (@Service)
├── repository/     # 数据访问 (@Repository)
├── model/          # 实体/DTO
│   ├── entity/     # JPA 实体
│   └── dto/        # 数据传输对象
├── exception/      # 异常处理
└── util/           # 工具类
```

### 命名规范

- **类**: `PascalCase` (UserService.java)
- **方法**: `camelCase` (findAllUsers())
- **包名**: `kebab-case` (com.example.user)
- **测试**: `{Name}Test.java`

---

## REST API 规范

```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @GetMapping
    public ResponseEntity<List<UserDTO>> findAll() {
        return ResponseEntity.ok(userService.findAll());
    }

    @GetMapping("/{id}")
    public ResponseEntity<UserDTO> findById(@PathVariable Long id) {
        return ResponseEntity.ok(userService.findById(id));
    }

    @PostMapping
    public ResponseEntity<UserDTO> create(@Valid @RequestBody CreateUserRequest request) {
        return ResponseEntity.status(201).body(userService.create(request));
    }
}
```

---

## 质量门禁

### Lint

```bash
# 检查
./mvnw checkstyle:check
# 或
./gradlew checkstyleMain

# 格式化
./mvnw spotless:check
```

### 测试

```bash
# 单元测试 + 集成测试
./mvnw test
./mvnw verify  # 包括集成测试

# 覆盖率
./mvnw jacoco:report
```

---

## 分层设计

```
Controller → Service → Repository ← Entity
    │           │           │
    ▼           ▼           ▼
   DTO       DTO         Entity
```

### 职责

| 层 | 职责 | 禁止 |
|----|------|------|
| Controller | 参数校验、路由 | 业务逻辑 |
| Service | 业务规则、事务 | 不直接操作数据库 |
| Repository | 数据访问 | 不含业务逻辑 |

---

## 异常处理

```java
// ✅ 全局异常处理
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ErrorResponse handleNotFound(ResourceNotFoundException ex) {
        return new ErrorResponse("NOT_FOUND", ex.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ErrorResponse handleValidation(MethodArgumentNotValidException ex) {
        var errors = ex.getBindingResult()
            .getFieldErrors()
            .stream()
            .map(e -> new FieldError(e.getField(), e.getDefaultMessage()))
            .toList();
        return new ErrorResponse("VALIDATION_FAILED", errors);
    }
}
```

---

## 常用依赖

| 用途 | 推荐包 |
|------|--------|
| API 文档 | springdoc-openapi |
| 数据库迁移 | Flyway |
| Map 工具 | MapStruct |
| 缓存 | Spring Cache + Redis |
| 消息队列 | Spring AMQP / Kafka |
| 安全 | Spring Security + JWT |
