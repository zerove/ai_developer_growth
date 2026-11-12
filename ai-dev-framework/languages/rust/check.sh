#!/bin/bash
# Rust 质量门禁脚本

set -e

echo "🔍 检查 Rust 项目..."

# 1. Clippy 检查
echo "=== Clippy 检查 ==="
if command -v cargo &>/dev/null; then
    if cargo clippy -- -D warnings; then
        echo "✅ Clippy 检查通过"
    else
        echo "❌ Clippy 检查失败"
        exit 1
    fi
else
    echo "⚠️  cargo 未安装，跳过检查"
fi

# 2. 测试检查
echo "=== 测试检查 ==="
if command -v cargo &>/dev/null; then
    if cargo test; then
        echo "✅ 测试通过"
    else
        echo "❌ 测试失败"
        exit 1
    fi
else
    echo "⚠️  cargo 未安装，跳过检查"
fi

# 3. 格式检查
echo "=== 格式检查 ==="
if command -v cargo &>/dev/null; then
    if cargo fmt -- --check; then
        echo "✅ 格式检查通过"
    else
        echo "⚠️  格式检查有警告"
    fi
else
    echo "⚠️  cargo 未安装，跳过检查"
fi

# 4. 安全检查
echo "=== 安全检查 ==="
if command -v cargo-audit &>/dev/null; then
    if cargo audit; then
        echo "✅ 安全检查通过"
    else
        echo "⚠️  安全检查有警告"
    fi
else
    echo "⚠️  cargo-audit 未安装，跳过检查"
fi

echo "✅ Rust 质量门禁检查完成"
