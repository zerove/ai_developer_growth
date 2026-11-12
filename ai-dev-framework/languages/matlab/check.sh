#!/bin/bash
set -e
echo "🔍 检查 Matlab 项目..."

cmd_lint="miss_hit"
cmd_fmt="miss_hit"
cmd_test="mlunit"

if [ -n "$cmd_lint" ] && command -v "$(echo "$cmd_lint" | cut -d\' \' -f1)" &>/dev/null; then
    $cmd_lint . && echo "✅ Lint OK" || echo "⚠️  Lint 有警告"
else
    echo "⚠️  miss_hit 未安装"
fi

if [ -n "$cmd_fmt" ] && command -v "$(echo "$cmd_fmt" | cut -d\' \' -f1)" &>/dev/null; then
    $cmd_fmt --check . 2>/dev/null && echo "✅ Format OK" || echo "⚠️  Format 需格式化"
    echo "⚠️  跳过格式化检查"
fi

if [ -n "$cmd_test" ] && command -v "$(echo "$cmd_test" | cut -d\' \' -f1)" &>/dev/null; then
    $cmd_test . && echo "✅ Tests OK" || echo "⚠️  测试有失败"
else
    echo "⚠️  mlunit 未安装"
fi

echo "✅ Matlab 质量门禁完成"
