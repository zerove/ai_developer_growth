#!/bin/bash
# ai-dev-framework 安装脚本

set -e

FRAMEWORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-.}"
LANGUAGE="${2:-auto}"

echo "🚀 安装 ai-dev-framework"
echo "项目目录: $PROJECT_DIR"
echo "语言: $LANGUAGE"

# 创建框架目录
mkdir -p "$PROJECT_DIR/.ai-framework"

# 复制核心文件
cp -r "$FRAMEWORK_DIR/core/"* "$PROJECT_DIR/.ai-framework/"
cp -r "$FRAMEWORK_DIR/languages/"* "$PROJECT_DIR/.ai-framework/languages/"
cp -r "$FRAMEWORK_DIR/hooks/"* "$PROJECT_DIR/.ai-framework/hooks/"

# 检测语言
if [ "$LANGUAGE" = "auto" ]; then
    if [ -f "Cargo.toml" ]; then
        LANGUAGE="rust"
    elif [ -f "go.mod" ]; then
        LANGUAGE="go"
    elif [ -f "pom.xml" ] || [ -f "build.gradle" ]; then
        LANGUAGE="java"
    elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
        LANGUAGE="python"
    elif [ -f "package.json" ]; then
        LANGUAGE="typescript"
    else
        LANGUAGE="python"
    fi
    echo "检测到语言: $LANGUAGE"
fi

# 创建质量门禁脚本
cat > "$PROJECT_DIR/.ai-framework/quality-gates/scripts/check.sh" << 'EOF'
#!/bin/bash
# 质量门禁检查脚本

set -e

FRAMEWORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
LANGUAGE="${1:-auto}"

# 检测语言
if [ "$LANGUAGE" = "auto" ]; then
    if [ -f "Cargo.toml" ]; then
        LANGUAGE="rust"
    elif [ -f "go.mod" ]; then
        LANGUAGE="go"
    elif [ -f "pom.xml" ] || [ -f "build.gradle" ]; then
        LANGUAGE="java"
    elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
        LANGUAGE="python"
    elif [ -f "package.json" ]; then
        LANGUAGE="typescript"
    else
        LANGUAGE="python"
    fi
fi

echo "使用语言配置: $LANGUAGE"

# 执行语言特定检查
if [ -f "$FRAMEWORK_DIR/languages/$LANGUAGE/check.sh" ]; then
    bash "$FRAMEWORK_DIR/languages/$LANGUAGE/check.sh"
else
    echo "⚠️  未找到语言配置: $LANGUAGE"
    echo "请手动配置检查脚本"
fi
EOF
chmod +x "$PROJECT_DIR/.ai-framework/quality-gates/scripts/check.sh"

# 创建语言检测脚本
cat > "$PROJECT_DIR/.ai-framework/scripts/detect-language.sh" << 'EOF'
#!/bin/bash
# 语言检测脚本

if [ -f "Cargo.toml" ]; then
    echo "rust"
elif [ -f "go.mod" ]; then
    echo "go"
elif [ -f "pom.xml" ] || [ -f "build.gradle" ]; then
    echo "java"
elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
    echo "python"
elif [ -f "package.json" ]; then
    echo "typescript"
else
    echo "unknown"
fi
EOF
chmod +x "$PROJECT_DIR/.ai-framework/scripts/detect-language.sh"

# 创建上下文更新脚本
cat > "$PROJECT_DIR/.ai-framework/scripts/update-context.sh" << 'EOF'
#!/bin/bash
# 上下文更新脚本

echo "📝 更新项目上下文..."

# 检查 CONTEXT.md 是否存在
if [ ! -f "CONTEXT.md" ]; then
    echo "# 项目上下文" > CONTEXT.md
    echo "" >> CONTEXT.md
    echo "## 项目状态" >> CONTEXT.md
    echo "" >> CONTEXT.md
    echo "- 开发中" >> CONTEXT.md
    echo "" >> CONTEXT.md
    echo "## 下一步计划" >> CONTEXT.md
    echo "" >> CONTEXT.md
    echo "- 完成核心功能" >> CONTEXT.md
fi

echo "✅ 上下文更新完成"
EOF
chmod +x "$PROJECT_DIR/.ai-framework/scripts/update-context.sh"

# 创建 CLAUDE.md
cat > "$PROJECT_DIR/CLAUDE.md" << 'EOF'
# 项目规范

本项目遵循 ai-dev-framework 治理标准。

## 快速开始

1. 阅读 `.ai-framework/core/GOVERNANCE.md`
2. 使用 `.ai-framework/core/templates/agent-prompt.md` 创建 agent
3. 通过 4 道质量门禁

## 工具集成

- opencode: hooks 已配置
- jcode: hooks 已配置
- pre-commit: 已安装

## 语言特定规则

见 `.ai-framework/languages/` 目录
EOF

# 创建 AGENTS.md
cat > "$PROJECT_DIR/AGENTS.md" << 'EOF'
# Agent 定义索引

本项目中的所有 agent 定义。

---

*本文件随新增 Agent 时更新。*
EOF

# 创建 CONTEXT.md
cat > "$PROJECT_DIR/CONTEXT.md" << 'EOF'
# 项目上下文

## 项目状态

- 开发中

## 下一步计划

- 完成核心功能
EOF

echo ""
echo "✅ 安装完成!"
echo ""
echo "目录结构:"
echo "  $PROJECT_DIR/.ai-framework/  # 框架文件"
echo "  $PROJECT_DIR/CLAUDE.md       # 项目规范"
echo "  $PROJECT_DIR/AGENTS.md       # Agent 索引"
echo "  $PROJECT_DIR/CONTEXT.md      # 项目上下文"
echo ""
echo "下一步:"
echo "  1. 阅读 .ai-framework/core/GOVERNANCE.md"
echo "  2. 使用 .ai-framework/core/templates/agent-prompt.md 创建 agent"
echo "  3. 通过 4 道质量门禁"
