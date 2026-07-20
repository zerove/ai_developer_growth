# Java 语言规则

> 适用于 Java 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | PascalCase | `MyClass.java` |
| 方法名 | camelCase | `myMethod()` |
| 变量名 | camelCase | `myVariable` |
| 类名 | PascalCase | `MyClass` |
| 接口 | PascalCase | `MyInterface` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SIZE` |
| 包名 | 小写 | `com.example.mypackage` |

### 导入顺序

```java
// 1. java.* 包
import java.util.List;
import java.util.Map;

// 2. javax.* 包
import javax.servlet.http.HttpServletRequest;

// 3. 第三方库
import org.springframework.web.bind.annotation.*;

// 4. 本地模块
import com.example.mypackage.MyClass;
```

---

## 错误处理

### 惯用模式

```java
// ✅ 正确
public String myFunction() throws MyException {
    try {
        String result = doSomething();
        return result;
    } catch (SpecificException e) {
        throw new MyException("Failed to do something", e);
    }
}

// ❌ 错误
public String myFunction() {
    try {
        String result = doSomething();
        return result;
    } catch (Exception e) {
        return null;
    }
}
```

---

## 测试

### 框架选择

| 框架 | 适用场景 |
|------|----------|
| JUnit 5 | 通用测试 |
| Mockito | Mock 框架 |
| AssertJ | 断言库 |

### 测试结构

```java
@Test
void testMyFunctionSuccess() {
    String result = myFunction(1, 2);
    assertEquals("3", result);
}

@Test
void testMyFunctionError() {
    assertThrows(MyException.class, () -> {
        myFunction(null, 2);
    });
}
```

---

## 文档

### Javadoc

```java
/**
 * 一句话描述函数功能。
 *
 * @param param1 参数1描述
 * @param param2 参数2描述
 * @return 返回值描述
 * @throws MyException 当参数无效时
 */
public String myFunction(int param1, String param2) throws MyException {
    return "";
}
```

---

## 工具配置

### Maven

```xml
<!-- pom.xml -->
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-checkstyle-plugin</artifactId>
    <version>3.3.0</version>
</plugin>
```

### Gradle

```groovy
// build.gradle
plugins {
    id 'checkstyle'
}

checkstyle {
    toolVersion = '10.12.5'
}
```

---

*本规则适用于 Java 项目的 AI Agent 开发。*
