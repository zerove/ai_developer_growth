# Java 示例项目

这是一个最小化的 Java 示例项目，展示如何使用 ai-dev-framework。

---

## 项目结构

```
java-example/
├── src/
│   └── main/
│       └── java/
│           └── com/
│               └── example/
│                   └── MathUtils.java
│   └── test/
│       └── java/
│           └── com/
│               └── example/
│                   └── MathUtilsTest.java
├── CLAUDE.md             # 项目规范
├── AGENTS.md             # Agent 索引
├── CONTEXT.md            # 项目上下文
└── pom.xml               # 项目配置
```

---

## 快速开始

```bash
# 构建项目
mvn compile

# 运行测试
mvn test

# 代码检查
mvn checkstyle:check
```

---

## Agent 示例

### src/main/java/com/example/MathUtils.java

```java
package com.example;

/**
 * 数学工具类。
 */
public class MathUtils {

    /**
     * 两个数相加。
     *
     * @param a 第一个数
     * @param b 第二个数
     * @return 两数之和
     */
    public static int add(int a, int b) {
        return a + b;
    }
}
```

### src/test/java/com/example/MathUtilsTest.java

```java
package com.example;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class MathUtilsTest {

    @Test
    void testAddSuccess() {
        assertEquals(3, MathUtils.add(1, 2));
    }

    @Test
    void testAddNegative() {
        assertEquals(0, MathUtils.add(-1, 1));
    }
}
```

---

## 质量门禁检查

```bash
# 检查代码质量
bash .ai-framework/quality-gates/scripts/check.sh java
```

---

*这是一个最小化的 Java 示例项目。*
