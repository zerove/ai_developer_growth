# C# 示例项目

> 配合 ai-dev-framework 使用的 C# 项目模板

---

## 项目结构

```
.
├── MyApp/
│   ├── Program.cs
│   ├── MyApp.csproj
│   └── Services/
├── MyApp.Tests/
│   ├── MyApp.Tests.csproj
│   └── UnitTest1.cs
├── MyApp.sln
└── .editorconfig
```

---

## 质量门禁

```bash
# 格式化
dotnet format --verify-no-changes

# 构建 + 类型检查
dotnet build

# 测试
dotnet test

# 安全检查
dotnet list package --vulnerable
```

---

## Program.cs

```csharp
using Microsoft.AspNetCore.Builder;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();

var app = builder.Build();
app.MapControllers();

app.Run();
```

## MyApp.csproj

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
```
