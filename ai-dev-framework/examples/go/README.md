# Go 示例项目

这是一个最小化的 Go 示例项目，展示如何使用 ai-dev-framework。

---

## 项目结构

```
go-example/
├── pkg/
│   └── math/
│       └── math.go       # 主模块
├── internal/
│   └── calc/
│       └── calc.go       # 内部模块
├── CLAUDE.md             # 项目规范
├── AGENTS.md             # Agent 索引
├── CONTEXT.md            # 项目上下文
└── go.mod                # 项目配置
```

---

## 快速开始

```bash
# 构建项目
go build ./...

# 运行测试
go test ./...

# 代码检查
golangci-lint run
```

---

## Agent 示例

### pkg/math/math.go

```go
// Package math 提供数学函数。
package math

// Add 两个数相加。
//
// Arguments:
//   - a: 第一个数
//   - b: 第二个数
//
// Returns:
//   - int: 两数之和
func Add(a, b int) int {
	return a + b
}
```

### pkg/math/math_test.go

```go
package math

import "testing"

func TestAddSuccess(t *testing.T) {
	result := Add(1, 2)
	if result != 3 {
		t.Errorf("expected 3, got %d", result)
	}
}

func TestAddNegative(t *testing.T) {
	result := Add(-1, 1)
	if result != 0 {
		t.Errorf("expected 0, got %d", result)
	}
}
```

---

## 质量门禁检查

```bash
# 检查代码质量
bash .ai-framework/quality-gates/scripts/check.sh go
```

---

*这是一个最小化的 Go 示例项目。*
