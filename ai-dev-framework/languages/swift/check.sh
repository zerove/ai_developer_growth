#!/bin/bash
# Swift 质量门禁脚本

set -e

echo "🔍 检查 Swift 项目..."

# 1. SwiftLint 检查
echo "=== SwiftLint 检查 ==="
if command -v swiftlint &>/dev/null; then
    if swiftlint; then
        echo "✅ SwiftLint 检查通过"
    else
        echo "❌ SwiftLint 检查失败"
        exit 1
    fi
else
    echo "⚠️  SwiftLint 未安装，跳过检查"
fi

# 2. 测试检查
echo "=== 测试检查 ==="
if command -v xcodebuild &>/dev/null; then
    if xcodebuild test -scheme App -destination 'platform=iOS Simulator,name=iPhone 15' -quiet; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
elif command -v swift &>/dev/null; then
    if swift test; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  Swift 未安装，跳过检查"
fi

# 3. 格式检查
echo "=== 格式检查 ==="
if command -v swift-format &>/dev/null; then
    if swift-format lint .; then
        echo "✅ 格式检查通过"
    else
        echo "⚠️  格式检查有警告"
    fi
else
    echo "⚠️  swift-format 未安装，跳过检查"
fi

echo "✅ Swift 质量门禁检查完成"
