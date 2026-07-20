# Go 语言规则

> 适用于 Go 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | snake_case | `my_module.go` |
| 函数名 | CamelCase | `MyFunction()` |
| 变量名 | CamelCase | `MyVariable` |
| 结构体 | PascalCase | `MyStruct` |
| 接口 | PascalCase | `MyInterface` |
| 常量 | CamelCase | `MaxSize` |
| 包名 | 小写 | `mypackage` |

### 导入顺序

```go
import (
    // 1. 标准库
    "fmt"
    "os"

    // 2. 第三方库
    "github.com/gin-gonic/gin"

    // 3. 本地模块
    "myproject/mypackage"
)
```

---

## 错误处理

### 惯用模式

```go
// ✅ 正确
func MyFunction() (string, error) {
    result, err := DoSomething()
    if err != nil {
        return "", fmt.Errorf("failed to do something: %w", err)
    }
    return result, nil
}

// ❌ 错误
func MyFunction() string {
    result, _ := DoSomething()
    return result
}
```

---

## 测试

### 框架选择

| 框架 | 适用场景 |
|------|----------|
| 内置测试 | 通用测试 |
| testify | 断言库 |
| gomock | Mock 框架 |

### 测试结构

```go
func TestMyFunctionSuccess(t *testing.T) {
    result, err := MyFunction(1, 2)
    if err != nil {
        t.Errorf("unexpected error: %v", err)
    }
    if result != 3 {
        t.Errorf("expected 3, got %d", result)
    }
}

func TestMyFunctionError(t *testing.T) {
    _, err := MyFunction(nil, 2)
    if err == nil {
        t.Error("expected error, got nil")
    }
}
```

---

## 文档

### 文档注释

```go
// MyFunction 一句话描述函数功能。
//
// Arguments:
//   - param1: 参数1描述
//   - param2: 参数2描述
//
// Returns:
//   - string: 返回值描述
//   - error: 错误描述
func MyFunction(param1 int, param2 string) (string, error) {
    return "", nil
}
```

---

## 工具配置

### golangci-lint

```yaml
# .golangci.yml
linters:
  enable:
    - errcheck
    - gosimple
    - govet
    - ineffassign
    - staticcheck
    - unused
```

---

*本规则适用于 Go 项目的 AI Agent 开发。*
