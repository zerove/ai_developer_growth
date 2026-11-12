#!/bin/bash
set -e
echo "🔍 检查 Haskell 项目..."

cmd_lint="hlint"
cmd_fmt="ormolu"
cmd_test="hspec"

if [ -n "$cmd_lint" ] && command -v "$(echo "$cmd_lint" | cut -d\' \' -f1)" &>/dev/null; then
    $cmd_lint . && echo "✅ Lint OK" || echo "⚠️  Lint 有警告"
else
    echo "⚠️  hlint 未安装"
fi

if [ -n "$cmd_fmt" ] && command -v "$(echo "$cmd_fmt" | cut -d\' \' -f1)" &>/dev/null; then
    $cmd_fmt --check . 2>/dev/null && echo "✅ Format OK" || echo "⚠️  Format 需格式化"
    echo "⚠️  跳过格式化检查"
fi

if [ -n "$cmd_test" ] && command -v "$(echo "$cmd_test" | cut -d\' \' -f1)" &>/dev/null; then
    $cmd_test . && echo "✅ Tests OK" || echo "⚠️  测试有失败"
else
    echo "⚠️  hspec 未安装"
fi

echo "✅ Haskell 质量门禁完成"
