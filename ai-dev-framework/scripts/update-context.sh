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
