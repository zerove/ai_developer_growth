# Swift 示例项目

> 配合 ai-dev-framework 使用的 Swift 项目模板

---

## 项目结构

```
Sources/
├── App/
│   ├── main.swift
│   └── App.swift
Tests/
├── AppTests/
│   └── AppTests.swift
Package.swift              # Swift Package Manager
.swiftlint.yml             # SwiftLint 配置
```

---

## 质量门禁

```bash
# Lint
swiftlint lint --strict

# 测试
swift test --parallel

# 构建检查
swift build
```

---

## Package.swift

```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MyApp",
    platforms: [.macOS(.v14), .iOS(.v17)],
    dependencies: [
        .package(url: "https://github.com/apple/swift-argument-parser", from: "1.2.0"),
    ],
    targets: [
        .executableTarget(
            name: "MyApp",
            dependencies: [
                .product(name: "ArgumentParser", package: "swift-argument-parser"),
            ]
        ),
        .testTarget(
            name: "MyAppTests",
            dependencies: ["MyApp"]
        ),
    ]
)
```
