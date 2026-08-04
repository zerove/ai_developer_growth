#!/bin/bash
# Ruby 质量门禁脚本

set -e

echo "🔍 检查 Ruby 项目..."

# 1. RuboCop 检查
echo "=== RuboCop 检查 ==="
if command -v rubocop &> /dev/null; then
    if rubocop; then
        echo "✅ RuboCop 检查通过"
    else
        echo "❌ RuboCop 检查失败"
        exit 1
    fi
else
    echo "⚠️  RuboCop 未安装，跳过检查"
fi

# 2. 测试检查
echo "=== 测试检查 ==="
if command -v rspec &> /dev/null; then
    if rspec; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
elif command -v bundle &> /dev/null; then
    if bundle exec rspec; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  RSpec 未安装，跳过检查"
fi

# 3. 安全检查
echo "=== 安全检查 ==="
if command -v bundle-audit &> /dev/null; then
    if bundle-audit check --update; then
        echo "✅ 安全检查通过"
    else
        echo "⚠️  安全检查有警告"
    fi
else
    echo "⚠️  bundle-audit 未安装，跳过检查"
fi

echo "✅ Ruby 质量门禁检查完成"
