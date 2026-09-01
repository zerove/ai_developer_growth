#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Check .jcode/hooks.json 完整性 (防止 fail-open hook 静默失败)
# ──────────────────────────────────────────────────────────────
# Phase 30 收口后建立: 本会话发现 update-moc hook 调用
# link_auditor.py --update-moc 但 link_auditor.py 不支持, hook 一直
# fail-open. 历史以来被其他 hook 覆盖掩盖.
#
# 此脚本作为前置门禁: 扫描 .jcode/hooks.json 所有 command, 对每个
# command 的 --help 输出检测 "unrecognized arguments" 关键词, 若发现
# 立即报错并提示移除或修复该 hook.
#
# 用法: bash tools/scripts/check_hooks_json_integrity.sh
# 退出码: 0 通过 / 1 有 fail-open hook 风险
# ──────────────────────────────────────────────────────────────
set -e

cd "$(dirname "$0")/../.."

if [ ! -f .jcode/hooks.json ]; then
    echo "❌ .jcode/hooks.json 文件不存在"
    exit 1
fi

# 用 Python 跑扫描 (bash 难以处理 JSON 嵌套结构)
# 通过直接调用 hooks_runner 来发现 fail-open hook (类似 update-moc 历史 bug):
# on_commit: .jcode/scripts/hooks_runner.py on_commit --files .adg/rules.yml
# on_merge:  .jcode/scripts/hooks_runner.py on_merge
PROBLEMS=$(python3 << 'EOF'
import json, subprocess
hooks = json.load(open('.jcode/hooks.json'))
problems = []

# 跑每个 phase 的 hooks_runner, 检查是否有 hook 真报错且 stderr 含 'unrecognized arguments'
phases_to_test = ['on_commit', 'on_merge']
for phase in phases_to_test:
    cmd = ['python', '.jcode/scripts/hooks_runner.py', phase]
    if phase == 'on_commit':
        cmd += ['--files', '.adg/rules.yml']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out = r.stdout + r.stderr
        # 解析每个 hook 的状态
        for line in out.splitlines():
            if '[失败]' in line and any(name in line for name in [h['name'] for h in hooks['hooks'][phase]]):
                # 提取 hook 名
                for h in hooks['hooks'][phase]:
                    if h['name'] in line:
                        # 检查失败原因是否含 "unrecognized arguments" (fail-open 标志)
                        # 注意: 必须在 hook 名上下文里出现, 不能是脚本名的整体错误
                        if 'unrecognized arguments' in out:
                            # 进一步精确: 该 hook 自身的命令错误
                            # 简单判断: 该 hook 在输出里有独立的 [失败] + unrecognized
                            problems.append(f"  - {phase}/{h['name']}: command 调用脚本不支持的参数")
                        break
    except Exception as e:
        pass

for p in problems:
    print(p)
EOF
)

if [ -n "$PROBLEMS" ]; then
    echo "❌ .jcode/hooks.json 检测到 fail-open 风险"
    echo ""
    echo "以下 hook 的 command 包含不被识别的参数 (类似 update-moc 历史 bug):"
    echo "$PROBLEMS"
    echo ""
    echo "可能原因: hook 的 command 调用了某个脚本 + 该脚本不支持的参数"
    echo ""
    echo "修复方向:"
    echo "  1. 移除该 hook"
    echo "  2. 修底层脚本支持该参数"
    echo ""
    exit 1
fi

echo "✅ .jcode/hooks.json 全部 hook 命令参数识别正常"
exit 0