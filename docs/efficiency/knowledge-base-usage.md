---
title: OpenCode 知识库使用方案 (Knowledge Base Usage Plan)
description: > 将35篇知识文档转化为开发实践。
category: 效率层
tags: ['base', 'AI', 'Python', '测试', '安全']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# OpenCode 知识库使用方案 (Knowledge Base Usage Plan)

> 将35篇知识文档转化为开发实践。

---

## 概述

本文档提供将知识库内容系统化应用于 OpenCode 开发的完整方案，包括文档引用规则、工作流集成、自动化配置。

---

## 1. 文档引用规则

### 1.1 文档分类与使用场景

| 文档类型 | 使用场景 | 引用方式 | 优先级 |
|----------|----------|----------|--------|
| **认知层** | 决策、规划 | 项目开始时 | 高 |
| **学习层** | 技能提升 | 遇到新领域时 | 中 |
| **效率层** | 日常开发 | 每次开发 | 高 |
| **工具层** | 工具选型 | 选择工具时 | 中 |
| **案例库** | 参考借鉴 | 相似场景时 | 低 |

### 1.2 文档引用模板

```markdown
# OpenCode 任务引用模板

## 任务描述
[具体任务]

## 引用文档
- 核心文档: [[efficiency/full-cycle-workflow|全周期工作流]]
- 参考文档: [[efficiency/anti-patterns|反模式与失败案例]]
- 工具文档: [[tools/ai-tool-matrix|工具矩阵]]

## 约束条件
- 遵循文档中的最佳实践
- 避免文档中提到的反模式
- 参考文档中的真实案例

## 输出要求
- 代码符合文档中的规范
- 测试覆盖文档中的要求
- 文档更新反映变更
```

---

## 2. 开发阶段文档集成

### 2.1 需求分析阶段

**引用文档**:
- [[mindset/product-thinking|产品思维]]
- [[efficiency/full-cycle-workflow|全周期工作流]]

**OpenCode Prompt**:
```markdown
## 任务: 需求分析

### 参考文档
- [[mindset/product-thinking]]: 产品思维原则
- [[efficiency/full-cycle-workflow]]: 需求分析阶段

### 输入
- 用户需求: [需求描述]
- 项目背景: [背景信息]

### 输出要求
1. 结构化 PRD
2. 用户故事
3. 功能矩阵
4. 边界条件

### 约束
- 遵循"用户价值优先"原则
- 避免"实现陷阱"
- 考虑边界情况
```

### 2.2 架构设计阶段

**引用文档**:
- [[efficiency/context-engineering|上下文工程]]
- [[efficiency/multi-agent-patterns|多 Agent 编排]]

**OpenCode Prompt**:
```markdown
## 任务: 架构设计

### 参考文档
- [[efficiency/context-engineering]]: 上下文管理
- [[efficiency/multi-agent-patterns]]: 编排模式

### 输入
- PRD 文档: [链接]
- 技术约束: [约束列表]

### 输出要求
1. 系统架构图
2. 模块划分
3. 接口设计
4. 数据模型

### 约束
- 模块边界清晰
- 接口契约明确
- 可扩展性设计
```

### 2.3 编码实现阶段

**引用文档**:
- [[efficiency/full-cycle-workflow|全周期工作流]]
- [[efficiency/anti-patterns|反模式与失败案例]]
- [[efficiency/token-optimization|Token 成本控制]]

**OpenCode Prompt**:
```markdown
## 任务: 编码实现

### 参考文档
- [[efficiency/full-cycle-workflow]]: 编码实现阶段
- [[efficiency/anti-patterns]]: 避免反模式
- [[efficiency/token-optimization]]: 成本控制

### 输入
- 架构设计: [链接]
- 接口定义: [链接]

### 输出要求
1. 代码实现
2. 单元测试
3. 代码注释
4. 文档更新

### 约束
- 遵循代码规范
- 测试覆盖率 > 80%
- 避免反模式
- 控制 Token 消耗
```

### 2.4 测试验证阶段

**引用文档**:
- [[efficiency/automated-bug-fixing|自动化修复]]
- [[efficiency/ai-security-review|安全审查]]

**OpenCode Prompt**:
```markdown
## 任务: 测试验证

### 参考文档
- [[efficiency/automated-bug-fixing]]: 测试策略
- [[efficiency/ai-security-review]]: 安全测试

### 输入
- 代码实现: [链接]
- 测试用例: [链接]

### 输出要求
1. 测试报告
2. 覆盖率报告
3. 安全扫描报告
4. 性能测试报告

### 约束
- 测试通过率 100%
- 覆盖率 > 80%
- 无高危漏洞
- 性能达标
```

