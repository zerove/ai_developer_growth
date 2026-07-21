---
title: Scala Governance Rules
description: > 适用于 Scala 项目的 AI Agent 开发规范。
category: 治理层
tags: ['测试', 'AI', 'API']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Scala Governance Rules

> 适用于 Scala 项目的 AI Agent 开发规范。

---

## 1. 代码规范

### 格式化

- **工具**: scalafmt
- **配置**: 使用默认配置
- **缩进**: 2 空格
- **行宽**: 120 字符

### Linting

- **工具**: scalafix
- **规则**: 启用所有规则
- **严格模式**: 启用 strict 模式

### 命名规范

```scala
// ✅ 正确
class UserService { ... }
def getUser(id: String): User = { ... }
val maxRetries = 3

// ❌ 禁止
class userService { ... }  // 应为 PascalCase
def GetUser(id: String): User = { ... }  // 应为 camelCase
```

---

## 2. 函数式编程

### 使用 immutable

```scala
// ✅ 正确
case class User(id: String, name: String)

// ❌ 禁止: 使用 var
class User {
  var id: String = _
  var name: String = _
}

// ✅ 正确: 使用 immutable 集合
val users = List("Alice", "Bob")
val newUsers = users :+ "Charlie"
```

### 使用 Option/Either

```scala
// ✅ 正确: 使用 Option
def findUser(id: String): Option[User] = {
  db.find(id)
}

// ✅ 正确: 使用 Either 处理错误
def processUser(id: String): Either[AppError, User] = {
  for {
    user <- findUser(id).toRight(NotFoundError(id))
    validated <- validateUser(user)
  } yield validated
}

// ❌ 禁止: 使用 null
def findUser(id: String): User = {
  if (exists) user else null  // 应返回 Option
}
```

### 模式匹配

```scala
// ✅ 正确
def processUser(user: User): String = user match {
  case User(_, name) if name.nonEmpty => s"Hello, $name"
  case User(_, _) => "Hello, Unknown"
}

// ❌ 禁止: 使用 isInstanceOf
if (user.isInstanceOf[Admin]) {
  val admin = user.asInstanceOf[Admin]
  processAdmin(admin)
}
```

---

## 3. 并发编程

### Futures

```scala
// ✅ 正确
def processConcurrently(): Future[List[User]] = {
  val futures = ids.map(id => processUser(id))
  Future.sequence(futures)
}

// ✅ 正确: 使用 for 推导式
def processUser(id: String): Future[User] = {
  for {
    user <- fetchUser(id)
    validated <- validateUser(user)
  } yield validated
}
```

### 使用 Akka/Cats Effect

```scala
// ✅ 正确: 使用 Effect 系统
import cats.effect.IO

def processUser(id: String): IO[User] = {
  for {
    user <- fetchUser(id)
    validated <- validateUser(user)
  } yield validated
}

// ❌ 禁止: 在 Future 中使用阻塞
def badExample(): Future[User] = {
  Future {
    blockingOperation()  // 阻塞!
  }
}
```

---

## 4. 测试规范

### ScalaTest

```scala
import org.scalatest.funsuite.AnyFunSuite

class UserServiceTest extends AnyFunSuite {
  test("getUser returns user when found") {
    val service = new UserService()
    val user = service.getUser("123")
    assert(user.id == "123")
  }
  
  test("getUser throws when not found") {
    val service = new UserService()
    assertThrows[NotFoundException] {
      service.getUser("nonexistent")
    }
  }
}
```

### ScalaCheck

```scala
import org.scalatestplus.scalacheck.ScalaCheckPropertyChecks

class UserServiceTest extends AnyFunSuite with ScalaCheckPropertyChecks {
  test("getUser always returns valid user") {
    forAll { (id: String) =>
      val service = new UserService()
      whenever(id.nonEmpty) {
        val result = service.getUser(id)
        assert(result.id.nonEmpty)
      }
    }
  }
}
```

---

## 5. 项目结构

```
project/
├── src/
│   ├── main/scala/
│   │   └── com/example/
│   │       ├── models/
│   │       ├── services/
│   │       └── repositories/
│   └── test/scala/
├── build.sbt
└── README.md
```

---

## 6. 安全规范

### 密钥管理

```scala
// ❌ 禁止
val apiKey = "sk-1234567890"

// ✅ 正确
val apiKey = sys.env.getOrElse("API_KEY", 
  throw new RuntimeException("API_KEY not set"))
```

---

## 7. 质量检查清单

### 代码质量

- [ ] scalafmt 通过
- [ ] scalafix 通过
- [ ] 无 null 使用
- [ ] 无 mutable 变量
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用 property-based 测试
- [ ] Mock 使用正确

### 函数式编程

- [ ] 使用 immutable 数据结构
- [ ] 使用 Option/Either 处理空值/错误
- [ ] 使用模式匹配代替类型检查

---

*本规范随 Scala 生态演进持续更新。最后更新: 2026-07-17*
