# ADR-059: 安全模式两套实现并存是刻意设计，不做合并

## 状态
接受

## 日期
2026-10-01

## 背景

治理资产审计报告"4 份安全模式实现"，建议收敛为单一来源：

| # | 位置 | 形式 | 规模 | 是否在门禁路径上 |
|---|------|------|------|------------------|
| 1 | `ai-dev-framework/common/security.yml` | YAML，18 条 `common-*` 规则 | 权威源 | ✅ 规则引擎加载 |
| 2 | `tools/scripts/rules_engine/security_patterns.py` | Python dict | 已删除（见下） | ❌ 生产零引用 |
| 3 | `tools/scripts/ai_quality_gate.py` | 10 条手写正则 | — | ✅ `on_commit`/`scheduled` 两处 hook |
| 4 | `.jcode/scripts/governance-auditor.py` | `UNSAFE_PATTERNS` | — | ✅ `full` 审计 |

### 已完成的部分

第 2 份（`security_patterns.py`，154 行 / 3 个 pattern 集）**已删除**。它同时使用
`security-eval-exec` 与权威源的 `common-eval-exec` 两套 ID 命名，生产代码零引用，
唯一消费者是它自己的测试——属于会误导后续维护（改错文件）的陷阱。

第 4 份（`governance-auditor.UNSAFE_PATTERNS`）经核查是**面向规则定义文件本身**的
审计（"这些反模式定义里有没有不安全的写法"），与前 3 份的"扫描用户代码"关注点不同，
不是重复。

## 决策

**第 1 份与第 3 份并存，不合并。** 二者是不同检测机制下的两层防线。

### 理由

1. **引擎不同，检出能力不可直接等价**
   - 第 1 份走规则引擎：AST 解析、作用域感知、按语言分发、支持 `severity` 与 `exclude_files`
   - 第 3 份走行级正则 + `_is_in_string()` 字面量排除，专治"正则扫全文"的一类误报
   把 3 换成 1 会**改变检出结果**（可能增也可能减），属于行为变更而非重构

2. **测试与实现的消息文本强耦合**
   `tests/test_enforcement_supplement.py` 有 17 处断言直接匹配中文消息，例如
   `assert "硬编码密钥" in issues[0]["message"]`、`assert "eval()" in issues[0]["message"]`。
   YAML 权威源的 `message` 字段措辞不同，合并必然先改测试——而"改测试适配新实现"
   正是掩盖行为变更的标准路径。合并必须先证明等价，再改断言，顺序不能反。

3. **第 3 份的误报抑制能力未被 YAML 侧覆盖**
   `test_eval_in_string_no_issue` 断言 `PATTERN = r"eval\s*\("` 这类字符串字面量
   不触发告警。AST 引擎理论上也不会告警（它是 Str 常量不是 Call 节点），
   但这是**需要逐条验证的等价性假设**，不是可以直接假定的结论。

## 后果

- 审计规则更新：判断"重复"必须先确认**引擎层是否等价**。同名的两份实现在不同
  抽象层（数据/规则 vs 扫描实现）不构成重复。
- 若后续要合并，前置条件是：
  1. 为第 3 份的 10 条模式各写一组"等价性用例"，同时喂给两套实现，断言检出集合一致
  2. 等价性成立后再改消息文本断言
  3. 保留 `_is_in_string` 等误报抑制能力，或确认 AST 侧已覆盖

## 关联

- 同期删除：`tools/scripts/rules_engine/security_patterns.py`（死代码，含冲突 ID 命名）
- 同类决策：[[docs/adr/ADR-058-context-sync-dual-implementation|ADR-058]]（context-sync 双实现）
