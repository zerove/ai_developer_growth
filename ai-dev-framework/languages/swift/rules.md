# Swift 语言规则

> 适用于 Swift 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | PascalCase | `MyModule.swift` |
| 函数名 | camelCase | `myFunction()` |
| 变量名 | camelCase | `myVariable` |
| 类名 | PascalCase | `MyClass` |
| 结构体 | PascalCase | `MyStruct` |
| 协议 | PascalCase | `MyProtocol` |
| 枚举 | PascalCase | `MyEnum` |

### 导入顺序

```swift
// 1. 标准库
import Foundation
import UIKit

// 2. 第三方库
import Alamofire
import SnapKit

// 3. 本地模块
import MyModule
```

---

## 错误处理

```swift
// ✅ 正确
func myFunction() throws -> String {
    do {
        let result = try doSomething()
        return result
    } catch let error as MyError {
        throw MyError.wrapped(error)
    }
}

// ❌ 错误
func myFunction() -> String? {
    let result = try? doSomething()
    return result
}
```

---

## 测试

```swift
import XCTest

class MyFunctionTests: XCTestCase {
    func testSuccess() {
        let result = myFunction(1, 2)
        XCTAssertEqual(result, 3)
    }

    func testError() {
        XCTAssertThrowsError(try myFunction(nil, 2))
    }
}
```

---

*本规则适用于 Swift 项目的 AI Agent 开发。*
