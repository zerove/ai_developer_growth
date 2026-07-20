# AI Dev Framework

> 通用的 AI Agent 开发治理标准，适用于任何项目、任何编程语言。

---

## 特性

- ✅ **语言无关**: 支持 10 种编程语言 (Python, Rust, Go, Java, TypeScript, Swift, Kotlin, Ruby, PHP, C#)
- ✅ **框架配置**: 7 种流行框架开箱可用 (React, Vue, Spring Boot, Next.js, FastAPI, Express, Actix)
- ✅ **工具集成**: 支持 opencode, jcode, pre-commit
- ✅ **质量门禁**: 4 道门禁确保代码质量
- ✅ **模板系统**: 项目上下文、架构决策、Agent 定义、质量报告模板
- ✅ **自检诊断**: 内置诊断脚本验证框架完整性
- ✅ **一键安装**: 自动语言检测 + 配置注入

---

## 快速开始

```bash
# 安装到你的项目 (auto 自动检测语言)
./install.sh /path/to/your/project auto

# 或指定语言
./install.sh /path/to/your/project python
./install.sh /path/to/your/project typescript
```

安装后:
1. 阅读 `.ai-framework/GOVERNANCE.md`
2. 使用模板创建 agent
3. 通过 4 道质量门禁
4. 定期更新上下文文件

---

## 目录结构

```
ai-dev-framework/
├── core/                          # 核心框架 (语言无关)
│   ├── GOVERNANCE.md              # 通用治理标准
│   ├── quality-gates/             # 4 道质量门禁
│   │   ├── gate1-prompt.md        # Gate 1: Prompt 设计
│   │   ├── gate2-implementation.md # Gate 2: 实现编码
│   │   ├── gate3-audit.md         # Gate 3: 自动化审计
│   │   └── gate4-documentation.md # Gate 4: 资产更新
│   └── templates/                 # 项目模板
│       ├── agent-prompt.md        # Agent 定义模板
│       ├── CONTEXT.md             # 项目上下文模板
│       ├── ADR.md                 # 架构决策记录模板
│       ├── AGENTS.md              # Agent 索引模板
│       └── quality-report.md      # 质量报告模板
├── languages/                     # 语言特定配置 (10 种)
│   ├── python/      (check.sh + rules.md)
│   ├── rust/        (check.sh + rules.md)
│   ├── go/          (check.sh + rules.md)
│   ├── java/        (check.sh + rules.md)
│   ├── typescript/  (check.sh + rules.md)
│   ├── swift/       (check.sh + rules.md)
│   ├── kotlin/      (check.sh + rules.md)
│   ├── ruby/        (check.sh + rules.md)
│   ├── php/         (check.sh + rules.md)
│   └── csharp/      (check.sh + rules.md)
├── frameworks/                    # 框架特定配置 (7 种)
│   ├── react/        (rules.md)
│   ├── vue/          (rules.md)
│   ├── spring-boot/  (rules.md)
│   ├── nextjs/       (rules.md)
│   ├── fastapi/      (rules.md)
│   ├── express/      (rules.md)
│   └── actix/        (rules.md)
├── hooks/                         # 工具集成
│   ├── opencode/      (hooks.json)
│   ├── jcode/         (config.yml)
│   └── pre-commit/    (.pre-commit-config.yaml)
├── examples/                      # 示例项目
│   ├── python/
│   ├── rust/
│   ├── go/
│   ├── java/
│   └── typescript/
├── install.sh                     # 一键安装 (自动语言检测)
├── diagnose.sh                    # 框架自检脚本
└── README.md                      # 本文件
```

---

## 支持的语言

| 语言 | Lint 工具 | 类型检查 | 测试工具 | 安全检查 |
|------|-----------|----------|----------|----------|
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

## 框架特定配置

| 框架 | 语言 | 适用场景 |
|------|------|----------|
| React | TypeScript | SPA 前端应用 |
| Vue | TypeScript | SPA 前端应用 |
| Next.js | TypeScript | 全栈 SSR 应用 |
| Spring Boot | Java | 企业后端服务 |
| FastAPI | Python | 高性能 API 服务 |
| Express | TypeScript | Node.js API 服务 |
| Actix Web | Rust | 高性能 Web 服务 |

---

## 质量门禁

| Gate | 阶段 | 检查内容 | 通过标准 |
|------|------|----------|----------|
| Gate 1 | 设计 | Prompt 编写标准 | 名称格式、描述完整、指令具体 |
| Gate 2 | 实现 | 编码审查 | 代码通过 linter、类型检查、测试 |
| Gate 3 | CI/CD | 自动化审计 | Linter、测试、安全扫描自动执行 |
| Gate 4 | 完成 | 资产更新 | CONTEXT.md、ADR.md、AGENTS.md 已更新 |

---

## 工具集成

### opencode

```json
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
governance:
  enabled: true
  hooks:
    pre_commit:
      - command: "bash .ai-framework/quality-gates/scripts/check.sh"
```

### pre-commit

```yaml
repos:
  - repo: local
    hooks:
      - id: governance-check
        name: Governance Check
        entry: bash .ai-framework/quality-gates/scripts/check.sh
        language: system
```

---

## 自检

```bash
# 验证框架完整性
bash diagnose.sh
```

输出示例:
```
✅ PASS 14 项核心文件
✅ PASS 10 种语言配置
✅ PASS 7 种框架配置
✅ PASS 3 种钩子集成
✅ PASS 所有脚本可执行
✅ 所有检查通过 — 框架完整可用
```

---

## 模板系统

| 模板 | 用途 |
|------|------|
| agent-prompt.md | 创建新的 Agent 定义 |
| CONTEXT.md | 记录项目当前上下文 |
| ADR.md | 记录架构决策 |
| AGENTS.md | 索引所有 Agent |
| quality-report.md | 生成质量报告 |

---

## 添加新语言

```bash
1. 创建 languages/{language}/ 目录
2. 创建 rules.md — 语言规则
3. 创建 check.sh — 质量门禁脚本
4. 更新 README.md
5. 运行 bash diagnose.sh 验证
```

---

## 添加新框架

```bash
1. 创建 frameworks/{framework}/ 目录
2. 创建 rules.md — 框架特定规则
3. 更新 README.md
4. 运行 bash diagnose.sh 验证
```

---

## 贡献

欢迎贡献新语言、新框架、新工具集成。

详见 `CONTRIBUTING.md`。

---

*本框架适用于任何项目、任何编程语言。*