### 2.5 部署上线阶段

**引用文档**:
- [[efficiency/full-cycle-workflow|全周期工作流]]
- [[efficiency/metrics-framework|度量体系]]

**OpenCode Prompt**:
```markdown
## 任务: 部署上线

### 参考文档
- [[efficiency/full-cycle-workflow]]: 部署阶段
- [[efficiency/metrics-framework]]: 度量收集

### 输入
- 测试报告: [链接]
- 部署配置: [链接]

### 输出要求
1. 部署脚本
2. 监控配置
3. 告警规则
4. 度量指标

### 约束
- 回滚方案准备
- 监控覆盖关键路径
- 度量指标完整
```

---

## 3. 文档引用自动化

### 3.1 OpenCode 配置文件

**.opencode/config.json**:
```json
{
  "knowledge_base": {
    "path": "./docs",
    "auto_load": true,
    "trigger_keywords": {
      "product-thinking": ["需求", "产品", "用户价值"],
      "full-cycle-workflow": ["开发", "实现", "编码"],
      "anti-patterns": ["避免", "陷阱", "错误"],
      "token-optimization": ["成本", "Token", "效率"],
      "ai-security-review": ["安全", "漏洞", "审查"],
      "metrics-framework": ["度量", "指标", "ROI"]
    }
  }
}
```

### 3.2 自动引用脚本

**scripts/load-docs.sh**:
```bash
#!/bin/bash

# 根据任务类型加载相关文档
load_docs() {
    local task_type=$1

    case $task_type in
        "requirement")
            echo "加载需求分析文档..."
            cat docs/mindset/product-thinking.md
            cat docs/efficiency/full-cycle-workflow.md
            ;;
        "architecture")
            echo "加载架构设计文档..."
            cat docs/efficiency/context-engineering.md
            cat docs/efficiency/multi-agent-patterns.md
            ;;
        "coding")
            echo "加载编码实现文档..."
            cat docs/efficiency/full-cycle-workflow.md
            cat docs/efficiency/anti-patterns.md
            cat docs/efficiency/token-optimization.md
            ;;
        "testing")
            echo "加载测试验证文档..."
            cat docs/efficiency/automated-bug-fixing.md
            cat docs/efficiency/ai-security-review.md
            ;;
        "deployment")
            echo "加载部署上线文档..."
            cat docs/efficiency/full-cycle-workflow.md
            cat docs/efficiency/metrics-framework.md
            ;;
        *)
            echo "加载全部文档..."
            cat docs/**/*.md
            ;;
    esac
}

# 使用示例
# ./load-docs.sh requirement
# ./load-docs.sh coding
```

### 3.3 OpenCode Skill 集成

**skills/knowledge-base/SKILL.md**:
```markdown
# Knowledge Base Skill

## 触发条件
- 用户提到"知识库"、"文档"、"最佳实践"
- 任务涉及新功能开发
- 任务涉及代码审查

## 加载逻辑
1. 解析任务类型
2. 加载相关文档
3. 提取关键约束
4. 应用到当前任务

## 文档映射
- 需求分析 → product-thinking, full-cycle-workflow
- 架构设计 → context-engineering, multi-agent-patterns
- 编码实现 → full-cycle-workflow, anti-patterns, token-optimization
- 测试验证 → automated-bug-fixing, ai-security-review
- 部署上线 → full-cycle-workflow, metrics-framework

## 输出格式
```markdown
## 知识库应用

### 相关文档
- [文档1]: [核心要点]
- [文档2]: [核心要点]

### 约束条件
- [约束1]
- [约束2]

### 最佳实践
- [实践1]
- [实践2]

### 反模式警告
- [警告1]
- [警告2]
```
```

---

## 4. 文档引用示例

### 4.1 完整开发流程示例

**场景**: 开发用户认证模块

**步骤 1: 需求分析**
```markdown
## 任务: 用户认证需求分析

### 引用文档
- [[mindset/product-thinking]]: 产品思维
- [[efficiency/full-cycle-workflow]]: 需求分析阶段

### Prompt
参考 [[mindset/product-thinking]] 中的"用户价值优先"原则，
分析用户认证模块的核心价值。

参考 [[efficiency/full-cycle-workflow]] 中的需求分析阶段，
生成包含用户故事、功能矩阵、边界条件的 PRD。

### 输出
- PRD 文档
- 用户故事
- 功能矩阵
- 边界条件
```

