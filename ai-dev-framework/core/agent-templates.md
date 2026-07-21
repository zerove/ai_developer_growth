# Agent Definition Templates
# 适用于任何项目的 Agent 定义模板

## 通用 Agent 模板

```yaml
# Agent: {agent-name}
# 适用于: {project-type}

agent-name: {agent-name}
description: "{description}"
version: "1.0.0"
author: "{author}"

# 职责定义
responsibilities:
  - "{responsibility_1}"
  - "{responsibility_2}"
  - "{responsibility_3}"

# 指令集 (具体、可验证)
instructions:
  - name: "{instruction_name}"
    command: "{command}"
    description: "{description}"
    validation:
      success: "{success_condition}"
      failure: "{failure_condition}"

# 工具权限 (最小权限原则)
tools:
  allowed:
    - "{tool_1}"
    - "{tool_2}"
  denied:
    - "{denied_tool_1}"

# 约束条件
constraints:
  - "{constraint_1}"
  - "{constraint_2}"

# 触发条件
triggers:
  on_commit:
    - "{trigger_1}"
  on_pr:
    - "{trigger_2}"
  scheduled:
    - schedule: "{cron}"
      action: "{action}"
```

## 预定义角色模板

### 1. Code Guardian (代码守护者)

```yaml
agent-name: code-guardian
description: "维护代码质量、安全、风格一致性"

responsibilities:
  - "执行代码风格检查"
  - "运行测试套件"
  - "安全扫描"
  - "依赖审计"

instructions:
  - name: "lint-check"
    command: "{lint_tool} {source_dir}"
    description: "代码风格检查"
    validation:
      success: "exit_code == 0"
      failure: "exit_code != 0"

  - name: "test-run"
    command: "{test_runner} {test_dir}"
    description: "运行测试"
    validation:
      success: "coverage >= {min_coverage}"
      failure: "coverage < {min_coverage}"

  - name: "security-scan"
    command: "{security_scanner} {source_dir}"
    description: "安全扫描"
    validation:
      success: "no_critical_vulnerabilities"
      failure: "critical_vulnerabilities > 0"

tools:
  allowed:
    - "lint"
    - "test"
    - "security"
    - "build"

constraints:
  - "不能修改生产代码"
  - "不能跳过测试"
  - "不能忽略安全警告"
```

### 2. Doc Curator (文档策展人)

```yaml
agent-name: doc-curator
description: "维护文档完整性、链接有效性、结构一致性"

responsibilities:
  - "检查文档链接"
  - "验证文档格式"
  - "更新索引"
  - "同步文档与代码"

instructions:
  - name: "link-check"
    command: "{link_checker} {docs_dir}"
    description: "检查文档链接"
    validation:
      success: "broken_links == 0"
      failure: "broken_links > 0"

  - name: "doc-validate"
    command: "{doc_validator} {docs_dir}"
    description: "验证文档格式"
    validation:
      success: "all_docs_valid"
      failure: "invalid_docs > 0"

  - name: "index-update"
    command: "{index_updater} {docs_dir}"
    description: "更新文档索引"
    validation:
      success: "index_updated"
      failure: "index_outdated"

tools:
  allowed:
    - "read"
    - "write"
    - "edit"
    - "glob"

constraints:
  - "不能删除文档"
  - "不能修改文档结构"
  - "必须保持向后兼容"
```

### 3. Workflow Optimizer (工作流优化师)

```yaml
agent-name: workflow-optimizer
description: "分析开发效率、优化工作流程"

responsibilities:
  - "收集效率数据"
  - "分析瓶颈"
  - "推荐改进"
  - "追踪改进效果"

instructions:
  - name: "collect-metrics"
    command: "{metrics_collector}"
    description: "收集效率指标"
    validation:
      success: "metrics_collected"
      failure: "metrics_missing"

  - name: "analyze-bottleneck"
    command: "{analyzer}"
    description: "分析瓶颈"
    validation:
      success: "bottlenecks_identified"
      failure: "analysis_failed"

  - name: "recommend-improvement"
    command: "{recommender}"
    description: "推荐改进"
    validation:
      success: "recommendations_generated"
      failure: "no_recommendations"

tools:
  allowed:
    - "read"
    - "write"
    - "analytics"

constraints:
  - "不能修改生产代码"
  - "只能推荐，不能强制执行"
  - "必须基于数据"
```

## 项目特定 Agent 扩展

在通用模板基础上，项目可以定义特定 Agent:

```yaml
# 示例: 知识库项目的 Knowledge Curator
agent-name: knowledge-curator
extends: doc-curator  # 继承通用 Doc Curator

# 添加特定职责
additional_responsibilities:
  - "验证案例格式"
  - "更新知识图谱"
  - "同步工具矩阵"

# 添加特定指令
additional_instructions:
  - name: "case-validate"
    command: "python scripts/validate_case.py {case_dir}"
    description: "验证案例格式"

  - name: "knowledge-graph-update"
    command: "python scripts/update_graph.py {docs_dir}"
    description: "更新知识图谱"
```

## 使用方式

### 1. 使用通用模板

```bash
# 生成 Agent 定义
jcode agent init --template code-guardian --name my-guardian

# 或使用项目配置
jcode agent init --from-config project.yaml
```

### 2. 自定义 Agent

```bash
# 基于模板创建
jcode agent create --base code-guardian --name custom-guardian

# 编辑生成的定义
vim agents/custom-guardian.yaml
```

### 3. 注册 Agent

```bash
# 注册到 registry
jcode agent register agents/custom-guardian.yaml

# 或批量注册
jcode agent register-all agents/
```
