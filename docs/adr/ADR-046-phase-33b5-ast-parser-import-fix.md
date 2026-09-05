# ADR-046: Phase 33b-5 ast_parser import 解析 bug 修复

## 状态
接受

## 日期
2026-09-05

## 背景

ADR-041/ADR-045 报告 ast_parser 的 import 解析存在两个 bug:
- `_parse_import_statement` 取 `node.children[0]` 当作 module —— 但 children[0]` 是 `'import'` 关键字, 不是模块名
- `_parse_import_from_statement` 在循环中持续覆盖 `module` 与 `names`, 仅保留最后一个 dotted_name 与 aliased_import

实测复现:
```python
>>> parse_file("from os import unused_path\n")
ImportInfo(module='List', names=[], is_from=False, level=0, line=1)
>>> parse_file("import os\n")
ImportInfo(module='import', names=['os'], is_from=False, level=0, line=1)
```

后果: `UnusedImportRule` 因 `imp.names=[]` 而从不触发 → ADR-045 已记录为已知限制.

## 决策

### 决策 1: 修复 tree-sitter 节点提取顺序

tree-sitter Python import 节点结构:
```
import_statement:
  - import (keyword)
  - dotted_name (X / X.Y)
  - aliased_import (X as Y) [可选]
  - dotted_name (Z) [可选, for `import X, Y`]

import_from_statement:
  - from (keyword)
  - relative_import (. / ..) [可选]
  - dotted_name (X / X.Y)
  - import (keyword)
  - dotted_name (Y) / aliased_import (Y as Z)
```

修正: 取**首个** dotted_name 作 module, 后续 dotted_name 与 aliased_import 作为 names.

### 决策 2: aliased_import 内部节点类型

`import a as b` 的 aliased_import children:
- `dotted_name 'a'` (不是 identifier)
- `as`
- `identifier 'b'`

`from X import a as b` 同上.

需识别 `identifier` 与 `dotted_name` 两种作为原始名.

### 决策 3: relative import 路径

`from . import x` 无 module dotted_name → `module=''`, `names=['x']`
`from ..pkg import y` relative_import 包含 `..pkg`, dotted_names=['y'] → `module=''`, `names=['y']`

简化策略: relative_seen 时所有 dotted_names 都视为 names, module 留空.

### 决策 4: 拆分 _parse_import_from_statement 为 helper

原实现函数体超 50 行触发 baseline 阈值. 拆为:
- `_extract_from_components(node)` → 返回 (level, dotted_names, names, relative_seen)
- `_assemble_from_import(...)` → 组装 ImportInfo
- `_parse_import_from_statement(node)` → 委托两个 helper

每个函数 ≤ 25 行, 复符合 baseline 0 Any/结构豁免.

## 后果

### 正面
- 修复 8 个 import 模式:
  - `import os` / `import sys, json` / `import a as b` / `import foo.bar`
  - `from typing import List` / `from typing import List, Optional`
  - `from foo.bar import baz` / `from collections import OrderedDict as OD`
  - `from . import x` / `from .. import x` / `from ..pkg import y`
- UnusedImportRule 现可正常触发 (ADR-041 限制解除)
- 函数拆解维持 baseline 0 增量

### 负面
- ADR-045 中记录的 `UnusedImportRule 未触发` 测试假设不再成立
  (`test_runs_semantic_checks_returns_list` 等仍通过, 因不强求 rule_ids)
- 真实集成测试 (Phase 33b-4) 需要重新验证 UnusedImportRule

## 验证

- 15/15 新增测试通过 (`test_ast_parser_import_fix.py`)
- 224/224 相关测试通过 (ast_parser/semantic_rules/semantic_checker)
- quality-gate: 192 passed, 0 failed
- baseline: 19 (12 文件) 一致
- typecheck: 192 source files 无问题
- lint: All checks passed

## 累计状态

- 46+1=47 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3911+15=3926 tests passed
- 87.72% 总覆盖率
- **ast_parser import 解析 bug 修复** ✅
- ADR-041 限制 (UnusedImportRule 未触发) 解除
- ADR-045 集成测试假设需要重新审视