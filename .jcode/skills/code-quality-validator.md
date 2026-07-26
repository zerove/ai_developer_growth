# code-quality-validator 代码质量验证器

根据语言特定的最佳实践、反模式和质量阈值验证代码输出。

## 使用场景

- 生成或修改任何语言的代码后
- 提交代码变更前
- 审查 AI 生成的代码时
- 为新项目设置质量门禁时

## 功能

1. **检测语言**和框架（从项目文件）
2. **加载语言特定规则**（从 `ai-dev-framework/languages/`）
3. **验证代码**：（错误处理、安全、类型安全、代码质量）
   - 命名规范检查
   - 量化阈值（函数长度、嵌套深度、行长度）
   - AST 分析（Python：复杂度、类型注解）
4. **报告问题**（严重度、修复提示、位置）
5. **建议修复**（针对每个检测到的问题）

## 用法

```
/validate-code
```

或者显式指定：
- 验证特定文件：`validate_language_rules.py <file> --lang python`
- 验证整个项目：`validate_language_rules.py <dir> --auto-detect`
- JSON 输出：`validate_language_rules.py <path> --json`

## 支持的语言

| 语言 | 反模式 | 命名 | 阈值 | 工具 |
|------|--------|------|------|------|
| Python | 21 | 4 | 7 | ruff/mypy |
| TypeScript | 17 | 5 | 6 | eslint |
| Rust | 15 | 5 | 6 | clippy |
| Go | 16 | 5 | 6 | golangci |
| Java | 17 | 4 | 6 | checkstyle |
| Kotlin | 10 | 4 | 6 | ktlint |
| C# | 13 | 5 | 6 | dotnet |
| PHP | 14 | 4 | 6 | phpcs |
| Ruby | 12 | 4 | 6 | rubocop |
| C/C++ | 13 | 5 | 6 | clang-tidy |
| Swift | 10 | 4 | 6 | swiftlint |
| Scala | 8 | 4 | 5 | scalafix |
| Elixir | 8 | 4 | 5 | credo |
| Lua | 8 | 4 | 5 | luacheck |
| JavaScript | 17 | 5 | 6 | eslint |
| Zig | 8 | 4 | 5 | zig fmt |
| R | 8 | 4 | 5 | lintr |
| Clojure | 8 | 4 | 5 | clj-kondo |
| Haskell | 8 | 4 | 5 | hlint |
| Dart | 8 | 4 | 5 | dart analyze |
| PowerShell | 8 | 4 | 5 | PSScriptAnalyzer |

## 规则类别

### 错误处理
检测裸 except、静默异常吞没、unwrap/expect 误用、忽略的错误。

### 安全
检测 eval/exec、硬编码密钥、SQL 注入、XSS 漏洞、TLS 绕过。

### 类型安全
检测 `any` 类型、可变默认值、缺少注解、不安全转换。

### 代码质量
检测通配符导入、全局声明、生产环境中的 console.log、var 声明。

### 可读性
强制函数长度限制、嵌套深度、行长度、圈复杂度。

## 工作流集成

```
用户请求 → 生成代码 → validate_language_rules.py → 修复问题 → 输出
```

此技能与治理质量门集成：
- **Gate 2**（实现）：反模式检查必须通过
- **Gate 3**（审计）：完整验证套件在 CI 中运行
