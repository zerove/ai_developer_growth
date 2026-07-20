# Kotlin 语言规则

> 适用于 Kotlin 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | PascalCase | `MyModule.kt` |
| 函数名 | camelCase | `myFunction()` |
| 变量名 | camelCase | `myVariable` |
| 类名 | PascalCase | `MyClass` |
| 接口 | PascalCase | `MyInterface` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SIZE` |

### 导入顺序

```kotlin
// 1. 标准库
import kotlinx.coroutines.*
import java.util.*

// 2. 第三方库
import com.squareup.moshi.*

// 3. 本地模块
import com.example.mypackage.MyClass
```

---

## 错误处理

```kotlin
// ✅ 正确
fun myFunction(): Result<String> {
    return runCatching {
        doSomething()
    }.mapError { error ->
        MyError("Failed to do something", error)
    }
}

// ❌ 错误
fun myFunction(): String? {
    return try {
        doSomething()
    } catch (e: Exception) {
        null
    }
}
```

---

## 测试

```kotlin
import io.kotest.core.spec.style.StringSpec
import io.kotest.matchers.shouldBe

class MyFunctionTest : StringSpec({
    "should return correct result" {
        myFunction(1, 2) shouldBe 3
    }
    
    "should throw error for invalid input" {
        shouldThrow<MyError> { myFunction(null, 2) }
    }
})
```

---

*本规则适用于 Kotlin 项目的 AI Agent 开发。*
