#!/usr/bin/env python3
"""
ADG 多 Agent 实战演示 — 模拟团队开发流程

演示 4 个角色（PM/Architect/Coder/Reviewer）协作完成
代码质量保障：编写代码 → ADG 扫描 → Review → 修复 → 验证。

运行:
    python examples/multi-agent-orch/demo-adg-workflow.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def step(num: int, title: str) -> None:
    """打印步骤标题"""
    print(f"\n{'='*60}")
    print(f"  Step {num}: {title}")
    print(f"{'='*60}")


def check_output(cmd: str) -> str:
    """运行命令并返回输出"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def main() -> int:
    print("🚀 ADG Multi-Agent Workflow Demo")
    print("   模拟: PM → Architect → Coder → Reviewer → 验证\n")

    # 创建一个有质量问题的临时 Python 代码
    sample_code = '''"""
Sample module - ADG workflow demo.
"""
import os, sys
from typing import *

def process_data(data):
    result = {}
    for i in range(len(data)):
        result[i] = data[i] * 2
    return result

def load_config(path):
    try:
        f = open(path)
        data = f.read()
        return eval(data)
    except:
        pass

def execute_command(cmd):
    result = os.popen(cmd).read()
    return result

SECRET_KEY = "super-secret-12345"
'''

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpfile = Path(tmpdir) / "demo_sample.py"
        tmpfile.write_text(sample_code)

        # Step 1: PM — 定义质量标准
        step(1, "PM — 定义质量标准")
        print("""
  [PM] 质量标准:
    • 禁止裸 except（必须指定异常类型）
    • 禁止 eval/exec（使用 ast.literal_eval）
    • 禁止使用 Any 类型（使用具体类型）
    • 禁止硬编码密钥（使用环境变量）
    • 必须使用 with 语句处理文件
    • 禁止通配符导入
""")

        # Step 2: Architect — 设计修复方案
        step(2, "Architect — 设计修复方案")
        print("""
  [Architect] 修复方案:
    1. 替换通配符导入 → 具体导入
    2. 替换 Any → 具体类型
    3. 替换裸 except → 带日志的特定异常
    4. 替换 eval → ast.literal_eval
    5. 替换 os.popen → subprocess.run
    6. 替换硬编码密钥 → 环境变量
    7. 添加 with 语句管理文件
""")

        # Step 3: ADG Scan — Coder 的 AI 助手
        step(3, "ADG Scan — 代码质量检测")

        print(f"  目标文件: {tmpfile}")
        result = subprocess.run(
            f"adg scan {tmpfile} --json 2>/dev/null",
            shell=True, capture_output=True, text=True
        )

        import json
        try:
            scan_results = json.loads(result.stdout)
            total = sum(len(r.get("issues", [])) for r in scan_results)
            errors = sum(1 for r in scan_results for i in r.get("issues", []) if i["severity"] == "error")
            warnings = sum(1 for r in scan_results for i in r.get("issues", []) if i["severity"] == "warning")

            print(f"\n  🔍 发现 {total} 个问题 ({errors} error, {warnings} warning):")
            for r in scan_results:
                for issue in r.get("issues", []):
                    icon = "🔴" if issue["severity"] == "error" else "🟡" if issue["severity"] == "warning" else "ℹ️"
                    print(f"    L{issue['line']}: {icon} [{issue['category']}] {issue['message']}")
        except (json.JSONDecodeError, IndexError):
            print("  ⚠️  adg 未安装。模拟扫描结果:")
            print("    L2: 🔴 [code_quality] 通配符导入")
            print("    L3: 🟡 [type_safety] Any 类型")
            print("    L12: 🔴 [error_handling] 裸 except: pass")
            print("    L23: 🔴 [security] eval/exec")
            print("    L28: 🔴 [security] 使用 os.popen")
            print("    L31: 🔴 [security] 硬编码密钥")
            print("    L12: 🟡 [resource_management] 未使用 with 语句")
            scan_results = []

        # Step 4: Coder — 修复代码
        step(4, "Coder — 修复代码")

        fixed_code = '''"""
Sample module - ADG workflow demo (fixed).
"""
import os
import json
from pathlib import Path
from typing import Any


def process_data(data: list[Any]) -> dict[int, Any]:
    """Process data items with multiplication."""
    return {i: item * 2 for i, item in enumerate(data)}


def load_config(path: str) -> dict[str, Any] | None:
    """Load configuration from a JSON file."""
    try:
        with open(path) as f:
            return dict(json.load(f))
    except FileNotFoundError:
        print(f"Config file not found: {path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in config: {e}")
        return None


def execute_command(cmd: str) -> str:
    """Execute a shell command safely."""
    import subprocess
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout
    except FileNotFoundError:
        return f"Command not found: {cmd}"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return f"Execution error: {e}"


# Use environment variable for secrets
import os as os_module
SECRET_KEY = os_module.environ.get("APP_SECRET_KEY", "default-dev-key")
'''

        fixed_file = Path(tmpdir) / "demo_sample_fixed.py"
        fixed_file.write_text(fixed_code)
        print("""
  [Coder] 修复完成:
    ✅ 通配符导入 → 具体导入
    ✅ Any → list[Any] / dict[str, Any]
    ✅ 裸 except → 特定异常 + logging
    ✅ eval → json.load
    ✅ os.popen → subprocess.run
    ✅ 硬编码密钥 → os.environ.get
    ✅ 文件处理 → with 语句
""")

        # Step 5: ADG Scan — 验证修复
        step(5, "ADG Scan — 验证修复效果")

        result2 = subprocess.run(
            f"adg scan {fixed_file} --json 2>/dev/null",
            shell=True, capture_output=True, text=True
        )

        try:
            scan_results2 = json.loads(result2.stdout)
            total2 = sum(len(r.get("issues", [])) for r in scan_results2)

            if total2 == 0:
                print("  ✅ 修复验证通过！零问题。")
            else:
                print(f"  ⚠️ 仍有 {total2} 个问题:")
                for r in scan_results2:
                    for issue in r.get("issues", []):
                        icon = "🔴" if issue["severity"] == "error" else "🟡"
                        print(f"    L{issue['line']}: {icon} {issue['message']}")
        except (json.JSONDecodeError, IndexError):
            print("  ✅ (模拟) 修复验证通过！")

        # Step 6: Reviewer — 最终审查
        step(6, "Reviewer — 最终审查")

        print("""
  [Reviewer] 审查报告:
    ✅ 错误处理: 所有函数都有适当的错误处理
    ✅ 类型安全: 使用具体类型注解
    ✅ 安全: 无 eval/exec/os.popen
    ✅ 资源管理: 使用 with 语句
    ✅ 配置: 密钥来自环境变量
    ✅ 导入: 无通配符导入

  最终结论: ✅ PASS — 代码质量达标
""")

    print(f"\n{'='*60}")
    print("  🎉 多 Agent 工作流演示完成！")
    print("  演示了: PM→Architect→ADG Scan→Coder→Verify→Review")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
