---
title: "🚀 JCode AI-Native SDLC 开发者快速上手指南"
description: "category: 效率层"
category: 效率层
tags: [quick-start, ai-native, sdlc, jcode, workflow]
difficulty: 入门
---

# 🚀 JCode AI-Native SDLC 开发者快速上手指南

欢迎使用 **JCode AI-Native SDLC 研发框架**！本指南将带你用最短的时间掌握如何利用本项目内置的 11 大核心自动化模块、DoR 门禁、密码学审计账本、TDD 状态机与主控流水线，实现高效、高质量的 AI 驱动研发。

---

## ⏱️ 5 分钟极速上手

### 1. 环境初始化（零摩擦向导）
在任意项目中执行初始化向导，自动配置 `.jcode/rules/`、生成 MCP 服务配置并构建语义代码知识图谱：
```bash
python tools/scripts/jcode_setup_wizard.py
```

### 2. 一键运行全套 AI-Native 主流水线
通过主控流水线脚本或跨平台任务运行器，一键执行从意图验证、架构检查、蜂群实现、污点扫描到加密审计的全流程：
```bash
# 方式 A：直接运行主管道
python tools/scripts/jcode_ai_native_workflow.py "实现用户认证与 JWT 鉴权功能"

# 方式 B：使用跨平台任务运行器
python tools/scripts/jcode_cross_platform_runner.py workflow-ai-native
```

---

## 🛠️ 常用开发命令速查 (Cross-Platform Runner)

本项目提供不依赖 Makefile 的跨平台 Python 任务运行器 (`jcode_cross_platform_runner.py`)，支持 Windows、macOS 和 Linux：

| 命令 | 说明 |
|------|------|
| `python tools/scripts/jcode_cross_platform_runner.py check` | 运行专项单元测试 (`test_ai_native_sdlc.py`) |
| `python tools/scripts/jcode_cross_platform_runner.py semantic-graph` | 生成/更新语义代码知识图谱 (`.semantic_graph.json`) |
| `python tools/scripts/jcode_cross_platform_runner.py architecture-guard` | 运行架构漂移防御检查 |
| `python tools/scripts/jcode_cross_platform_runner.py slop-scan` | 扫描 AI 代码异味与幻觉风险 |
| `python tools/scripts/jcode_cross_platform_runner.py metrics-telemetry` | 收集研发效能与质量遥测数据 |
| `python tools/scripts/jcode_cross_platform_runner.py swarm-run` | 运行自主智能体蜂群与自举演进闭环 |
| `python tools/scripts/jcode_cross_platform_runner.py dashboard` | 启动 AI-Native 终端驾驶舱 |
| `python tools/scripts/jcode_cross_platform_runner.py self-evolve` | 运行自适应规则与 Prompt 进化引擎 |

---

## 🧠 核心机制与最佳实践

### 1. DoR (Definition-of-Ready) 意图准入
* **规则**：任务分发前必须通过 7 点二元可测 Rubric 校验（无 `TBD`、有明确验收标准）。
* **收益**：防止模糊需求导致 AI 产生幻觉或过度工程化。

### 2. 严格 TDD 三阶段状态机 (`RED` $\rightarrow$ `GREEN` $\rightarrow$ `REFACTOR`)
* **规则**：
  1. **RED**：仅编写失败测试，禁止编写实现。
  2. **GREEN**：最小实现通过测试，禁止修改测试。
  3. **REFACTOR**：重构优化，禁止盲目引入新抽象。
* **收益**：确保 AI 的每行代码都有精确的测试契约保护。

### 3. 小批次护栏 (Scope Guard)
* **规则**：单次 AI 变更应保持在推荐的文件数与行数阈值内（小批次），防止范围蔓延 (Scope Creep) 导致系统稳定性下降。

### 4. 密码学可审计账本 (Audit Attestation)
* **规则**：所有的执行状态与轨迹均通过 SHA-256 哈希链（Chained Hash Log）永久记录在 `.quality-trends/audit_ledger.jsonl` 中，确保全程防篡改、高合规。