**步骤 2: 架构设计**
```markdown
## 任务: 用户认证架构设计

### 引用文档
- [[efficiency/context-engineering]]: 上下文管理
- [[efficiency/multi-agent-patterns]]: 编排模式

### Prompt
参考 [[efficiency/context-engineering]] 中的"分层上下文策略"，
设计认证模块的架构。

参考 [[efficiency/multi-agent-patterns]] 中的"主从模式"，
设计多 Agent 协作方案。

### 输出
- 系统架构图
- 模块划分
- 接口设计
- 数据模型
```

**步骤 3: 编码实现**
```markdown
## 任务: 用户认证编码实现

### 引用文档
- [[efficiency/full-cycle-workflow]]: 编码实现阶段
- [[efficiency/anti-patterns]]: 避免反模式
- [[efficiency/token-optimization]]: 成本控制

### Prompt
参考 [[efficiency/full-cycle-workflow]] 中的"TDD 驱动开发"，
先写测试再实现。

参考 [[efficiency/anti-patterns]] 中的"安全盲区型"，
确保认证代码的安全性。

参考 [[efficiency/token-optimization]] 中的"分层模型使用"，
选择合适的模型。

### 输出
- 代码实现
- 单元测试
- 代码注释
- 文档更新
```

**步骤 4: 测试验证**
```markdown
## 任务: 用户认证测试验证

### 引用文档
- [[efficiency/automated-bug-fixing]]: 测试策略
- [[efficiency/ai-security-review]]: 安全测试

### Prompt
参考 [[efficiency/automated-bug-fixing]] 中的"验证套件"，
设计完整的测试方案。

参考 [[efficiency/ai-security-review]] 中的"OWASP Top 10"，
进行安全测试。

### 输出
- 测试报告
- 覆盖率报告
- 安全扫描报告
- 性能测试报告
```

---

## 5. 度量与优化

### 5.1 文档使用度量

**度量指标**:
- 文档引用频率
- 文档应用效果
- 文档更新及时性
- 文档覆盖完整性

**度量工具**:
```python
# 记录文档引用
def log_doc_usage(doc_name, task_type, success_rate):
    # 存储到数据库
    db.insert({
        'doc_name': doc_name,
        'task_type': task_type,
        'success_rate': success_rate,
        'timestamp': datetime.now()
    })
```

### 5.2 文档优化流程

```
1. 收集使用反馈
   └── 开发者反馈、效果数据

2. 分析问题
   └── 识别低效文档、缺失内容

3. 优化文档
   └── 更新内容、补充案例

4. 验证效果
   └── A/B 测试、效果对比

5. 持续改进
   └── 定期回顾、迭代优化
```

---

## 6. 常见问题

### Q1: 文档太多，如何选择？

**选择策略**:
- 根据任务类型选择核心文档
- 使用自动化工具辅助选择
- 建立文档优先级机制

### Q2: 文档过时如何处理？

**更新机制**:
- 定期审查文档时效性
- 建立文档更新流程
- 使用版本控制管理文档

### Q3: 如何确保文档被使用？

**推广策略**:
- 集成到开发流程
- 建立使用激励
- 定期培训和分享

---

## 总结

**核心原则**:
1. **场景驱动**: 根据任务类型选择文档
2. **自动化优先**: 使用工具辅助文档加载
3. **持续优化**: 根据反馈迭代文档
4. **效果度量**: 量化文档应用价值

**关键行动**:
1. 建立文档引用规则
2. 配置自动化工具
3. 集成到开发流程
4. 度量和优化效果

---

**📂 导航**
- [[MOC|⬅️ 返回知识地图]]
- **相关文章**: [[efficiency/full-cycle-workflow|全周期工作流]] | [[tools/ide-best-practices|IDE 最佳实践]]
---

## 导航

**分类**: 效率层

**相关文档**:

- [[docs/efficiency/full-cycle-workflow|全周期工作流]]
- [[docs/efficiency/automated-bug-fixing|自动化修复]]
- [[docs/efficiency/anti-patterns|反模式]]
- [[docs/efficiency/context-engineering|上下文工程]]
- [[docs/efficiency/token-optimization|Token 优化]]
