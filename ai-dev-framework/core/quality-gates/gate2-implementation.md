# Gate 2: 实现编码审查

> 语言无关的实现编码审查标准

---

## 检查项

| # | 检查项 | 验证方式 | 通过标准 |
|---|--------|----------|----------|
| 2.1 | Linter 通过 | 自动执行 linter | 0 errors |
| 2.2 | 类型检查通过 | 自动执行类型检查 | 0 errors |
| 2.3 | 测试通过 | 自动执行测试套件 | 100% passed |
| 2.4 | 安全扫描 | 自动执行安全扫描 | 0 critical/high |
| 2.5 | 代码格式 | 自动执行格式化检查 | 符合项目规范 |

---

## 语言特定工具

| 语言 | Linter | 类型检查 | 测试工具 | 安全扫描 |
|------|--------|----------|----------|----------|
| Python | ruff | mypy | pytest | bandit |
| Rust | clippy | rustc | cargo test | cargo audit |
| Go | golangci-lint | go vet | go test | govulncheck |
| Java | checkstyle | javac | junit | spotbugs |
| TypeScript | eslint | tsc | jest/vitest | npm audit |
| Swift | swiftlint | swiftc | xctest | swift-format |
| Kotlin | ktlint | kotlinc | kotest | detekt |
| Ruby | rubocop | ruby -c | rspec | bundle-audit |
| PHP | phpstan | php -l | phpunit | php-cs-fixer |
| C# | dotnet format | dotnet build | dotnet test | dotnet list package |

---

## 审查清单

### 代码质量

- [ ] Linter 检查通过 (0 errors)
- [ ] 类型检查通过 (0 errors)
- [ ] 代码格式符合规范
- [ ] 无重复代码
- [ ] 无死代码

### 测试覆盖

- [ ] 单元测试通过 (100%)
- [ ] 集成测试通过 (100%)
- [ ] 覆盖率 ≥ 70%
- [ ] 测试包含边界情况

### 安全性

- [ ] 安全扫描通过 (0 critical)
- [ ] 无硬编码密钥
- [ ] 无 SQL 注入风险
- [ ] 无 XSS 风险

---

## 审查结果

| 状态 | 说明 |
|------|------|
| ✅ PASS | 所有检查项通过 |
| ⚠️ WARNING | 有警告，可酌情通过 |
| ❌ FAIL | 有严重问题，必须修复 |

---

*本检查项适用于任何语言的实现编码审查。*
