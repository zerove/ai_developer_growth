---
title: C# Governance Rules
description: > 适用于 C# 项目的 AI Agent 开发规范。
category: 治理层
tags: ['AI', 'API', '测试', 'SQL', 'LLM']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# C# Governance Rules

> 适用于 C# 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: dotnet format 或 EditorConfig
- **缩进**: 4 空格
- **行宽**: 120 字符
- **花括号**: Allman 风格

### Linting

- **工具**: Roslyn Analyzers
- **规则**: 启用所有警告
- **代码质量**: SonarQube

### 命名规范

```csharp
// ✅ 正确
public class UserService { ... }
public void GetUser(string id) { ... }
private const int MaxRetries = 3;

// ❌ 禁止
public class userService { ... }  // 应为 PascalCase
public void GetUser(string id) { ... }  // 应为 camelCase
```

---

## 2. 错误处理

### 自定义异常层次

```csharp
public class AppException : Exception
{
    public string Code { get; }

    public AppException(string message, string code)
        : base(message)
    {
        Code = code;
    }
}

public class ValidationException : AppException
{
    public string Field { get; }

    public ValidationException(string field, string message)
        : base(message, "VALIDATION_ERROR")
    {
        Field = field;
    }
}

public class NotFoundException : AppException
{
    public NotFoundException(string resource, string id)
        : base($"{resource} with id {id} not found", "NOT_FOUND")
    {
    }
}
```

### 禁止行为

```csharp
// ❌ 禁止: 空 catch
try
{
    DoSomething();
}
catch (Exception)
{
    // 忽略
}

// ❌ 禁止: 使用异常控制流
try
{
    return dictionary[key];
}
catch (KeyNotFoundException)
{
    return defaultValue;
}

// ✅ 正确
return dictionary.TryGetValue(key, out var value) ? value : defaultValue;
```

---

## 3. 现代 C# 特性

### Nullable Reference Types

```csharp
// 启用: <Nullable>enable</Nullable>

// ❌ 禁止: 不检查 null
string Process(string? input)
{
    return input.ToUpper();  // 可能 null!
}

// ✅ 正确
string Process(string? input)
{
    return input?.ToUpper() ?? string.Empty;
}
```

### Records

```csharp
// ✅ 正确: 使用 record 代替 DTO
public record UserDTO(string Id, string Name, string Email);

// ❌ 禁止: 手动编写 DTO
public class UserDTO
{
    public string Id { get; set; }
    public string Name { get; set; }
    public string Email { get; set; }
}
```

### Pattern Matching

```csharp
// ✅ 正确
string GetDescription(object obj) => obj switch
{
    int i when i > 0 => "Positive integer",
    int i => "Non-positive integer",
    string s => $"String: {s}",
    null => "Null",
    _ => "Unknown"
};
```

---

## 4. 异步编程

### async/await

```csharp
// ✅ 正确
public async Task<User> GetUserAsync(string id)
{
    using var client = new HttpClient();
    var response = await client.GetAsync($"/users/{id}");
    response.EnsureSuccessStatusCode();
    return await response.Content.ReadFromJsonAsync<User>();
}

// ✅ 正确: 并发执行
public async Task<List<User>> GetUsersAsync(IEnumerable<string> ids)
{
    var tasks = ids.Select(GetUserAsync);
    return (await Task.WhenAll(tasks)).ToList();
}
```

### 禁止行为

```csharp
// ❌ 禁止: 同步阻塞
var result = GetUserAsync(id).Result;

// ❌ 禁止: .Result 或 .Wait()
task.Wait();
task.Result;
```

---

## 5. 测试规范

### xUnit 结构

```csharp
public class UserServiceTests
{
    private readonly UserService _service;

    public UserServiceTests()
    {
        _service = new UserService();
    }

    [Fact]
    public async Task GetUser_ReturnsUser_WhenFound()
    {
        var user = await _service.GetUserAsync("123");
        Assert.Equal("123", user.Id);
    }

    [Fact]
    public async Task GetUser_Throws_WhenNotFound()
    {
        await Assert.ThrowsAsync<NotFoundException>(() =>
            _service.GetUserAsync("nonexistent"));
    }
}
```

### Mock 框架 (Moq)

```csharp
public class UserServiceTests
{
    private readonly Mock<IUserRepository> _repositoryMock;
    private readonly UserService _service;

    public UserServiceTests()
    {
        _repositoryMock = new Mock<IUserRepository>();
        _service = new UserService(_repositoryMock.Object);
    }

    [Fact]
    public async Task GetUser_ReturnsUser()
    {
        _repositoryMock
            .Setup(r => r.GetByIdAsync("123"))
            .ReturnsAsync(new User("123"));

        var user = await _service.GetUserAsync("123");
        Assert.NotNull(user);
        _repositoryMock.Verify(r => r.GetByIdAsync("123"), Times.Once);
    }
}
```

---

## 6. 项目结构

```
project/
├── src/
│   ├── Project.Api/
│   │   ├── Controllers/
│   │   ├── Services/
│   │   ├── Repositories/
│   │   └── Program.cs
│   ├── Project.Core/
│   │   ├── Models/
│   │   └── Interfaces/
│   └── Project.Infrastructure/
│       └── Data/
├── tests/
│   └── Project.Tests/
├── Project.sln
└── README.md
```

---

## 7. 依赖管理

### NuGet

```xml
<ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />
    <PackageReference Include="xunit" Version="2.5.0" />
</ItemGroup>
```

### 依赖注入

```csharp
// Program.cs
builder.Services.AddScoped<IUserService, UserService>();
builder.Services.AddScoped<IUserRepository, UserRepository>();
```

---

## 8. 安全规范

### SQL 注入防护

```csharp
// ❌ 禁止: 字符串拼接
var query = $"SELECT * FROM Users WHERE Id = '{userId}'";

// ✅ 正确: 使用参数化查询
var user = await context.Users
    .FromSqlInterpolated($"SELECT * FROM Users WHERE Id = {userId}")
    .FirstOrDefaultAsync();
```

### 密钥管理

```csharp
// ❌ 禁止
var apiKey = "YOUR_API_KEY_HERE";

// ✅ 正确
var apiKey = configuration["ApiKey"];
```

---

## 9. 质量检查清单

### 代码质量

- [ ] dotnet format 通过
- [ ] 无编译警告
- [ ] 无空 catch 块
- [ ] 启用 Nullable Reference Types
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] Mock 使用正确
- [ ] 无共享可变状态

### 文档质量

- [ ] 所有公开类有 XML 注释
- [ ] 复杂逻辑有注释
- [ ] README.md 已更新

---

*本规范随 .NET 生态演进持续更新。最后更新: 2026-07-17*
