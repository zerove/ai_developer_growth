# JCode 多语言适配指南

> **版本**: 1.0 | **适用**: JCode 1.0+ | **更新**: 2026-08-22

---

## 概述

JCode 框架通过 **语言工具链注册表** (`tools/scripts/language_registry.py`) 实现跨语言、跨项目的通用化。核心思想：**配置驱动，语言无关**。

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    JCode 核心技能层                           │
├─────────────────────────────────────────────────────────────┤
│  hooks_runner.py  │  governance-auditor.py  │  context_sync │
│  self_correction  │  multi_agent_orch       │  ...          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              语言工具链注册表 (LanguageRegistry)              │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┐        │
│  │ Python  │TypeScript│  Rust   │   Go    │  Java   │ ...    │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              项目配置 (.jcode/project.yaml)                  │
│  language.primary + language.secondary + tools + thresholds  │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 1. 初始化新项目

```bash
# 交互式
jcode init

# 指定语言
jcode init --lang python
jcode init --lang typescript
jcode init --lang rust
jcode init --lang go

# 使用模板
jcode init --template api      # Go + Python API 服务
jcode init --template web      # TypeScript + Python 全栈
jcode init --template cli      # Rust CLI 工具
jcode init --template library  # 多语言库开发
jcode init --template data     # Python 数据科学
```

### 2. 生成的配置文件

生成 `.jcode/project.yaml`，包含：

```yaml
project:
  name: "my-project"
  version: "0.1.0"
language:
  primary: "python"      # 主语言
  secondary: []          # 次要语言
  version: ">=3.11"
  runtime: "cpython"
paths:
  src: "src"
  tests: "tests"
tools:
  format:
    command: "ruff"
    args: ["format"]
    check_args: ["format", "--check"]
  lint:
    command: "ruff"
    args: ["check"]
    fix_args: ["check", "--fix"]
  typecheck:
    command: "mypy"
    args: ["--config-file", "pyproject.toml", "src"]
  test:
    command: "pytest"
    args: ["-v", "--tb=short"]
  security:
    command: "bandit"
    args: ["-r", "src", "-f", "json", "-o", "bandit-report.json"]
thresholds:
  coverage:
    overall: 60
    per_file: 50
  complexity:
    cyclomatic: 10
  naming:
    style: "snake_case"
hooks:
  on_commit: [...]
  on_pr: [...]
  on_merge: [...]
  scheduled: [...]
```

---

## 支持的语言

| 语言 | 代码 | 版本要求 | 运行时 | 包管理器 | 主要工具链 |
|------|------|----------|--------|----------|------------|
| Python | `python` | >=3.11 | cpython | pip/poetry | ruff, mypy, pytest, bandit |
| TypeScript | `typescript` | >=5.0 | node | npm/yarn/pnpm | prettier, eslint, tsc, vitest |
| JavaScript | `javascript` | >=18.0 | node | npm | prettier, eslint, vitest |
| Rust | `rust` | >=1.70 | rustc | cargo | rustfmt, clippy, cargo test |
| Go | `go` | >=1.21 | go | go mod | gofmt, golangci-lint, go test |
| Java | `java` | >=17 | jvm | maven/gradle | google-java-format, spotbugs |
| C++ | `cpp` | >=17 | native | conan/vcpkg | clang-format, clang-tidy |
| C# | `csharp` | >=8.0 | clr | nuget | dotnet format, dotnet test |
| Ruby | `ruby` | >=3.0 | ruby | bundler | rubocop, rspec |
| PHP | `php` | >=8.1 | php | composer | php-cs-fixer, phpstan, phpunit |

> 完整列表见 `tools/scripts/language_registry.py` 中的 `Language` 枚举

---

## 多语言项目配置

### 主语言 + 次要语言

```yaml
language:
  primary: "typescript"     # 前端主语言
  secondary: ["python"]     # 后端/脚本语言
  version: ">=5.0"
```

### 运行检查

