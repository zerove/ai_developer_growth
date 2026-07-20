# Kotlin 示例项目

> 配合 ai-dev-framework 使用的 Kotlin 项目模板

---

## 项目结构

```
src/
├── main/
│   └── kotlin/
│       └── com/example/
│           ├── App.kt
│           └── service/
└── test/
    └── kotlin/
        └── com/example/
            └── AppTest.kt
build.gradle.kts        # Gradle 配置
.editorconfig           # 编辑器配置
```

---

## 质量门禁

```bash
# Lint
./gradlew ktlintCheck

# 测试
./gradlew test

# 检测安全
./gradlew detekt
```

---

## build.gradle.kts

```kotlin
plugins {
    kotlin("jvm") version "1.9.22"
    id("org.jlleitschuh.gradle.ktlint") version "12.1.0"
    id("io.gitlab.arturbosch.detekt") version "1.23.6"
}

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
}
```
