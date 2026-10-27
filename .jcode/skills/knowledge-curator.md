# knowledge-curator Skill

维护知识库结构完整性、收集真实案例、审核文档质量、更新 INDEX/MOC

## Usage

```
/knowledge-curator [action]
```

### Actions

- `scan` - 扫描所有案例格式完整性
- `audit` - 检查文档断链
- `validate <file>` - 验证新提交案例
- `sync` - 同步工具矩阵
- `update-moc` - 更新知识图谱（尚未实现，返回非零）

> `update-moc` 当前是显式失败占位：历史实现调用 `link_auditor.py --update-moc`
> （该参数不存在）。MOC 更新需要独立脚本，完成前不纳入自动化工作流。

## Examples

```bash
# 扫描所有案例
/knowledge-curator scan

# 检查文档断链
/knowledge-curator audit

# 验证新案例
/knowledge-curator validate case-studies/new-case.md

# 同步工具矩阵
/knowledge-curator sync

# 更新知识图谱（尚未实现）
/knowledge-curator update-moc
```

## Implementation

This skill runs the following scripts:

1. `tools/scripts/validate_case_study.py` - 案例验证
2. `tools/scripts/link_auditor.py` - 断链检查
3. `tools/scripts/update_ai_tool_matrix.py` - 工具矩阵更新

## Constraints

- 不修改核心方法论文档内容，仅维护索引和统计
- 所有验证脚本必须在 CI/CD 中自动运行
- 新术语必须先在 `UBIQUITOUS_LANGUAGE.md` 定义后再使用
- 案例研究必须包含效率对比数据（≥3个维度）
