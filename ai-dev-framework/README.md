# ai-dev-framework

> **AI Agent 开发治理框架** — 适用于任何项目的 AI Agent 开发治理标准。

`pip install ai-dev-framework`（安装后提供的命令是 `adg-dev`）

---

## 快速开始

```bash
# 初始化项目治理配置
adg-dev init my-project

# 检查治理状态
adg-dev check
```

## 功能

- **参数化配置**: 按语言/框架/项目类型自动推荐工具链
- **钩子系统**: 基于事件的自动化触发器（commit/PR/merge/scheduled）
- **Agent 定义**: 为项目自动生成 AI Agent 定义
- **质量门禁**: 4 道门禁确保代码质量

## 为什么需要治理框架？

AI 辅助开发正在改变软件工程，但带来了新挑战：

- Agent 行为不可预测 → 需要标准化定义
- 代码质量波动 → 需要自动化门禁
- AI 生成代码的幻觉 → 需要审计机制
- 多 AI 工具协作 → 需要统一配置

## 使用场景

| 场景 | 说明 |
|------|------|
| 新项目初始化 | `adg-dev init` 一键生成治理配置 |
| 现有项目接入 | 复制 `GOVERNANCE.md` 并根据语言调整 |
| 团队标准化 | 统一 AI Agent 行为规范 |
| CI/CD 集成 | 钩子系统自动触发质量检查 |

## 集成

支持与 opencode、jcode、pre-commit 等工具集成。详见 `docs/` 目录。

---

**License**: MIT
