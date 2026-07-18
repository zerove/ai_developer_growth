# Spring Boot Governance Rules

> 适用于 Spring Boot 项目的 AI Agent 开发规范。

---

## 1. 项目结构

### 分层架构

```
project/
├── src/main/java/
│   └── com/example/
│       ├── Application.java
│       ├── controller/
│       │   └── UserController.java
│       ├── service/
│       │   ├── UserService.java
│       │   └── impl/
│       │       └── UserServiceImpl.java
│       ├── repository/
│       │   └── UserRepository.java
│       ├── model/
│       │   ├── entity/
│       │   └── dto/
│       └── config/
├── src/main/resources/
│   └── application.yml
├── src/test/java/
├── pom.xml
└── README.md
```

---

## 2. 控制器规范

### RESTful 设计

```java
@RestController
@RequestMapping('/api/users')
@RequiredArgsConstructor
public class UserController {
    
    private final UserService userService;
    
    // ✅ 正确
    @GetMapping
    public ResponseEntity<List<UserDTO>> listUsers() {
        return ResponseEntity.ok(userService.findAll());
    }
    
    @GetMapping("/{id}")
    public ResponseEntity<UserDTO> getUser(@PathVariable String id) {
        return userService.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
    
    @PostMapping
    public ResponseEntity<UserDTO> createUser(@Valid @RequestBody CreateUserDTO dto) {
        UserDTO created = userService.create(dto);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }
    
    @PutMapping("/{id}")
    public ResponseEntity<UserDTO> updateUser(
        @PathVariable String id,
        @Valid @RequestBody UpdateUserDTO dto
    ) {
        return userService.update(id, dto)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
    
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteUser(@PathVariable String id) {
        if (userService.delete(id)) {
            return ResponseEntity.noContent().build();
        }
        return ResponseEntity.notFound().build();
    }
}
```

### 禁止行为

```java
// ❌ 禁止: 返回实现类
public class UserController {
    @GetMapping
    public List<User> listUsers() {  // 应返回 DTO
        return userService.findAll();
    }
}

// ❌ 禁止: 在控制器中包含业务逻辑
public class UserController {
    @PostMapping
    public User createUser(@RequestBody User user) {
        if (userRepository.existsByEmail(user.getEmail())) {
            throw new RuntimeException("Email exists");
        }
        return userRepository.save(user);
    }
}
```

---

## 3. 服务规范

### 服务实现

```java
@Service
@RequiredArgsConstructor
@Transactional
public class UserServiceImpl implements UserService {
    
    private final UserRepository userRepository;
    private final UserMapper userMapper;
    
    @Override
    public List<UserDTO> findAll() {
        return userRepository.findAll().stream()
            .map(userMapper::toDTO)
            .toList();
    }
    
    @Override
    public Optional<UserDTO> findById(String id) {
        return userRepository.findById(id)
            .map(userMapper::toDTO);
    }
    
    @Override
    public UserDTO create(CreateUserDTO dto) {
        if (userRepository.existsByEmail(dto.getEmail())) {
            throw new BusinessException("Email already exists");
        }
        
        User user = userMapper.toEntity(dto);
        User saved = userRepository.save(user);
        return userMapper.toDTO(saved);
    }
    
    @Override
    @Transactional(readOnly = true)
    public boolean existsByEmail(String email) {
        return userRepository.existsByEmail(email);
    }
}
```

---

## 4. 仓库规范

### Spring Data JPA

```java
public interface UserRepository extends JpaRepository<User, String> {
    
    // ✅ 正确: 方法命名查询
    Optional<User> findByEmail(String email);
    boolean existsByEmail(String email);
    List<User> findByRole(Role role);
    
    // ✅ 正确: JPQL 查询
    @Query("SELECT u FROM User u WHERE u.createdAt > :date")
    List<User> findRecentUsers(@Param("date") LocalDateTime date);
}
```

---

## 5. 异常处理

### 全局异常处理

```java
@RestControllerAdvice
public class GlobalExceptionHandler {
    
    @ExceptionHandler(NotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(NotFoundException ex) {
        return ResponseEntity
            .status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse(ex.getMessage()));
    }
    
    @ExceptionHandler(ValidationException.class)
    public ResponseEntity<ErrorResponse> handleValidation(ValidationException ex) {
        return ResponseEntity
            .badRequest()
            .body(new ErrorResponse(ex.getMessage()));
    }
    
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneral(Exception ex) {
        return ResponseEntity
            .status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new ErrorResponse("Internal server error"));
    }
}
```

---

## 6. 测试规范

### 单元测试

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {
    
    @Mock
    private UserRepository userRepository;
    
    @Mock
    private UserMapper userMapper;
    
    @InjectMocks
    private UserServiceImpl userService;
    
    @Test
    void shouldReturnUserWhenFound() {
        // Given
        User user = new User("1", "test@example.com");
        UserDTO dto = new UserDTO("1", "test@example.com");
        
        when(userRepository.findById("1")).thenReturn(Optional.of(user));
        when(userMapper.toDTO(user)).thenReturn(dto);
        
        // When
        Optional<UserDTO> result = userService.findById("1");
        
        // Then
        assertThat(result).isPresent();
        assertThat(result.get().getEmail()).isEqualTo("test@example.com");
    }
}
```

### 集成测试

```java
@SpringBootTest
@AutoConfigureMockMvc
class UserControllerTest {
    
    @Autowired
    private MockMvc mockMvc;
    
    @Test
    void shouldReturnUser() throws Exception {
        mockMvc.perform(get("/api/users/1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.email").value("test@example.com"));
    }
}
```

---

## 7. 配置规范

### 配置类

```java
@Configuration
@EnableWebMvc
public class WebConfig implements WebMvcConfigurer {
    
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
            .allowedOrigins("https://example.com")
            .allowedMethods("GET", "POST", "PUT", "DELETE");
    }
}
```

### 属性绑定

```java
@ConfigurationProperties(prefix = 'app')
@Validated
public record AppProperties(
    @NotBlank String apiKey,
    @Positive int maxRetries,
    @Email String adminEmail
) {}
```

---

## 8. 安全规范

### Spring Security

```java
@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {
    
    private final JwtAuthenticationFilter jwtFilter;
    
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(csrf -> csrf.disable())
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .anyRequest().authenticated()
            )
            .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)
            .build();
    }
}
```

---

## 9. 质量检查清单

### 代码质量

- [ ] Checkstyle 通过
- [ ] 无空 catch 块
- [ ] 使用 DTO 而非实体
- [ ] 无硬编码密钥
- [ ] 异常处理完整

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] Mock 使用正确
- [ ] 集成测试覆盖关键流程

### 安全

- [ ] Spring Security 正确配置
- [ ] JWT 认证完整
- [ ] 输入验证完整

---

*本规范随 Spring Boot 生态演进持续更新。最后更新: 2026-07-17*
