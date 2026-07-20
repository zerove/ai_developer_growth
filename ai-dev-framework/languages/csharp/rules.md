# C# 语言规则

> 适用于 C# 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | PascalCase | `MyClass.cs` |
| 方法名 | PascalCase | `MyMethod()` |
| 变量名 | camelCase | `myVariable` |
| 类名 | PascalCase | `MyClass` |
| 接口 | IPascalCase | `IMyInterface` |
| 属性 | PascalCase | `MyProperty` |
| 常量 | PascalCase | `MaxSize` |

### 导入顺序

```csharp
// 1. 标准库
using System;
using System.Collections.Generic;

// 2. 第三方库
using Newtonsoft.Json;
using Microsoft.EntityFrameworkCore;

// 3. 本地模块
using MyProject.Services;
```

---

## 错误处理

```csharp
// ✅ 正确
public async Task<string> MyFunctionAsync()
{
    try
    {
        var result = await DoSomethingAsync();
        return result;
    }
    catch (SpecificException ex) when (ex.ErrorCode == 100)
    {
        throw new MyException("Failed", ex);
    }
}

// ❌ 错误
public async Task<string?> MyFunctionAsync()
{
    try
    {
        return await DoSomethingAsync();
    }
    catch
    {
        return null;
    }
}
```

---

## 测试

```csharp
[TestFixture]
public class MyFunctionTests
{
    [Test]
    public void TestSuccess()
    {
        var result = MyClass.MyFunction(1, 2);
        Assert.That(result, Is.EqualTo(3));
    }

    [Test]
    public void TestError()
    {
        Assert.Throws<MyException>(() => MyClass.MyFunction(null, 2));
    }
}
```

---

*本规则适用于 C# 项目的 AI Agent 开发。*
