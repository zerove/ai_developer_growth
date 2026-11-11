# ADR-081: 自动修复必须只改上报的那一处命中

## 状态

接受

## 日期

2026-11-12

## 影响组件

- `tools/scripts/auto_fix.py`（`RegexFixProvider.generate_fixes`、`_resolve_pattern`、
  `_resolve_match`、`_select_match`、`_build_action`）
- `tests/test_auto_fix_regex_contract.py`
- `tests/test_auto_fix_orchestrator.py`（历史行为回归）
- `tests/test_redos_guard_autofix.py`（ReDoS 守卫回归）

## 背景

`RegexFixProvider.generate_fixes` 是"按 Issue 生成修复动作"的入口，
`AutoFixOrchestrator.create_plan` 会对每个 Issue 调用它，产出的 `FixAction`
最终被写回源文件。

旧实现有三处结构性缺陷：

### 缺陷 1：把 `rule_id` 当正则用

```python
pattern = issue.rule_id.replace(":", r"\:")
fixed_line = re.sub(pattern, issue.fix_replacement, original_line)
```

`rule_id` 是**标识符**（`py-eval`、`sec-001`），不是 pattern。于是：

- "检测用的正则"（规则定义里的 `pattern`）与"修复用的正则"（`rule_id`）根本不是
  一回事 —— 修复可能落到行内与问题无关的位置；
- 与文件级路径 `apply_rules`（用规则自带的 `pattern`）语义分叉：同一条规则在
  两条路径上"匹配什么"不一致。

### 缺陷 2：`re.sub` 改写整行所有匹配

`re.sub` 会替换行内**全部**非重叠匹配。一行里出现三处同样写法时，一次修复会
把三处一起改掉，其中两处并未被上报 —— 修复范围超出问题范围。

### 缺陷 3：零长匹配会在行首凭空插入

pattern 形如 `x*` 时可零长匹配。`re.sub` 对零长匹配会在每个位置插入替换文本，
于是"修复"变成在行首插入垃圾内容（`fix_applier._apply_literal_replacement`
此前已经因为同类问题做过防护，见其注释里记录的"行首插入 `DONEx = ...`"实测）。

三方输入（pattern / replacement / 被改的源码行）都不可信：前两者来自规则配置
（PR 场景由外部贡献者控制），第三者是待改源码，且结果**写回文件**。

## 决策

收敛 `generate_fixes` 的契约为"**只改上报的那一处命中**"：

1. **pattern 以注册规则为准**：`self.rules[rule_id]["pattern"]` 存在时用它，
   与文件级 `apply_rules` 同源；未注册该 `rule_id` 时回退到历史行为
   （`rule_id` 当 pattern），保持向后兼容。
2. **按列锚定**：规则 pattern 参与匹配时，只接受**恰好命中 `issue.column`**
   （1-based，与 `anti_pattern_checker` 上报列同源）的那个匹配；找不到即放弃
   修复，不做"就近替换"。回退路径没有可验证的列对应关系，取首个匹配。
3. **只替换这一处**：用匹配区间切片拼接替换结果，不再整行全替换。替换模板经
   `Match.expand` 展开，保留 `\1` 等反向引用语义。
4. **零长匹配不替换**：空区间的替换等于凭空插入内容，一律放弃。
5. **既有防护保留**：pattern 仍先过 `guard_pattern`（ReDoS）与 `re.compile`
   合法性检查，失败即放弃并告警。

失败一律"放弃这一条修复"（返回空 `FixAction` 列表），不改文件、不抛异常 ——
与 ADR-078 的"检查失败必须可见"同族：**宁可不修，不可改错**。

## 后果

### 正面

- 修复范围与上报范围一致，不再波及同行的其它命中。
- 行级修复与文件级 `apply_rules` 使用同一个 pattern 源，语义不再分叉。
- 零长匹配、非法正则、非法替换模板都被安全拒绝，不会写坏文件。

### 负面 / 代价

- 当 `issue.column` 与规则 pattern 的命中位置不一致时（文件在上报后被改动、
  或问题由其它检查器产出），该条修复会被放弃 —— 宁可漏修，不可改错。
- 未注册规则的调用方仍走"rule_id 当 pattern"的历史路径，该路径无法按列锚定，
  只能取首个匹配。

## 修订记录

- 2026-11-12: 首次落地。`generate_fixes` 改为"规则 pattern 优先 + 按列锚定 +
  只替换这一处 + 零长不替换"，新增 `tests/test_auto_fix_regex_contract.py`
  锁定契约；历史行为（rule_id 当 pattern）保留为兼容回退路径。
