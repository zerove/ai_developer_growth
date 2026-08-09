---
title: PHP Governance Rules
description: > 适用于 PHP 项目的 AI Agent 开发规范。
category: 治理层
tags: ['测试', 'AI', 'SQL', 'API']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# PHP Governance Rules

> 适用于 PHP 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: PHP-CS-Fixer 或 PHP_CodeSniffer
- **缩进**: 4 空格
- **行宽**: 120 字符
- **花括号**: PSR-12 风格

### Linting

- **工具**: PHPStan 或 Psalm
- **级别**: Level 8 (PHPStan)
- **静态分析**: SonarQube

### 命名规范

```php
// ✅ 正确
class UserService { ... }
function getUser(string $id): User { ... }
const MAX_RETRIES = 3;

// ❌ 禁止
class userService { ... }  // 应为 PascalCase
function GetUser(string $id) { ... }  // 应为 camelCase
```

---

## 2. 错误处理

### 自定义异常

```php
class AppException extends Exception
{
    protected string $code;

    public function __construct(string $message, string $code)
    {
        parent::__construct($message);
        $this->code = $code;
    }

    public function getCode(): string
    {
        return $this->code;
    }
}

class ValidationException extends AppException
{
    public function __construct(
        private string $field,
        string $message
    ) {
        parent::__construct($message, 'VALIDATION_ERROR');
    }

    public function getField(): string
    {
        return $this->field;
    }
}

class NotFoundException extends AppException
{
    public function __construct(string $resource, string $id)
    {
        parent::__construct(
            "{$resource} with id {$id} not found",
            'NOT_FOUND'
        );
    }
}
```

### 禁止行为

```php
// ❌ 禁止: 空 catch
try {
    doSomething();
} catch (Exception $e) {
    // 忽略
}

// ❌ 禁止: 使用异常控制流
try {
    return $array[$key];
} catch (Exception $e) {
    return $defaultValue;
}

// ✅ 正确
return $array[$key] ?? $defaultValue;
```

---

## 3. 现代 PHP 特性

### 类型声明

```php
// ❌ 禁止: 无类型
function process($data) {
    return $data['key'];
}

// ✅ 正确
function process(array $data): string
{
    return $data['key'] ?? '';
}
```

### 枚举 (PHP 8.1+)

```php
// ✅ 正确
enum Status: string
{
    case Active = 'active';
    case Inactive = 'inactive';
    case Pending = 'pending';
}

// ❌ 禁止: 使用常量代替
class Status
{
    const ACTIVE = 'active';
    const INACTIVE = 'inactive';
    const PENDING = 'pending';
}
```

### 命名参数 (PHP 8.0+)

```php
// ✅ 正确
$user = new User(
    name: 'John',
    email: 'john@example.com',
    role: Role::User
);

// ❌ 禁止: 位置参数过多
$user = new User('John', 'john@example.com', Role::User, true, null);
```

---

## 4. 依赖管理

### Composer

```json
{
    "require": {
        "php": "^8.2",
        "symfony/framework-bundle": "^6.4"
    },
    "require-dev": {
        "phpunit/phpunit": "^10.0",
        "phpstan/phpstan": "^1.10"
    }
}
```

### 自动加载

```php
// composer.json
{
    "autoload": {
        "psr-4": {
            "App\\": "src/"
        }
    }
}
```

---

## 5. 测试规范

### PHPUnit

```php
use PHPUnit\Framework\TestCase;

class UserServiceTest extends TestCase
{
    private UserService $service;

    protected function setUp(): void
    {
        $this->service = new UserService();
    }

    public function testGetUserReturnsUserWhenFound(): void
    {
        $user = $this->service->getUser('123');
        $this->assertEquals('123', $user->getId());
    }

    public function testGetUserThrowsWhenNotFound(): void
    {
        $this->expectException(NotFoundException::class);
        $this->service->getUser('nonexistent');
    }
}
```

### Mock 框架

```php
use PHPUnit\Framework\MockObject\MockBuilder;

class UserServiceTest extends TestCase
{
    public function testGetUser(): void
    {
        $repository = $this->createMock(UserRepository::class);
        $repository->expects($this->once())
            ->method('findById')
            ->with('123')
            ->willReturn(new User('123'));

        $service = new UserService($repository);
        $user = $service->getUser('123');

        $this->assertNotNull($user);
    }
}
```

---

## 6. 项目结构

```
project/
├── src/
│   ├── Controller/
│   ├── Service/
│   ├── Repository/
│   ├── Model/
│   └── Exception/
├── tests/
├── composer.json
└── README.md
```

---

## 7. 安全规范

### SQL 注入防护

```php
// ❌ 禁止: 字符串拼接
$query = "SELECT * FROM users WHERE id = '{$userId}'";

// ✅ 正确: 使用 PDO
$stmt = $pdo->prepare('SELECT * FROM users WHERE id = :id');
$stmt->execute(['id' => $userId]);
$user = $stmt->fetch();
```

### 密钥管理

```php
// ❌ 禁止
$apiKey = 'YOUR_API_KEY_HERE';

// ✅ 正确
$apiKey = getenv('API_KEY');
if ($apiKey === false) {
    throw new \RuntimeException('API_KEY not set');
}
```

---

## 8. 质量检查清单

### 代码质量

- [ ] PHP-CS-Fixer 通过
- [ ] PHPStan 无错误 (Level 8)
- [ ] 无空 catch 块
- [ ] 无 `@` 错误抑制
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] Mock 使用正确
- [ ] 无共享状态

### 文档质量

- [ ] 所有公开类有 PHPDoc
- [ ] 复杂逻辑有注释
- [ ] README.md 已更新

---

*本规范随 PHP 生态演进持续更新。最后更新: 2026-07-17*
