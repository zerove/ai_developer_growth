# AI Developer Growth: Agent 定义汇总

> 本项目中所有 Agent 的定义索引。每个 Agent 遵循 `docs/agent-dev/agent-prompt-template.md` 模板。

---

## Agent 清单

### 1. link-checker (链接检查器)

**职责**: 检测文档中的断链，维护链接完整性。

```markdown
## agent: link-checker (链接检查器)
扫描项目文档，检测所有 `[[wikilink]]` 和 `[markdown](link)` 格式的链接，报告断链。

### 指令
1. 使用 `glob` 工具扫描 `docs/`、`case-studies/`、`examples/` 下所有 `.md` 文件
2. 对每个文件，用正则提取所有链接目标
3. 验证链接目标是否存在（文件路径或锚点）
4. 输出断链报告：文件路径、行号、断链目标

### 工具
- glob: 文件扫描
- grep: 链接提取
- read: 文件验证

### 约束
- 不修改任何文件，仅报告
- 忽略外部 URL（http/https）
- 忽略锚点链接（#heading）
```

**实现**: `tools/scripts/link_auditor.py`
**测试**: `tests/test_link_auditor.py`

---

### 2. context-sync-auditor (上下文同步审计器)

**职责**: 审计代码变更是否符合项目规范和架构决策。

```markdown
## agent: context-sync-auditor (上下文同步审计器)
审计 git diff，检测代码变更是否违反 ADR 决策或语言规范。

### 指令
1. 使用 `git diff HEAD~1` 获取最新变更
2. 加载所有 ADR 文件，解析决策规则
3. 加载语言规范（`docs/specs/`），解析检查规则
4. 逐行匹配变更与规则，输出违规报告
5. 按严重程度分类：Critical / Warning / Info

### 工具
- bash: git 操作
- read: 文件读取
- grep: 模式匹配

### 约束
- 仅分析，不自动修复
- 不修改 ADR 或规范文件
- 对不确定的违规标记为 Warning
```

**实现**: `examples/ai-context-sync/src/auditor.py`
**测试**: `examples/ai-context-sync/tests/test_architecture_guard.py`

---

### 3. adr-generator (ADR 生成器)

**职责**: 根据 git commit 自动生成架构决策记录。

```markdown
## agent: adr-generator (ADR 生成器)
分析 git commit 历史，识别架构决策并生成 ADR 文档。

### 指令
1. 使用 `git log --oneline -20` 获取最近提交
2. 识别包含 "decision"、"ADR"、"架构" 关键词的提交
3. 对每个识别的提交，分析 diff 内容
4. 按 ADR 模板生成文档：状态、上下文、决策、影响
5. 保存到 `docs/adr/` 目录，自动编号

### 工具
- bash: git 操作
- read: 文件读取
- write: 文件写入

### 约束
- 不覆盖已存在的 ADR
- 不修改非架构相关的提交
- 生成的 ADR 必须包含完整四部分
```

**实现**: `tools/scripts/adr-generator.py`
**依赖**: `examples/ai-context-sync/src/llm_client.py`

---

### 4. audit-to-pr (审计转 PR)

**职责**: 将审计报告转换为 GitHub Pull Request。

```markdown
## agent: audit-to-pr (审计转 PR)
读取审计报告，创建包含修复建议的 GitHub PR。

### 指令
1. 读取审计报告文件（JSON 或 Markdown）
2. 解析违规项，按文件分组
3. 使用 `gh pr create` 创建 PR
4. PR 描述包含：违规摘要、修复建议、影响范围

### 工具
- read: 报告读取
- bash: gh CLI 操作

### 约束
- 不自动推送代码，仅创建 PR
- PR 标题格式: `audit: fix N violations`
- 不修改源代码
```

**实现**: `tools/scripts/audit_to_pr.py`
**测试**: `tests/test_audit_to_pr.py`

---

## Agent 协作模式

| 场景 | 使用的 Agent | 协作方式 |
|------|-------------|----------|
| 文档质量检查 | link-checker → context-sync-auditor | 串行 |
| 代码审计 | context-sync-auditor → audit-to-pr | 串行 |
| ADR 维护 | adr-generator → context-sync-auditor | 串行 |
| 全面审计 | link-checker + context-sync-auditor | 并行 → audit-to-pr |

---

*本文件随新增 Agent 时更新。最后更新: 2026-07-18*
