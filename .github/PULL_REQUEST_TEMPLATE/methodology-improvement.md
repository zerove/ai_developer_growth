---
name: methodology-improvement
about: 方法论文档改进 PR
title: "[Methodology] <文档路径> - <改进摘要>"
labels: ["methodology", "review"]
assignees: ""
---

## 📄 关联 Issue

Closes #<issue_number>

---

## 📝 变更摘要

| 维度 | 说明 |
|------|------|
| **目标文档** | `docs/<category>/<filename>.md` |
| **改进类型** | 内容修正 / 章节补充 / 案例支撑 / 结构优化 / 术语统一 / 工具更新 |
| **影响范围** | 单文档 / 跨文档术语 / 学习路径 |

---

## 🔍 变更详情

### 修改前
<引用原文或描述原状>

### 修改后
<展示新内容或描述新状况>

---

## ✅ 质量检查

- [ ] **内容准确性**: 信息经验证，引用可靠来源
- [ ] **术语一致性**: 与 UBIQUITOUS_LANGUAGE.md 对齐
- [ ] **链接有效性**: 运行 `python -m tools.scripts.link_auditor docs/<category>/<filename>.md` 通过
- [ ] **格式规范**: 标题层级、表格对齐、代码块标注语言
- [ ] **案例支撑**: 新增内容有真实案例或权威来源支撑
- [ ] **学习路径**: 如影响学习路径，已同步更新 MOC.md/INDEX.md

---

## 🧪 验证步骤

```bash
# 1. 链接检查
python -m tools.scripts.link_auditor docs/<category>/<filename>.md

# 2. 术语一致性检查
python -m tools.scripts.check_ubiquitous_language

# 3. 文档结构检查
python -m tools.scripts.validate_case_study --path docs/<category>/<filename>.md
```

---

## 📸 截图/对比 (如适用)

| 修改前 | 修改后 |
|--------|--------|
| ![before](url) | ![after](url) |

---

## 📝 审查重点

请重点关注：
1.
2.

---

/label `in-review` /assign @<reviewer>
