#!/bin/bash
# C# 质量门禁脚本

set -e

echo "🔍 检查 C# 项目..."

# 1. dotnet 格式检查
echo "=== dotnet format 检查 ==="
if command -v dotnet &>/dev/null; then
    if dotnet format --verify-no-changes; then
        echo "✅ dotnet format 检查通过"
    else
        echo "❌ dotnet format 检查失败"
        exit 1
    fi
else
    echo "⚠️  dotnet 未安装，跳过检查"
fi

# 2. 测试检查
echo "=== 测试检查 ==="
if command -v dotnet &>/dev/null; then
    if dotnet test; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  dotnet 未安装，跳过检查"
fi

# 3. 编译检查
echo "=== 编译检查 ==="
if command -v dotnet &>/dev/null; then
    if dotnet build --no-restore; then
        echo "✅ 编译检查通过"
    else
        echo "❌ 编译检查失败"
        exit 1
    fi
else
    echo "⚠️  dotnet 未安装，跳过检查"
fi

# 4. 安全检查
echo "=== 安全检查 ==="
if command -v dotnet &>/dev/null; then
    if dotnet list package --vulnerable; then
        echo "✅ 安全检查通过"
    else
        echo "⚠️  安全检查有警告"
    fi
else
    echo "⚠️  dotnet 未安装，跳过检查"
fi

echo "✅ C# 质量门禁检查完成"