```bash
# 只检查主语言
hooks_runner.py lint
hooks_runner.py format
hooks_runner.py typecheck
hooks_runner.py test
hooks_runner.py security

# 检查指定语言
hooks_runner.py lint --lang python,typescript
hooks_runner.py format --lang rust
hooks_runner.py test --lang go

# 全量检查（自动检测所有语言）
hooks_runner.py full
hooks_runner.py full --lang python,typescript,go
```

### governance-auditor 多语言

```bash
# 指定语言
.jcode/scripts/governance-auditor.py lint --lang python
.jcode/scripts/governance-auditor.py typecheck --lang typescript
.jcode/scripts/governance-auditor.py test --lang rust,go

# 全量审计
.jcode/scripts/governance-auditor.py full
.jcode/scripts/governance-auditor.py full --lang python,typescript
```

---

## 自定义工具链

### 方式 1: 通过 project.yaml 覆盖

```yaml
tools:
  format:
    command: "custom-formatter"
    args: ["--style=google"]
    check_args: ["--check"]
  lint:
    command: "custom-linter"
    args: ["--strict"]
    fix_args: ["--fix"]
```

### 方式 2: 代码中注册自定义工具链

```python
from tools.scripts.language_registry import Language, LanguageToolchain, ToolConfig, ToolCategory, registry

# 定义自定义语言工具链
custom_ts = LanguageToolchain(
    language=Language.TYPESCRIPT,
    version=">=5.0",
    runtime="node",
    format=ToolConfig(
        command="prettier",
        args=["--write", "--plugin=prettier-plugin-organize-imports"],
        check_args=["--check", "--plugin=prettier-plugin-organize-imports"],
    ),
    lint=ToolConfig(
        command="eslint",
        args=[".", "--ext", ".ts,.tsx"],
        fix_args=[".", "--fix", "--ext", ".ts,.tsx"],
    ),
    # ... 其他工具
)

# 注册到注册表
registry.register(custom_ts)
```

### 方式 3: 扩展语言

```python
from tools.scripts.language_registry import Language, LanguageToolchain, ToolConfig

# 添加新语言（如 Dart）
DART_TOOLCHAIN = LanguageToolchain(
    language=Language.DART,
    version=">=3.0",
    runtime="dart",
    extensions=[".dart"],
    package_manager="pub",
    lock_file="pubspec.lock",
    format=ToolConfig(command="dart", args=["format"]),
    lint=ToolConfig(command="dart", args=["analyze"]),
    test=ToolConfig(command="dart", args=["test"]),
)

registry.register(DART_TOOLCHAIN)
```

---

## 阈值配置

每个语言有默认阈值，可在 `project.yaml` 中覆盖：

```yaml
thresholds:
  coverage:
    overall: 80           # 整体覆盖率
    per_file: 70          # 单文件最低
    critical_paths: 90    # 关键路径
  
  complexity:
    cyclomatic: 10        # 圈复杂度
    cognitive: 15         # 认知复杂度
    nesting: 4            # 最大嵌套
    function_length: 50   # 函数最大行数
  
  naming:
    style: "camelCase"    # snake_case | camelCase | PascalCase
    max_length: 64
  
  documentation:
    public_api: 80
    internal: 40
  
  security:
    max_high: 0
    max_medium: 5
    max_low: 20
  
  performance:
    max_build_time: 300
    max_test_time: 180
```

---

## Hooks 配置

在 `project.yaml` 中自定义 Git Hooks：

```yaml
hooks:
  on_commit:
    - name: "format-check"
      skill: "format"
      action: "check"
      enabled: true
    - name: "lint-check"
      skill: "lint"
      action: "check"
      enabled: true
      condition: "files_contain('src/')"  # 条件表达式
  
  on_pr:
    - name: "full-test"
      skill: "test"
      action: "run"
      enabled: true
    - name: "quality-gate"
      skill: "governance"
      action: "gate"
      enabled: true
  
  scheduled:
    - name: "weekly-audit"
      skill: "governance"
      action: "full"
      schedule: "0 9 * * 1"  # Cron 表达式
      enabled: true
```

