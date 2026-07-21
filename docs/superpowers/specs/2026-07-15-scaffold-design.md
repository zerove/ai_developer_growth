---
title: 设计规格：dx scaffold 指令 (2026-07-15)
description: 设计规格：dx scaffold 指令 (2026-07-15) - 技术文档
category: 效率层
tags: ['AI', '07', 'Python', '15', '2026']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# 设计规格：dx scaffold 指令 (2026-07-15)

## 概述
实现 `dx scaffold <template>` 指令，用于快速基于预定义模板初始化项目骨架，并自动配置 `ai-context-sync` 环境。

## 架构设计
- **位置**: `examples/ai-context-sync/src/cli.py`
- **依赖**: `typer`, `shutil`, `os`
- **执行流程**:
  1. `typer` 命令解析 `<template>` 参数。
  2. 校验当前工作目录是否为空（仅允许包含 `.git` 或 `.DS_Store`）。
  3. 读取 `templates/<template>` 目录内容。
  4. 将模板文件递归复制到目标路径。
  5. 内部调用 `init()` 函数生成 `.ai-sync.json`。
  6. 在 `CONTEXT.md` 中添加初始化元数据。

## 接口设计
```python
@app.command()
def scaffold(
    template: str = typer.Argument(..., help="模板名称（位于 templates/ 目录）")
):
    """根据预定义模板初始化项目。"""
```

## 异常处理
- 若目录非空，抛出 `typer.Exit` 并提示用户。
- 若模板不存在，抛出 `typer.Exit` 并提示用户。
- 若初始化 `init` 失败，记录日志并通知用户。

## 验收标准
- [ ] 执行指令后当前目录下出现模板文件。
- [ ] 当前目录自动生成 `.ai-sync.json`。
- [ ] `CONTEXT.md` 包含模板来源记录。
- [ ] 目录非空时执行指令被拒绝。
