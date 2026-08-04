# 核心编程规范 (Language-Agnostic Coding Standards)

> 适用于所有编程语言的通用编码规范，是语言特定规则的超集。

---

## 1. 命名规范

### 1.1 通用命名规则

| 类型 | 规范 | 示例 | 反例 |
|------|------|------|------|
| 变量 | 有意义的名词，camelCase 或 snake_case | `userCount`, `user_count` | `x`, `data1`, `tmp` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` | `maxRetries`, `max_retries` |
| 函数/方法 | 动词开头，描述行为 | `calculateTotal()`, `fetch_user()` | `total()`, `user()` |
| 类/类型 | PascalCase，名词 | `UserService`, `HttpResponse` | `user_service`, `http_response` |
| 布尔值 | `is_`/`has_`/`can_` 前缀 | `isActive`, `has_permission` | `active`, `permission` |
| 私有成员 | 前缀 `_` 或 `private` | `_internal`, `private_field` | `internal`, `field` |

### 1.2 禁止的命名

```yaml
forbidden_patterns:
  - 单字母变量（循环索引除外）: `a`, `b`, `cc`
  - 无意义缩写: `tmp`, `val`, `res`, `ret`
  - 驼峰与蛇形混用: `user_Name`, `get_userName`
  - 保留字变体: `class_name`, `type_`（仅在冲突时加后缀）
  - 布尔值不含判断词: `flag`, `status`（应用 `isReady`, `hasData`）
```

### 1.3 语义化命名

```
好的命名 = 类型 + 语义 + 上下文

❌ data, result, info, temp, obj
✅ userList, errorMessage, retryCount, configFile
```

---

## 2. 函数/方法设计

### 2.1 单一职责原则

```yaml
function_rules:
  max_lines: 50
  max_parameters: 5
  max_return_values: 2
  max_nesting_depth: 4
  max_cognitive_complexity: 15
```

### 2.2 函数结构模板

```
1. 参数验证（Guard Clauses）
2. 核心逻辑（不超过 3 层嵌套）
3. 错误处理
4. 返回结果
```

### 2.3 纯函数优先

```
优先级：
1. 纯函数（无副作用，相同输入相同输出）
2. 只读函数（读取状态但不修改）
3. 命令式函数（修改状态，需明确标注）
```

### 2.4 禁止模式

```yaml
forbidden_function_patterns:
  - Boolean 参数控制行为: `function doSomething(flag: bool)` → 拆分为两个函数
  - 过长参数列表: >5 个参数 → 使用配置对象/结构体
  - 输出参数: 使用返回值代替
  - 混合抽象层级: 函数内不应同时有 `parseHTTP()` 和 `openSocket()`
```

---

## 3. 代码组织

### 3.1 文件结构

```yaml
file_organization:
  max_lines: 500
  max_functions_per_file: 20
  ordering:
    - imports/dependencies
    - constants/configuration
    - types/interfaces
    - private helpers
    - public API
    - exports
```

### 3.2 模块组织

```
project/
├── src/
│   ├── core/           # 核心业务逻辑
│   ├── domain/         # 领域模型
│   ├── application/    # 应用服务
│   ├── infrastructure/ # 外部集成
│   ├── interfaces/     # API/CLI/UI 层
│   └── shared/         # 共享工具
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── docs/
```

### 3.3 依赖方向

```
interfaces → application → domain ← infrastructure
                              ↑
                           shared (无状态工具)
```

**禁止**: domain 层依赖 infrastructure 或 interfaces 层。

---

## 4. 错误处理

### 4.1 错误处理原则

```yaml
error_principles:
  - 不要忽略错误: 空 catch/except 是 bug 温床
  - 不要吞没错误: 捕获后必须记录或重新抛出
  - 使用类型化错误: 自定义错误类型，不用字符串
  - 错误是数据: 错误应该可以被序列化、传递、匹配
  - 快速失败: 在入口处验证，不要让错误数据传播