---

## CI/CD 集成

### GitHub Actions 示例

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      
      - name: Install JCode
        run: pip install -e .
      
      - name: Run hooks
        run: |
          python -m tools.scripts.hooks_runner full
      
      - name: Governance audit
        run: |
          python .jcode/scripts/governance-auditor.py full
```

### 矩阵构建

```yaml
ci:
  matrix:
    python: ["3.11", "3.12", "3.13"]
    node: ["18", "20", "22"]
    rust: ["stable", "beta"]
    go: ["1.21", "1.22"]
```

---

## 迁移指南

### 从单语言项目迁移

1. **备份原配置**
   ```bash
   cp pyproject.toml pyproject.toml.bak
   ```

2. **初始化 JCode 配置**
   ```bash
   jcode init --lang python
   ```

3. **同步工具配置**
   - 将 `pyproject.toml` 中的 `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest]` 等保留
   - JCode 会自动读取这些配置

4. **验证**
   ```bash
   hooks_runner.py full
   ```

### 从其他工具迁移

| 原工具 | JCode 对应 |
|--------|------------|
| pre-commit | `hooks.on_commit` |
| GitHub Actions | `ci` + `hooks.on_pr` |
| Dependabot | `hooks.scheduled` + `deps` |
| CodeQL | `security` skill |
| SonarQube | `quality-gate` + `thresholds` |

---

## 常见问题

### Q: 某语言工具未安装怎么办？

```bash
# 查看安装提示
python -c "
from tools.scripts.language_registry import get_tool, Language, ToolCategory
tool = get_tool(Language.TYPESCRIPT, ToolCategory.LINT)
print(f'命令: {tool.command}')
print(f'安装: {tool.install_hint}')
"
```

### Q: 如何跳过某个检查？

```yaml
hooks:
  on_commit:
    - name: "security-scan"
      skill: "security"
      action: "scan"
      enabled: false  # 禁用
```

### Q: 如何针对特定目录运行？

```bash
hooks_runner.py lint --path src/
hooks_runner.py test --path tests/
```

### Q: 多语言项目如何指定不同路径？

```yaml
paths:
  # Python 后端
  src: "backend/src"
  tests: "backend/tests"
  
  # TypeScript 前端 (通过 secondary 语言单独配置)
language:
  primary: "python"
  secondary: ["typescript"]
```

> 注: 目前 `paths` 为全局配置，多语言目录建议使用 monorepo 结构或单独配置文件。

---

## 扩展开发

### 添加新 Skill

1. 创建技能文件 `.jcode/skills/my-skill.py`
2. 在 `project.yaml` 中启用：
   ```yaml
   agents:
     enabled: [..., "my-skill"]
   ```
3. 在 hooks 中引用：
   ```yaml
   hooks:
     on_pr:
       - name: "my-check"
         skill: "my-skill"
         action: "run"
   ```

### 添加新规则包

```yaml
extensions:
  rule_packs:
    - "https://github.com/myorg/jcode-rules-python"
    - "https://github.com/myorg/jcode-rules-security"
```

---

## 最佳实践

1. **统一使用 project.yaml** - 避免分散配置
2. **语言版本显式声明** - 避免环境差异
3. **阈值逐步收紧** - 从宽松开始，迭代提高
4. **Hooks 分层** - commit 快速检查，PR 全量，定时深度
5. **CI 矩阵覆盖** - 多版本、多平台验证
6. **通知分级** - 失败即时通知，成功定期汇总

---

## 相关文档

- [GOVERNANCE.md](GOVERNANCE.md) - 治理标准
- [AGENTS.md](AGENTS.md) - Agent 定义索引
- [CONTRIBUTING.md](CONTRIBUTING.md) - 贡献指南
- [tools/scripts/language_registry.py](tools/scripts/language_registry.py) - 注册表源码
- [.jcode/project.yaml](.jcode/project.yaml) - 配置示例