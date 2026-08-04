# governance-auditor Skill

自动化审计代码质量、安全漏洞、

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
- `validate-governance-docs` - 验证15个治理层文档
- `check-ai-sdlc-compliance` - 检查 AI-SDLC 合规性
- `audit-hallucination-risks` - 审计幻觉风险
- `audit-sdlc` - AI-SDLC 5 阶段合规审计
- `validate-agent-definition` - 验证 Agent 定义格式
- `check-ai-annotation` - 检查 AI 代码标注
- `ai-quality-gate` - 运行 AI 代码质量门禁
- `full` - 运行完整审计（包含所有检查）

## Examples

```bash
# 运行 lint 检查
/governance-auditor lint

# 运行完整审计
/governance-auditor full

# 运行测试
/governance-auditor test

# 验证治理文档
/governance-auditor validate-governance-docs

# 检查 AI-SDLC 合规性
/governance-auditor check-ai-sdlc-compliance

# 审计幻觉风险
/governance-auditor audit-hallucination-risks

# AI-SDLC 合规审计
/governance-auditor audit-sdlc

# 验证 Agent 定义
/governance-auditor validate-agent-definition

# 检查 AI 代码标注
/governance-auditor check-ai-annotation

# 运行 AI 代码质量门禁
/governance-auditor ai-quality-gate
```

## Implementation

This skill runs the following commands:

1. `ruff check .` - 代码风格检查
2. `ruff format --check .` - 格式检查
3. `mypy tools/scripts/ --ignore-missing-imports` - 类型检查
4. `python -m pytest tests/ -v --cov=tools/scripts` - 测试套件
5. `bandit -r tools/scripts/` - 安全扫描
6. 验证15个治理层文档的 frontmatter、
7. 检查 CI/CD、pre-commit 配置完整性
8. 扫描代码中的不安全模式和文档中的绝对化声明
9. `python tools/scripts/validate_agent_definition.py` - 验证 Agent 定义格式
10. `python tools/scripts/check_ai_annotation.py` - 检查 AI 代码标注
11. `python tools/scripts/ai_quality_gate.py --full` - AI 代码质量门禁
12. `adg-dev audit sdlc --path <project>` - AI-SDLC 5 阶段合规审计（需求→设计→编码→测试→部署）

## Enforcement Scripts

### validate_agent_definition.py
验证 Agent 定义文件是否符合 GOVERNANCE.md 规范:
- 命名规范 (kebab-case)
- 必需字段 (描述、工具、约束、指令)
- 工具权限最小化
- 约束完整性

### check_ai_annotation.py
检查 AI 生成的代码是否包含 [AI-GEN] 标注:
- 检测 AI 生成指标
- 验证标注存在
- 自动添加标注 (--fix)

### ai_quality_gate.py
集成所有 AI 代码质量检查:
- AI 代码标注 ([AI-GEN])
- 安全模式检查 (SQL 拼接、硬编码密钥等)
- 类型安全检查 (unwrap/as any)
- 错误处理检查
- 代码结构检查

## Governance Docs Validated

- ai-code-generation-quality.md - AI 代码生成质量标准
- ai-model-selection.md - AI 模型选择标准
- ai-sdlc.md - AI 软-review-checklist.md - AI 代码审查检查清单
- ai-nondeterministic-testing.md - 非确定性测试标准
- ai-hallucination-mitigation.md - 幻觉缓解策略
- ai-code-licensing.md - AI -environment.md - AI 开发环境配置
- ai-context-window-management.md - 上下文窗口管理
- ai-performance-benchmarks.md - AI 性能基准
- ai-debugging-standards.md - AI 调试标准
- ai-version-control.md - AI 代码版本控制
- ai-deployment-operations.md - AI 部署运维标准
- ai-developer-training.md - AI 开发者培训标准
- ai-dev-toolchain.md - AI 开发工具链

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
- Pytest 测试通过（覆盖率 ≥80%）
- AI 代码质量门禁通过

### Gate 4: 资产更新审查
- README 更新
- CHANGELOG 更新
- ADR 记录（如适用）
- INDEX.md 更新
- MOC.md 更新