```

### 4.2 错误层级

```
ApplicationError
├── ValidationError     # 输入验证失败
├── NotFoundError       # 资源不存在
├── ConflictError       # 状态冲突
├── AuthenticationError # 认证失败
├── AuthorizationError  # 授权失败
├── ExternalServiceError # 外部服务故障
└── InternalError       # 内部逻辑错误
```

### 4.3 错误处理禁止

```yaml
forbidden_error_patterns:
  - 空 catch/except 块
  - catch Exception（过于宽泛）
  - 使用字符串作为错误类型
  - 在循环中捕获异常（应在调用层处理）
  - 返回 null/undefined 表示错误（应使用 Result/Either 类型）
  - throw new Error("message具体错误类型）
```

---

## 5. 类型安全

### 5.1 类型使用原则

```yaml
type_safety_rules:
  - 优先使用具体类型，避免 any/unknown
  - 使用联合类型代替布尔标志
  - 使用不可变类型（readonly/frozen）
  - 使用枚举或字面量类型代替魔法字符串
  - 使用泛型约束，不用裸泛型
  - 函数返回类型必须显式声明
```

### 5.2 禁止的类型使用

```yaml
forbidden_type_patterns:
  - `any` / `dynamic`（除非绝对必要且有注释说明）
  - `Object` / `object`（应使用具体类型）
  - 魔法字符串: `"active"` → `const ACTIVE = "active" as const`
  - 可变全局状态
  - 类型断言 `as Type`（优先使用类型守卫）
```

---

## 6. 注释与文档

### 6.1 注释原则

```yaml
comment_rules:
  why_not_what: "注释解释为什么这样做，而不是做了什么"
  public_api_must_doc: "所有公共 API 必须有文档注释"
  no_commented_code: "禁止注释掉的代码（用 git 管理）"
  no_obvious_comments: "不要注释显而易见的事情"
```

### 6.2 TODO/FIXME 规范

```
// TODO(username): [日期] 描述待办事项 - ticket链接
// FIXME(username): [日期] 描述已知问题 - ticket链接
// HACK(username): [日期] 描述临时方案
// DEPRECATED: [日期] 描述废弃原因 - 替代方案
```

**禁止**: 无归属、无日期、无上下文的 TODO。

---

## 7. 代码重复

### 7.1 重复阈值

```yaml
duplication_rules:
  max_duplicate_lines: 6
  max_duplicate_percentage: 5
  exceptions:
    - 测试中的 setup/teardown
    - 配置文件中的相似结构
    - 不同领域的相似但独立的逻辑
```

### 7.2 消除重复策略

```
1. 提取函数（优先）
2. 提取公共模块
3. 使用泛型/模板
4. 使用组合/继承（谨慎）
5. 使用代码生成（最后手段）
```

---

## 8. 安全编码

### 8.1 输入验证

```
- 所有外部输入必须验证
- 使用白名单，不用黑名单
- 验证数据类型、范围、格式
- 在边界处验证，内部可信任
```

### 8.2 敏感数据

```
- 密钥/密码不硬编码
- 日志中不记录敏感信息
- 使用环境变量或密钥管理服务
- 最小权限原则
```

---

## 9. 性能意识

### 9.1 性能规则

```yaml
performance_rules:
  - 先正确，后优化
  - 避免过早优化
  - 热点路径优化
  - 使用适当的数据结构
  - 避免 N+1 查询
  - 使用缓存（但要正确失效）
  - 惰性加载大资源
```

### 9.2 性能禁止

```yaml
forbidden_performance_patterns:
  - 循环内创建数据库连接
  - 同步阻塞异步操作
  - 不必要的深拷贝
  - 全量加载大文件到内存
  - 循环内字符串拼接
```

---

## 10. 可测试性

### 10.1 可测试性设计

```
- 依赖注入，不用全局状态
- 纯函数优先
- 接口抽象，方便 Mock
- 避免静态方法（难以 Mock）
- 配置外部化
```

### 10.2 测试代码标准

```yaml
test_standards:
  - 测试与生产代码同等质量
  - 测试命名：被测行为 + 条件 + 预期结果
  - 每个测试只验证一个行为
  - 使用 AAA 模式：Arrange-Act-Assert
  - 测试数据工厂优于硬编码
  - Mock 外部依赖，不 Mock 被测对象
```

---

## 11. 代码格式

### 11.1 格式化规则

```yaml
formatting_rules:
  indentation: 2 或 4（项目内一致即可）
  max_line_length: 100
  max_function_length: 50 行
  max_file_length: 500 行
  trailing_comma: 始终使用（便于 diff）
  semicolons: 语言默认风格
  quotes: 语言默认风格
```

### 11.

```
必须配置:
- Linter（ESLint, Ruff, Clippy 等）
- Formatter（Prettier, Black, rustfmt 等）
- Pre-commit hooks
- CI 检查
```

---

## 12. 提交规范

### 12.1 Commit Message 格式

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

###

| Type | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
|） |
| refactor | 重构（不新增功能/修复 bug） |
| perf | 性能优化 |
| test | 测试相关 |
| chore | 构建/工具变更 |
| ci | CI/CD 变更 |

### 12
```
feature/TICKET-123-user-authentication
bugfix/TICKET-456-fix-login-error
hotfix/TICKET-789-security-patch
release/v1.2.0
```
