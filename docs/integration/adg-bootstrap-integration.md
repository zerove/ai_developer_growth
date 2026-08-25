# ADG Bootstrap：把治理能力移植到任意项目

> 一条命令，把本项目的质量门禁、hook 流程、多语言规则引擎装进你的其他项目。

## 快速开始

在本项目（源）根目录执行：

```bash
# 自动探测目标语言
python tools/scripts/adg_bootstrap.py /path/to/your-project

# 显式指定语言组合
python tools/scripts/adg_bootstrap.py /path/to/your-project --langs go,typescript

# 最小安装（仅核心脚本 + 公共规则）
python tools/scripts/adg_bootstrap.py /path/to/your-project --minimal
```

## 移植产物清单

| 产物 | 作用 |
|------|------|
| `.jcode/hooks.json` | 统一 hook 运行器配置（`--lang` 参数按目标主语言自动改写） |
| `.jcode/scripts/` | governance-auditor、context-sync、hooks_runner 等治理脚本 |
| `tools/scripts/` | 运行时依赖（_common、language_registry、app_config）+ adg_cli + rules_engine |
| `.adg/framework/` | ai-dev-framework 规则集（common/domains/frameworks + 所选语言规则） |
| `.pre-commit-config.yaml` | 质量门禁钩子（Python 项目自动启用 ruff） |
| `pyproject.toml [tool.adg]` | exclude 排除治理设施自身，防止自扫误报 |
| `.adg/requirements.txt` | 目标项目的 Python 依赖清单 |
| `AGENTS.md` | 注入使用说明与提交规范（幂等，不覆盖已有内容） |

## 目标项目内启用

```bash
pip install -r .adg/requirements.txt
pip install pre-commit && pre-commit install

# 质量检查
python -m tools.scripts.adg_cli check . --lang <主语言>

# 语言/框架探测
python -m tools.scripts.adg_cli detect

# Hook 流程
python .jcode/scripts/hooks_runner.py lint
```

## 支持的语言

python · go · rust · java · typescript · javascript · kotlin · csharp · ruby · php · swift · cpp

分层违规检测、AST 深度分析（tree-sitter）、依赖解析（9 个生态）、
源码注释知识索引等能力的语言覆盖矩阵见 `docs/guides/multi-language-guide.md`。

## 设计说明

- **幂等**：重复执行不会重复注入 AGENTS.md；已有 `[tool.adg]` 配置不覆盖。
- **安全**：拒绝把治理装到源项目自身；未知语言显式报错。
- **同源排除**：adg_cli 与 rules_engine 共享 `[tool.adg].exclude` 配置，
  在目标项目新增目录时一处配置即可全局生效。
- **独立运行**：目标项目无需克隆本项目；所有脚本按相对路径自举。


## v2.4.0 发布状态 (2026-08-25)

- 标签 `v2.4.0` 已指向 442f182 并强推远端（修正旧 tag 指向历史提交的问题）
- release.yml 触发正常，但 GitHub Actions 因账户 Billing 阻塞无法启动 job（非代码问题）
- Billing 恢复后：`gh run rerun` 或删标签重推即可完成正式发布
- 本地闭环已验证：`pip wheel ai-dev-framework/` 构建 OK（24945 字节）


### Billing 恢复前的本地预演 (2026-08-25 补)

validate job 全部 8 步已在本地同命令预演通过：

| 步骤 | 结果 |
|---|---|
| ruff check / format --check | PASS |
| mypy strict | PASS |
| hooks_runner doctor / baseline validate | PASS |
| coverage 阈值 | 85.3% ≥ 60% |
| ADG governance error=0 | PASS |
| 版本一致 (tag=pyproject=2.4.0) + CHANGELOG 条目 | PASS |
| python -m build + twine check | PASSED ×2 |

另发现并修复 workflow 真实 bug：changelog 提取区间匹配恒为空（a3879e1），
tag 已同步指向该修复。Billing 恢复后 rerun 即可完成发布。
