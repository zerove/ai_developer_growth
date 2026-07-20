#!/bin/bash
# TypeScript 质量门禁脚本

set -e

echo "🔍 检查 TypeScript 项目..."

# 1. Lint 检查
echo "=== Lint 检查 ==="
if command -v eslint &> /dev/null; then
    if eslint . --ext .ts,.tsx; then
        echo "✅ Lint 检查通过"
    else
        echo "❌ Lint 检查失败"
        exit 1
    fi
else
    echo "⚠️  eslint 未安装，跳过检查"
fi

# 2. 类型检查
echo "=== 类型检查 ==="
if command -v tsc &> /dev/null; then
    if tsc --noEmit; then
        echo "✅ 类型检查通过"
    else
        echo "❌ 类型检查失败"
        exit 1
    fi
else
    echo "⚠️  tsc 未安装，跳过检查"
fi

# 3. 测试检查
echo "=== 测试检查 ==="
if command -v jest &> /dev/null; then
    if jest --passWithNoTests; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
elif command -v vitest &> /dev/null; then
    if vitest run; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  jest/vitest 未安装，跳过检查"
fi

# 4. 安全检查
echo "=== 安全检查 ==="
if command -v npm &> /dev/null; then
    if npm audit --audit-level=high; then
        echo "✅ 安全检查通过"
    else
        echo "⚠️  安全检查有警告"
    fi
else
    echo "⚠️  npm 未安装，跳过检查"
fi

echo "✅ TypeScript 质量门禁检查完成"
