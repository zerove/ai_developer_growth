# governance-auditor Skill

自动化审计代码质量、安全漏洞、治理标准合规性

## Usage

```
/governance-auditor [action]
```

### Actions

- `lint` - 运行 ruff lint 检查
- `format` - 运行 ruff format 检查
- `typecheck` - 运行 mypy 类型检查
- `test` - 运行 pytest 测试套件
- `security` - 运行安全扫描
- `full` - 运行完整审计

## Examples

```bash
# 运行 lint 检查
/governance-auditor lint

# 运行完整审计
/governance-auditor full

# 运行测试
/governance-auditor test
```

## Implementation

This skill runs the following commands:

1. `ruff check .` - 代码风格检查
2. `ruff format --check .` - 格式检查
3. `mypy tools/scripts/ --ignore-missing-imports` - 类型检查
4. `python -m pytest tests/ -v --cov=tools/scripts` - 测试套件
5. `bandit -r tools/scripts/` - 安全扫描

## Quality Gates

### Gate 1: Prompt 设计审查
- Agent 名称符合命名规范
- 描述清晰、无歧义
- 指令具体、可验证

### Gate 2: 实现编码审查
- 代码符合项目编码规范
- 无 `unwrap()`/`expect()` 在生产代码
- 错误处理完整
- 测试覆盖核心逻辑

### Gate 3: 自动化审计
- Ruff lint 通过
- MyPy 类型检查通过
- Pytest 测试通过（覆盖率 ≥70%）

### Gate 4: 文档审查
- README 更新
- CHANGELOG 更新
- ADR 记录（如适用）
