# AI Dev Framework

> 通用的 AI Agent 开发治理标准，适用于任何项目、任何编程语言。

---

## 特性

- ✅ **语言无关**: 支持 Python, Rust, Go, Java, TypeScript 等 13+ 种语言
- ✅ **工具集成**: 支持 opencode, jcode, pre-commit
- ✅ **质量门禁**: 4 道门禁确保代码质量
- ✅ **一键安装**: 简单的安装脚本

---

## 快速开始

### 安装

```bash
# 克隆框架
git clone https://github.com/your-org/ai-dev-framework.git
cd ai-dev-framework

# 安装到你的项目
./install.sh /path/to/your/project python
```

### 使用

1. 阅读 `GOVERNANCE.md`
2. 使用 `templates/agent-prompt.md` 创建 agent
3. 通过 4 道质量门禁
4. 定期更新上下文文件

---

## 目录结构

```
ai-dev-framework/
├── core/                          # 核心框架 (语言无关)
│   ├── GOVERNANCE.md              # 通用治理标准
│   ├── quality-gates/             # 质量门禁
│   └── templates/                 # 模板
├── languages/                     # 语言特定配置
│   ├── python/
│   ├── rust/
│   ├── go/
│   ├── java/
│   └── typescript/
├── hooks/                         # 工具集成
│   ├── opencode/
│   ├── jcode/
│   └── pre-commit/
├── examples/                      # 示例项目
└── install.sh                     # 一键安装
```

---

## 支持的语言

| 语言 | Lint 工具 | 测试工具 | 安全检查 |
|------|-----------|----------|----------|
| Python | ruff | pytest | bandit |
| Rust | clippy | cargo test | cargo audit |
| Go | golangci-lint | go test | govulncheck |
| Java | checkstyle | junit | spotbugs |
| TypeScript | eslint | jest/vitest | npm audit |
| Swift | swiftlint | xcodebuild/swift test | swift-format |
| Kotlin | ktlint | gradle/mvn test | detekt |
| Ruby | rubocop | rspec | bundle-audit |
| PHP | phpstan | phpunit | php-cs-fixer |
| C# | dotnet format | dotnet test | dotnet list package |

---

## 工具集成

### opencode

```json
// .opencode/hooks.json
{
  "pre_prompt": [
    {
      "name": "check-governance",
      "command": "bash .ai-framework/quality-gates/scripts/check.sh"
    }
  ]
}
```

### jcode

```yaml
# .jcode/config.yml
governance:
  enabled: true
  hooks:
    pre_commit:
      - command: "bash .ai-framework/quality-gates/scripts/check.sh"
```

### pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: governance-check
        name: Governance Check
        entry: bash .ai-framework/quality-gates/scripts/check.sh
        language: system
```

---

## 质量门禁

| Gate | 检查内容 | 通过标准 |
|------|----------|----------|
| Gate 1 | Prompt 设计 | 名称格式、描述完整、指令具体 |
| Gate 2 | 实现编码 | 代码通过 linter、无类型错误 |
| Gate 3 | 自动化审计 | Linter、测试、安全扫描通过 |
| Gate 4 | 资产更新 | CONTEXT.md、ADR.md 已更新 |

---

## 添加新语言

1. 创建 `languages/{language}/` 目录
2. 创建 `rules.md` - 语言规则
3. 创建 `check.sh` - 质量门禁脚本
4. 创建 `example/` - 示例项目
5. 更新 README.md

---

## 贡献

欢迎贡献新语言、新框架、新工具集成。

详见 `CONTRIBUTING.md`。

---

*本框架适用于任何项目、任何编程语言。*
