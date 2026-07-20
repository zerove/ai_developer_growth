# Universal Agent Development Governance

> 通用的 AI Agent 开发治理标准，适用于任何项目、任何编程语言。

---

## 1. Agent 定义格式

所有 agent 定义必须包含以下字段：

```yaml
agent-name: kebab-case 命名 (如: code-reviewer)
描述: 一句话核心职责
工具: 最小权限列表
约束: 明确的禁止行为
指令: 具体、可验证的操作步骤
```

### 命名规范

- 使用 kebab-case: `code-reviewer`, `test-runner`
- 名词+动词或动词+名词: `bug-fixer`, `deploy-helper`
- 避免缩写: 用 `helper` 不用 `hlp`

### 指令编写原则

1. **具体性**: 每条指令必须包含具体的工具名、文件路径、函数名
2. **可验证性**: 指令执行后必须有明确的成功/失败判定
3. **原子性**: 一条指令只做一件事
4. **顺序性**: 指令必须按逻辑顺序排列

---

## 2. 开发流程 (5 步闭环)

```
需求分析 → Prompt 设计 → 实现编码 → 自动化审计 → 资产更新
   ①          ②          ③          ④           ⑤
```

### 阶段详情

| 阶段 | 输入 | 输出 | 负责人 |
|------|------|------|--------|
| ① 需求分析 | 用户需求 | 需求文档 | PM/TL |
| ② Prompt 设计 | 需求文档 | Agent 定义 | Agent Dev |
| ③ 实现编码 | Agent 定义 | 可执行代码 | Agent Dev |
| ④ 自动化审计 | 可执行代码 | 审计报告 | CI/CD |
| ⑤ 资产更新 | 审计报告 | 更新文档 | Agent Dev |

---

## 3. 质量门禁 (4 道)

```
Gate 1: Prompt 设计 → Gate 2: 实现编码 → Gate 3: 自动化审计 → Gate 4: 资产更新
```

### Gate 1: Prompt 设计审查

- [ ] 名称格式正确 (kebab-case)
- [ ] 描述完整 (一句话核心职责)
- [ ] 指令具体、可验证
- [ ] 工具最小化
- [ ] 职责唯一性 (无重叠)

### Gate 2: 实现编码审查

- [ ] 代码通过 linter 检查
- [ ] 无类型错误 (如适用)
- [ ] 无安全漏洞
- [ ] 测试覆盖率 ≥ 70%

### Gate 3: 自动化审计

- [ ] Linter 检查通过
- [ ] 测试全部通过
- [ ] 安全扫描通过
- [ ] 性能基准达标 (如适用)

### Gate 4: 资产更新

- [ ] CONTEXT.md 已更新
- [ ] ADR.md 已记录关键决策
- [ ] AGENTS.md 已更新 (如新增 agent)
- [ ] 文档与代码一致

---

## 4. 上下文管理

### 必需文件

| 文件 | 用途 | 更新频率 |
|------|------|----------|
| `CONTEXT.md` | 项目状态 | 每次重大迭代 |
| `ADR.md` | 架构决策 | 关键决策时 |
| `AGENTS.md` | Agent 定义 | 新增/修改 agent |
| `UBIQUITOUS_LANGUAGE.md` | 领域术语 | 新增术语时 |

### 更新规则

1. **CONTEXT.md**: 包含项目目标、当前状态、下一步计划
2. **ADR.md**: 记录架构决策的上下文、决策、影响
3. **AGENTS.md**: 索引所有 agent 定义
4. **UBIQUITOUS_LANGUAGE.md**: 定义领域术语

---

## 5. 语言特定规则

每种语言有特定的规则和工具配置，见 `languages/` 目录。

### 通用原则

1. **代码风格**: 遵循语言社区标准
2. **错误处理**: 使用语言惯用模式
3. **测试**: 遵循语言测试框架
4. **文档**: 遵循语言文档标准

---

## 6. 工具集成

### opencode 集成

```json
// .opencode/hooks.json
{
  "pre_prompt": [
    {
      "name": "check-governance",
      "command": "bash .ai-framework/quality-gates/scripts/check.sh",
      "description": "检查代码质量"
    }
  ]
}
```

### jcode 集成

```yaml
# .jcode/config.yml
governance:
  enabled: true
  hooks:
    pre_commit:
      - command: "bash .ai-framework/quality-gates/scripts/check.sh"
        description: "检查代码质量"
```

### pre-commit 集成

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: governance-check
        name: Governance Check
        entry: bash .ai-framework/quality-gates/scripts/check.sh
        language: system
```

---

## 快速开始

### 安装

```bash
# 克隆框架
git clone https://github.com/your-org/ai-dev-framework.git
cd ai-dev-framework

# 安装到你的项目
./install.sh /path/to/your/project python
```

### 使用

1. 阅读 `GOVERNANCE.md`
2. 使用 `templates/agent-prompt.md` 创建 agent
3. 通过 4 道质量门禁
4. 定期更新上下文文件

---

*本框架适用于任何项目、任何编程语言。*
