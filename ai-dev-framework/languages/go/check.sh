#!/bin/bash
# Go 质量门禁脚本

set -e

echo "🔍 检查 Go 项目..."

# 1. Lint 检查
echo "=== Lint 检查 ==="
if command -v golangci-lint &> /dev/null; then
    if golangci-lint run; then
        echo "✅ Lint 检查通过"
    else
        echo "❌ Lint 检查失败"
        exit 1
    fi
else
    echo "⚠️  golangci-lint 未安装，跳过检查"
fi

# 2. 测试检查
echo "=== 测试检查 ==="
if command -v go &> /dev/null; then
    if go test ./...; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  go 未安装，跳过检查"
fi

# 3. 格式检查
echo "=== 格式检查 ==="
if command -v go &> /dev/null; then
    if gofmt -l . | grep -q .; then
        echo "⚠️  格式检查有警告"
        gofmt -l .
    else
        echo "✅ 格式检查通过"
    fi
else
    echo "⚠️  go 未安装，跳过检查"
fi

# 4. 安全检查
echo "=== 安全检查 ==="
if command -v govulncheck &> /dev/null; then
    if govulncheck ./...; then
        echo "✅ 安全检查通过"
    else
        echo "⚠️  安全检查有警告"
    fi
else
    echo "⚠️  govulncheck 未安装，跳过检查"
fi

echo "✅ Go 质量门禁检查完成"
