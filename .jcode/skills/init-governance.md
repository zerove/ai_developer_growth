# init-governance Skill

一键初始化当前项目的 ADG 治理配置。安装预提交钩子、规则文件。

## Usage

```
/init-governance
```

在任意项目根目录运行一次即可。

## What it does

1. 创建 `.jcode/config.yml` — 项目中文配置
2. 创建 `.jcode/hooks.json` — 提交/PR 自动检查触发器
3. 创建 `.pre-commit-config.yaml` — git 提交前检查
4. 提示安装 pre-commit 钩子

## Requirements

- 全局已安装（一次）：`python ~/.jcode/governance/ai-dev-framework/../scripts/install-governance.py`
- 或本项目 `ai-dev-framework/` 在本地存在

## Implementation

This skill runs:

```bash
python scripts/install-governance.py --path .
```
