# generate-rules Skill

为 ADG 规则引擎生成新语言的代码质量规则。
**Jcode agent 本身就是 LLM**——不需要外部 API，基于对语言的知识生成规则。

## Usage

```
/generate-rules <language>                          # 为语言生成规则（交互式）
/generate-rules <language> --file sample.ext        # 基于示例文件生成
/generate-rules <language> --force                  # 覆盖已有规则
/generate-rules --list                              # 列出已生成规则的语言
/generate-rules --status [language]                 # 查看生成规则状态
```

## Examples

```bash
# 为 Mojo 生成规则（交互式，agent 基于知识生成）
/generate-rules mojo

# 为 Solidity 生成规则，基于示例文件分析
/generate-rules solidity --file contracts/Token.sol

# 查看已生成的规则
/generate-rules --status
/generate-rules --status mojo

# 列出所有支持的语言
/generate-rules --list
```

## Implementation

### 生成规则
调用 `tools/scripts/rules_engine/rule_generator.py` 保存 agent 生成的规则：

```python
from tools.scripts.rules_engine.rule_generator import (
    save_rules,
    format_rules,
    KNOWN_LANGUAGES,
    load_generated_rules,
    discover_generated_rules,
    list_generated_languages,
    detect_language_from_extension,
    validate_rules_yaml,
)
```

工作流:
1. agent 分析语言特征（内置知识 + 可选样本文件）
2. 构建规则列表（id/name/severity/category/pattern/message）
3. 调用 `save_rules(language, rules)` 保存
4. `rule_loader.py` 自动发现新规则
5. 下次 `adg-dev scan` 自动加载

### 查看状态
```bash
python -m tools.scripts.rules_engine.rule_generator [language]
```

### 语言支持
agent 可以为任意编程语言生成规则，包括：
- 主流程语言 (Python/JS/TS/Rust/Go/Java 等 26+ 种)
- 新兴语言 (Mojo/Zig/Solidity)
- 领域特定语言 (GraphQL/YAML/TOML)
- 自定义 DSL

## Rule Format

每条规则是一个 dict:

```python
{
    "id": "mojo-unsafe-cast",  # 唯一 ID: {lang}-{short-name}
    "name": "Unsafe pointer cast",
    "severity": "error",  # error / warning / info
    "category": "security",  # 分类
    "pattern": r"unsafe\s*\{",  # 正则表达式
    "message": "Unsafe blocks should be minimized",
    "fix_hint": "Use safe abstractions",  # 可选
    "exclude_files": ["test_*.mojo"],  # 可选
}
```
