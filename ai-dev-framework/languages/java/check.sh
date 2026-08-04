#!/bin/bash
# Java 质量门禁脚本

set -e

echo "🔍 检查 Java 项目..."

# 1. 编译检查
echo "=== 编译检查 ==="
if command -v mvn &> /dev/null; then
    if mvn compile -q; then
        echo "✅ 编译通过"
    else
        echo "❌ 编译失败"
        exit 1
    fi
elif command -v gradle &> /dev/null; then
    if gradle compileJava -q; then
        echo "✅ 编译通过"
    else
        echo "❌ 编译失败"
        exit 1
    fi
else
    echo "⚠️  Maven/Gradle 未安装，跳过检查"
fi

# 2. 测试检查
echo "=== 测试检查 ==="
if command -v mvn &> /dev/null; then
    if mvn test -q; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
elif command -v gradle &> /dev/null; then
    if gradle test -q; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  Maven/Gradle 未安装，跳过检查"
fi

# 3. 代码质量检查
echo "=== 代码质量检查 ==="
if command -v mvn &> /dev/null; then
    if mvn checkstyle:check -q 2>/dev/null; then
        echo "✅ 代码质量检查通过"
    else
        echo "⚠️  代码质量检查有警告"
    fi
elif command -v gradle &> /dev/null; then
    if gradle checkstyleMain -q 2>/dev/null; then
        echo "✅ 代码质量检查通过"
    else
        echo "⚠️  代码质量检查有警告"
    fi
else
    echo "⚠️  Maven/Gradle 未安装，跳过检查"
fi

echo "✅ Java 质量门禁检查完成"
