# ADG Learn生成

> 分析代码库并自动生成自定义治理规则。

## 使用

```bash
# 分析当前项目
adg learn

# 分析指定项目并输出到文件
adg learn ./my-project -o .adg/rules.yml

# JSON 格式输出
adg learn ./my-project --format json
```

## 工作原理

1. **语言检测**: 通过文件扩展名识别主要编程语言
2. **模式扫描**: 使用 10+ 个检测器扫描代码中的反模式
3. **规则生成**: 根据检测到的模式生成 YAML 配置
4. **输出**: 可直接使用的 `.adg/rules.yml` 文件

## 支持的检测器

| 检测器 | 类别 | 严重度 |
|--------|------|--------|
| eval/exec 使用 | security | error |
| print 语句 | code_quality | warning |
| TODO/FIXME | code_quality | info |
| 硬编码 URL | config | warning |
| 空 catch 块 | error_handling | error |
| 裸 except | error_handling | error |
| 魔法数字 | code_quality | info |
| 深层嵌套 | code_quality | warning |
| console.log | code_quality | info |
| SQL 字符串拼接 | security | error |

## 输出示例

```yaml
language: python
config_version: '1.0'
source: auto-generated
anti_patterns:
  - id: detected-eval-usage
    name: Dynamic code execution
    severity: error
    category: security
    pattern: '\beval\s*\(|\bexec\s*\('
    message: 'eval/exec detected in codebase (found 3 occurrences)'
    fix_hint: Replace with safer alternatives
```

## 与自定义规则集成

生成的规则文件可以直接放在 `.adg/rules.yml` 中：

```bash
adg learn -o .adg/rules.yml
# 规则将自动被 adg check 加载
```
