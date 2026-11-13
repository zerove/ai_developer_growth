# 规则贡献指南

欢迎为 ADG 贡献新语言的规则！

## 规则目录结构

```
~/.config/adg/rules/
├── languages/          # 语言专用规则
│   ├── python/
│   │   ├── rules.d/
│   │   │   └── anti_patterns.yml
│   │   ├── check.sh    # 可选：自定义检查脚本
│   │   └── rules.md    # 文档
│   ├── javascript/
│   └── ... (26 种语言)
└── common/             # 跨语言通用规则
    ├── security.yml
    └── universal.yml
```

## 添加新语言

### 1. 创建目录

```bash
mkdir -p ~/.config/adg/rules/languages/<lang>/rules.d/
```

### 2. 规则模板

```yaml
# languages/<lang>/rules.d/anti_patterns.yml
language: <lang>
version: '>=1.0'
config_version: '1.0'

anti_patterns:
- id: <lang>-<rule-id>         # 语言前缀 + 短横线命名
  name: <Rule display name>    # 人类可读的名称
  severity: error|warning|info # 错误/警告/信息
  category: <category>         # 分类: security, error_handling, type_safety, code_quality, performance, logging, testing, concurrency, resource_management, ci_cd, config
  pattern: '<regex>'           # 检测正则（Python re 语法）
  exclude_files:               # 可选：排除特定文件
  - fix_heuristics.py
  exclude_patterns:            # 可选：基于内容排除
  - TYPE_CHECKING
  message: '<human message>'   # 问题的描述
  fix_hint: '<fix suggestion>' # 修复建议

naming:
  file:
    pattern: '^[a-z]...$'      # 文件名正则
    message: '...'
  function:
    pattern: '^[a-z]...$'
    message: '...'
  class:
    pattern: '^[A-Z]...$'
    message: '...'

thresholds:
  max_function_length: 50
  max_file_length: 500
  max_line_length: 120

tooling:
  linter: <name>
  formatter: <name>
  type_checker: <name>
  test_runner: <name>
```

### 3. 编写规则文档

```markdown
# <语言> 规则

## 代码风格
...

## 反模式
...

## 工具配置
...
```

### 4. 验证

```bash
# 找一个该语言的源文件测试
adg scan path/to/test/file.<ext>
```

## 规则编写最佳实践

### DO
- 使用明确的规则 ID，带语言前缀（`py-bare-except`）
- 编写 `test_cases` 验证匹配/不匹配
- `severity` 合理分级：
  - `error` = 可能导致运行时错误的（SQL注入、裸 except）
  - `warning` = 应修复但非阻塞的（Any 类型、缺少类型提示）
  - `info` = 风格建议（TODO 注释、缺少 `__all__`）
- 对可能匹配注释/字符串的模式添加 `exclude_patterns`
- 对内部工具代码使用 `exclude_files`

### DON'T
- 不要在规则中硬编码文件路径
- 不要使用过于宽泛的 pattern（导致大量误报）
- 不要包含供应商/第三方代码的排除规则
- 不要将规则 severity 全部设为 error

## 分类标准

| 分类 | 说明 | 示例 |
|------|------|------|
| security | 安全漏洞 | SQL注入、硬编码密钥 |
| error_handling | 错误处理 | 裸 except、空 catch |
| type_safety | 类型安全 | Any 类型、缺少类型注解 |
| code_quality | 代码质量 | 通配符导入、可变默认参数 |
| performance | 性能 | N+1 查询、循环中分配 |
| logging | 日志 | print 替代 logging |
| testing | 测试 | sleep 在测试中 |
| concurrency | 并发 | 缺少 await、共享可变状态 |
| resource_management | 资源管理 | 未关闭文件/连接 |
| ci_cd | CI/CD | 禁用检查、latest 标签 |
| config | 配置 | 硬编码 hosts/origins |

## 通用规则集

`common/security.yml` 和 `common/universal.yml` 自动应用于所有语言。
如果你的语言规则需要覆盖通用规则，使用 `severity` 更低的 ID 或在规则中通过 `exclude_files` 排除。

## CI 验证

提交 PR 时，运行以下验证：

```bash
# 验证 YAML 格式
python -c "import yaml; yaml.safe_load(open('path/to/anti_patterns.yml'))"

# 验证规则可加载
adg scan path/to/test/file.<ext>

# 验证文档格式（如果适用）
python -m tools.scripts.validate_language_rules
```

---

*贡献即表示你同意将规则以 MIT 许可证发布。*
