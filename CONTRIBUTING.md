# 贡献指南

感谢你对 AI Developer Growth 项目的关注！我们欢迎各种形式的贡献。

---

## 贡献类型

### 1. 案例提交 (Case Study)

提交你在 AI 协作开发中的实战案例。

**要求**:
- 真实项目，非虚构
- 包含效率提升数据
- 有关键洞察和适用场景
- 格式符合模板

**提交流程**:
1. Fork 本仓库
2. 创建案例文件: `case-studies/your-case-study.md`
3. 参考模板: `.github/ISSUE_TEMPLATE/case-study.md`
4. 提交 PR，选择"案例提交"类型

### 2. 工具推荐 (Tool Recommendation)

推荐新的 AI 开发工具。

**要求**:
- 工具真实存在
- 提供官网链接
- 说明核心功能和适用场景
- 分析优劣势

**提交流程**:
1. Fork 本仓库
2. 更新 `docs/tools/ai-tool-matrix.md`
3. 提交 PR，选择"工具推荐"类型

### 3. 文档改进 (Documentation)

改进现有文档。

**类型**:
- 修复错误
- 补充内容
- 改进表达
- 添加示例

**提交流程**:
1. Fork 本仓库
2. 修改文档
3. 提交 PR，选择"文档改进"类型

### 4. 代码贡献 (Code Contribution)

贡献代码示例或工具。

**要求**:
- 代码可运行
- 有测试覆盖
- 符合项目规范

**提交流程**:
1. Fork 本仓库
2. 创建功能分支
3. 编写代码和测试
4. 提交 PR

### 5. 语言规则贡献 (Language Rules)

为新的编程语言添加代码质量规则。

**快速开始**:
```bash
# 初始化新语言规则目录
python tools/scripts/rule_author.py init --lang mylang

# 添加反模式规则
python tools/scripts/rule_author.py add-rule --lang mylang \
  --category anti_patterns \
  --id mylang-bare-except \
  --name "Bare except" \
  --severity error \
  --pattern 'except\s*:' \
  --message "Avoid bare except"

# 验证规则
python tools/scripts/rule_author.py validate \
  --file ai-dev-framework/languages/mylang/rules.d/anti_patterns.yml

# 测试规则正则
python tools/scripts/validate_rule_tests.py --lang mylang
```

**规则 YAML 格式**:
```yaml
language: mylang
version: '>=1.0'
config_version: '1.0'
anti_patterns:
  - id: mylang-rule-id
    name: Human readable name
    severity: error  # error | warning | info
    category: security  # security | error_handling | type_safety | code_quality
    pattern: 'regex pattern'
    message: What's wrong
    fix_hint: How to fix
    test_cases:
      - code: 'code that matches'
        should_match: true
      - code: 'code that does not match'
        should_match: false
```

**提交流程**:
1. Fork 本仓库
2. 运行 `python tools/scripts/rule_author.py init --lang yourlang`
3. 添加规则到 `ai-dev-framework/languages/yourlang/rules.d/anti_patterns.yml`
4. 添加测试用例 (test_cases)
5. 运行 `python tools/scripts/validate_rule_tests.py --lang yourlang` 验证
6. 运行 `python -m pytest tests/test_validate_language_rules.py -v` 确保不破坏现有测试
7. 提交 PR

### 前置条件

- Python 3.11+
- pip
- git

### 安装

```bash
# 克隆仓库
git clone https://github.com/zerove/ai_developer_growth.git
cd ai_developer_growth

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖
pip install ruff mypy pytest pytest-cov
```

### 开发工具

```bash
# 代码检查
ruff check .

# 代码格式化
ruff format .

# 类型检查
mypy .

# 运行测试
pytest

# 测试覆盖率
pytest --cov=. --cov-report=term-missing
```

---

## 代码规范

### Python

- 遵循 PEP 8
- 使用 type hints
- 添加 docstrings
- 避免 `except Exception`

### Markdown

- 使用中文
- 遵循项目术语表
- 保持格式一致
- 验证链接有效性

---

## 提交规范

### Commit Message

```
<type>: <subject>

<body>

<footer>
```

**Type**:
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 其他

**示例**:
```
feat: add new case study for Cursor collaboration

- Added case study: AI-assisted refactoring
- Included efficiency metrics
- Added key insights and applicable scenarios

Closes #123
```

---

## 审核流程

### 案例提交审核

1. **自动化检查**: 格式验证、链接检查
2. **社区催化剂**: 验证案例真实性、效率数据
3. **工作流优化师**: 评估效率提升数据
4. **知识策展人**: 整合到知识库

### 代码提交审核

1. **自动化检查**: lint、类型检查、测试
2. **治理审计员**: 代码质量、安全检查
3. **Reviewer**: 代码逻辑、设计审查

---

## 社区准则

### 行为准则

- 尊重每一位贡献者
- 建设性反馈
- 包容不同观点
- 专注于技术讨论

### 沟通方式

- **GitHub Issues**: 问题讨论
- **GitHub PRs**: 代码审查
- **Discussions**: 一般讨论

---

## 贡献者认可

### 贡献者排行榜

所有贡献者将在 README 中得到认可。

### 贡献者等级

| 等级 | 要求 | 权限 |
|------|------|------|
| 贡献者 | 1+ 合并 PR | 标签管理 |
| 活跃贡献者 | 5+ 合并 PR | Issue 管理 |
| 核心贡献者 | 10+ 合并 PR | PR 审核 |
| 维护者 | 20+ 合并 PR | 仓库管理 |

---

## 获取帮助

如有疑问，请：

1. 查看现有文档
2. 搜索 GitHub Issues
3. 提交新 Issue

---

## 致谢

感谢所有为 AI Developer Growth 项目做出贡献的人！
