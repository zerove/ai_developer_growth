# Agent 定义索引

> {{PROJECT_NAME}} 项目中所有 AI agent 的定义索引

---

## Agent 列表

| Agent | 职责 | 语言 | 文件 |
|-------|------|------|------|
| {{AGENT_NAME}} | {{DESCRIPTION}} | {{LANGUAGE}} | {{PATH}} |

---

## 添加新 Agent

```markdown
## {{AGENT_NAME}}

**职责**: {{DESCRIPTION}}
**语言**: {{LANGUAGE}}
**触发词**: {{TRIGGERS}}

### 规则
- {{RULE_1}}
- {{RULE_2}}

### 文件
{{PATH}}
```

---

## 维护规则

1. **索引唯一性**: 每个 agent 只出现一次在索引表中
2. **触发词**: 列出所有能触发该 agent 的关键词
3. **职责清晰**: 职责描述不超过两句
4. **同步更新**: 修改 agent 定义后立即更新索引
