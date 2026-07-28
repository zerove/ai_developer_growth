# Scala 语言规则

> 适用于 Scala OOP-Functional 项目

---

## 代码风格

| 元素 | 规范 | 示例 |
|------|------|------|
| 文件名 | snake_case | `scala_module.scala` |
| 函数 | snake_case | `my_function()` |
| 类 | PascalCase | `MyClass` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SIZE` |

### 格式化

```
scalafmt .
```

---

## 错误处理

```
# ✅ 正确
try { specific_operation() }
catch (SpecificError) { handle() }

# ❌ 错误: 空捕获
try { operation() } catch { }
```

---

## 测试

| 框架 | 用途 |
|------|------|
| scalatest | 通用测试 |

```
scalatest .
```

---

## AI 反模式

### 硬编码值
```
# ❌
url = "http://localhost:8080"

# ✅
url = get_config("API_URL", "http://localhost:8080")
```

### 忽略错误
```
# ❌
try { x() } catch { }

# ✅
try { x() } catch (e) { log(e); throw }
```

---

## 阈值

| 指标 | 阈值 |
|------|------|
| 函数行数 | 50 |
| 文件行数 | 500 |
| 嵌套深度 | 4 |

---

*验证: `python tools/scripts/validate_language_rules.py --lang scala`*
