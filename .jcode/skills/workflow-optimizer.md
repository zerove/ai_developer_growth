# workflow-optimizer Skill

分析 AI 协作效率数据、优化全周期工作流、推荐工具组合

## Usage

```
/workflow-optimizer [action]
```

### Actions

- `analyze` - 分析效率数据
- `recommend` - 推荐工具组合
- `report` - 生成效率报告

## Examples

```bash
# 分析效率数据
/workflow-optimizer analyze

# 推荐工具组合
/workflow-optimizer recommend

# 生成效率报告
/workflow-optimizer report
```

## Implementation

This skill analyzes:

1. `case-studies/` - 案例效率数据
2. `docs/tools/ai-tool-matrix.md` - 工具矩阵
3. `docs/efficiency/` - 效率方法论

## Metrics Framework

### 效率指标
- **开发速度**: 代码产出/小时
- **质量指标**: Bug 率、测试覆盖率
- **学习曲线**: 新技术掌握时间
- **协作效率**: 人机协作比

### 工具评估
- **模型性能**: 准确度、响应时间
- **IDE 效率**: 代码补全、重构支持
- **Agent 能力**: 任务自动化程度
