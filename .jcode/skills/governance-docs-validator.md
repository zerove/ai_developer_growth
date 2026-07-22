# governance-docs-validator Skill

验证治理层、索引引用、交叉引用同步

## Usage

```
/governance-docs-validator [action]
```

### Actions

- `validate` - 验证15个治理层文档的 frontmatter、导航、内容结构
- `check-index` - 验证 GOVERNANCE.md、INDEX.md、CLAUDE.md 中的引用完整性
- `sync-refs` - 同步治理文档的交叉引用
- `full` - 运行完整验证

## Examples

```bash
# 验证文档格式
/governance-docs-validator validate

# 检查索引引用
/governance-docs-validator check-index

# 同步交叉引用
/governance-docs-validator sync-refs

# 运行完整验证
/governance-docs-validator full
```

## Implementation

This skill runs `python .jcode/scripts/governance-docs-validator.py <action>`

### Validation Checks

1. **Frontmatter 完整性**: 检查 title、description、category、tags、difficulty 字段
2. **标题格式**: 确保标题包含英文后缀
3. **分类有效性**: 验证 category 在允许列表中
4. **导航部分**: 确保存在 `## 导航` 或 `## Navigation`
5. **相关文档**: 确保存在相关文档引用部分
6. **内容结构**: 至少包含3个二级标题

### Index Checks

- GOVERNANCE.md 包含所有15个文档引用
- INDEX.md 包含所有15个文档引用
- CLAUDE.md 包含所有15个文档引用

## Constraints

- 不修改文档核心内容
- 仅验证格式和引用完整性
- 修复操作仅添加缺失的引用，不删除现有内容
