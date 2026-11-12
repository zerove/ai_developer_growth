# ADR-050: Phase 33b-9 ast_parser monster.py 端到端契约验证

## 状态
接受

## 日期
2026-09-05

## 背景

按指令 "map every explicit requirement and changed public output to a concrete check" 探索 ast_parser 公共接口 + 集成边界的真实端到端契约。

ADR-048/049 修复了 9 个 walk/count 函数的 RecursionError, 但**未验证单一文件含多种压力源**时端到端契约仍成立。

## 决策

### 决策 1: 构造 monster.py 综合压力源

单一文件同时包含:
- 8 种 import 模式 (import X / import X, Y / from X import Y, Z / from X import Y as Z / from . / from .. / from ..pkg / import X as Y)
- 500 链 binary_expression (1+1+1+... * 500)
- 50 层嵌套 class_definition
- 50 层嵌套 function_definition

### 决策 2: 端到端契约断言

`SemanticChecker.analyze_directory(monster.py.parent)` 必须:
- files_analyzed == 1
- imports == 8 (所有 import 模式解析正确)
- classes == 1 (嵌套 class 算 1 个最外层, 因 _walk_classes 在外层 class_definition 处 return)
- functions == 1 (同上, 嵌套 function 算 1 个最外层)
- error_nodes == 0
- issues 是 list (不爆栈)

### 决策 3: 多语言 monster (JS/Rust/Go)

每个语言 500 链 binary_expression 端到端 parse_file, 验证不爆栈。

### 决策 4: 真实发现 — 嵌套 class 算 1 个

**真实行为**: 50 层嵌套 class (`class C0: class C1: class C2: ...`) 被识别为 1 个 `C0` (最外层)。这是 _walk_classes 的设计选择: 命中 `class_definition` 后 `return`, 不递归 children。

**Python 语义**: `class C0:` 的 body 内 `class C1:` 是嵌套类定义, 不是独立顶层类。从 _walk_classes 视角, C0 已经包含整个 body, 不应重复提取 C1-C49。

测试断言调整为 `len(classes) == 1`, 而非 `== 50`。

## 后果

### 正面
- **公共接口 + 集成边界** 端到端验证通过
- monster.py 测试是**回归检测**: 任何未来 walk/count 函数破坏递归安全将立即触发
- 多语言 (JS/Rust/Go) 端到端也验证迭代化
- 真实设计发现 (嵌套 class 算 1 个) 文档化

### 负面
- 测试代码量 86 行 (含大量 list comprehension 构造代码)
- 不验证多文件场景 (留待后续)

## 验证

- 2/2 `test_ast_parser_monster.py` 通过
- 0 个失败
- 全量门禁 (lint/typecheck/quality-gate/baseline) 全过
- 3934 个测试无回归

## 累计状态

- 50+1=51 ADR (含本 ADR)
- 11 降级规则 (baseline.json)
- 3934+2=3936 tests passed
- 88.16% 总覆盖率
- monster.py 端到端契约锁定: 任何破坏自动检测
