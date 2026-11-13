---
name: case-study-review
about: 案例研究 PR 审查清单
title: "[Case Study] Review: <案例标题>"
labels: ["case-study", "review"]
assignees: ""
---

## 📋 案例研究 PR 审查清单

**关联 Issue**: #<issue_number>

---

### 📝 内容完整性

- [ ] **标题格式**: `[Case Study] <简短标题>` (文件名)
- [ ] **基本信息表**: 项目类型、规模、耗时、AI 工具栈、效率提升
- [ ] **背景与挑战**: 目标清晰、挑战具体、约束明确
- [ ] **AI 协作过程**: 4 个阶段完整记录，含人/AI 分工、验证方式、耗时对比
- [ ] **效率对比表**: 5 个阶段 + 总计，数据量化
- [ ] **关键洞察**: 3-5 条，可复用、具体可执行
- [ ] **适用场景**: 标签完整勾选
- [ ] **交付物**: PRD/DESIGN/代码/测试/数据/洞察/场景

---

### 🔍 质量标准

#### 效率数据真实性
- [ ] 数据来源可追溯 (Git commit / 计时记录 / 截图)
- [ ] "传统方式" 基线合理 (非夸大)
- [ ] "AI 协作" 含真实 AI 工作时间 (非仅人工监控时间)
- [ ] 提升倍数计算正确: 传统小时数 / (AI 分钟数 / 60)

#### 协作过程真实性
- [ ] 记录了具体的 Prompt / 交互片段
- [ ] 记录了 AI 失误/幻觉及修复过程
- [ ] 人工验证步骤明确 (非完全信任 AI)
- [ ] TDD 循环证据: Test First → Implement → Verify

#### 关键洞察可复用性
- [ ] 洞察非泛泛而谈 (如 "AI 很快" ❌ → "结构化 Prompt 让 LLM 输出可解析 JSON" ✅)
- [ ] 适用场景标注清晰
- [ ] 其他开发者能直接应用

---

### 📄 格式规范

- [ ] 文件命名: `case-studies/<kebab-case-title>/README.md`
- [ ] 使用 Wikilink 格式引用内部文档: `[[../docs/MOC|显示文本]]`
- [ ] 表格对齐正确
- [ ] 代码块标注语言
- [ ] 无明显错别字/语法错误

---

### 🧪 验证步骤 (Reviewer 执行)

```bash
# 1. 验证链接有效性
python -m tools.scripts.link_auditor case-studies/<case-name>/

# 2. 验证效率数据一致性
# 人工检查表格计算

# 3. 验证代码可运行 (如有)
cd case-studies/<case-name>/ && python -m pytest tests/ -v

# 3. 验证链接
python -m tools.scripts.link_auditor case-studies/<case-name>/README.md
```

---

## 📝 审查结论

| 维度 | 状态 | 备注 |
|------|------|------|
| 内容完整性 | ☐ 通过 / ☐ 需补全 |  |
| 数据真实性 | ☐ 通过 / ☐ 存疑 |  |
| 过程可复用性 | ☐ 通过 / ☐ 需改进 |  |
| 格式规范 | ☐ 通过 / ☐ 需修正 |  |
| **总体** | **☐ Approve / ☐ Request Changes** |  |

---

## 💬 审查意见

**优点**:
-

**需改进**:
1.
2.

**问题**:
-

---

/assign @<reviewer> /label `in-review` → `approved` 或 `needs-revision`
