#!/bin/bash
# Kotlin 质量门禁脚本

set -e

echo "🔍 检查 Kotlin 项目..."

# 1. ktlint 检查
echo "=== ktlint 检查 ==="
if command -v ktlint &>/dev/null; then
    if ktlint; then
        echo "✅ ktlint 检查通过"
    else
        echo "❌ ktlint 检查失败"
        exit 1
    fi
else
    echo "⚠️  ktlint 未安装，跳过检查"
fi

# 2. 测试检查
echo "=== 测试检查 ==="
if command -v gradle &>/dev/null; then
    if gradle test -q; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
elif command -v mvn &>/dev/null; then
    if mvn test -q; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  Gradle/Maven 未安装，跳过检查"
fi

# 3. 安全检查
echo "=== 安全检查 ==="
if command -v detekt &>/dev/null; then
    if detekt; then
        echo "✅ 安全检查通过"
    else
        echo "⚠️  安全检查有警告"
    fi
else
    echo "⚠️  detekt 未安装，跳过检查"
fi

echo "✅ Kotlin 质量门禁检查完成"
