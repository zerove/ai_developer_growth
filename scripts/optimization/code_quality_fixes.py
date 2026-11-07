"""
代码质量修复工具 - 实现Phase 1的推荐修复

此脚本实现以下修复:
1. 提取重复的代码方法到共享模块
2. 实现日志安全脱敏
3. 迁移敏感配置到环境变量
"""

import argparse
import json
import os
import re
from pathlib import Path


# 配置安全模块
class ConfigSecurityManager:
    def __init__(self, config_file: str = ".jcode/hooks.json"):
        self.config_file = Path(config_file)
        self.env_prefix = "ADG_"

    def migrate_sensitive_config(self) -> dict[str, str]:
        """将敏感配置迁移到环境变量"""
        if not self.config_file.exists():
            return {}

        with open(self.config_file, encoding="utf-8") as f:
            config = json.load(f)

        env_updates = {}
        sensitive_keys = ["api_key", "secret", "password", "token", "webhook"]

        for key, value in config.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                env_var = f"{self.env_prefix}{key.upper()}"
                os.environ[env_var] = str(value)
                env_updates[env_var] = "***"
                print(f"✅ 已迁移敏感配置: {key} -> {env_var}")

        # 更新配置文件，移除敏感值
        sanitized_config = self._sanitize_config(config, sensitive_keys)

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(sanitized_config, f, indent=2, ensure_ascii=False)

        return env_updates

    def _sanitize_config(self, config: dict, sensitive_keys: list[str]) -> dict:
        """清理配置文件中的敏感信息"""
        sanitized = config.copy()
        for key in sanitized:
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
        return sanitized


# 日志安全脱敏模块
class LogSanitizer:
    def __init__(self):
        self.patterns = [
            (r"api_key=[^&\s]+", "api_key=***"),
            (r"secret=[^&\s]+", "secret=***"),
            (r"password=[^&\s]+", "password=***"),
            (r"token=[^&\s]+", "token=***"),
            (r"Authorization: Bearer [^\s]+", "Authorization: Bearer ***"),
        ]

    def sanitize_log_message(self, message: str) -> str:
        """对日志消息进行脱敏处理"""
        sanitized = message
        for pattern, replacement in self.patterns:
            sanitized = re.sub(pattern, replacement, sanitized)
        return sanitized

    def sanitize_log_file(self, log_file: str, backup: bool = True):
        """对整个日志文件进行脱敏处理"""
        log_path = Path(log_file)
        if not log_path.exists():
            print(f"❌ 日志文件不存在: {log_file}")
            return

        content = log_path.read_text(encoding="utf-8")
        original_content = content

        sanitized = self.sanitize_log_message(content)

        if backup:
            backup_path = log_path.with_suffix(f".backup{log_path.suffix}")
            log_path.write_text(original_content, encoding="utf-8")
            backup_path.write_text(sanitized, encoding="utf-8")
            print(f"✅ 已备份原始日志到: {backup_path}")
        else:
            log_path.write_text(sanitized, encoding="utf-8")

        print(f"✅ 已完成日志脱敏处理: {log_file}")


# 代码重复提取模块
class DuplicateCodeExtractor:
    def __init__(self, source_dir: str = "."):
        self.source_dir = Path(source_dir)
        self.common_utils_dir = Path("tools/scripts/_common.py")

    def analyze_duplicate_patterns(self) -> dict[str, list[str]]:
        """分析代码中的重复模式"""
        duplicates = {}

        # 查找重复的检查方法
        check_methods = []
        for py_file in self.source_dir.rglob("*.py"):
            if "__pycache__" in str(py_file) or ".venv" in str(py_file):
                continue

            content = py_file.read_text(encoding="utf-8")
            # 查找重复的检查函数模式
            if "def _check_" in content:
                check_methods.append(str(py_file))

        duplicates["check_functions"] = check_methods
        return duplicates

    def extract_common_functions(self) -> list[str]:
        """提取通用函数到共享模块"""
        if not self.common_utils_dir.exists():
            self.common_utils_dir.write_text(
                '''"""通用工具函数 - 自动提取的重复代码"""

import os
import re
import sys
from pathlib import Path
from typing import Any, List, Dict
import logging

def run_command(command: str, cwd: str = None) -> Tuple[int, str, str]:
    """执行外部命令"""
    import subprocess
    try:
        result = subprocess.run(
            command, shell=True, cwd=cwd,
            capture_output=True, text=True, encoding='utf-8'
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def print_check(message: str, status: str = "INFO"):
    """格式化输出检查结果"""
    symbols = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "INFO": "ℹ️"}
    symbol = symbols.get(status.upper(), "ℹ️")
    print(f"{symbol} {message}")

def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent.parent
''',
                ignore_existing=True,
            )

        return [str(self.common_utils_dir)]


def main():
    """主函数 - 执行所有代码质量修复"""
    parser = argparse.ArgumentParser(description="代码质量修复工具")
    parser.add_argument("--check-only", action="store_true", help="只检查，不修改")
    parser.add_argument("--backup", action="store_true", help="创建备份")

    args = parser.parse_args()

    print("🔧 开始代码质量修复...")

    # 1. 配置安全修复
    print("\n📋 步骤1: 配置安全修复")
    config_manager = ConfigSecurityManager()
    if args.check_only:
        print("📋 配置中发现的敏感配置:")
        # 检查但不修改
        if config_manager.config_file.exists():
            with open(config_manager.config_file, encoding="utf-8") as f:
                config = json.load(f)
            for key, value in config.items():
                if any(sensitive in key.lower() for sensitive in ["api_key", "secret", "password", "token", "webhook"]):
                    print(f"   🔒 {key}: {type(value).__name__}")
    else:
        config_updates = config_manager.migrate_sensitive_config()
        print(f"📋 已迁移 {len(config_updates)} 个敏感配置到环境变量")

    # 2. 日志安全修复
    print("\n📋 步骤2: 日志安全修复")
    log_sanitizer = LogSanitizer()

    log_files = [".adg-hook.log", ".log", "logs/debug.log", "logs/error.log"]

    for log_file in log_files:
        log_path = Path(log_file)
        if log_path.exists():
            if args.check_only:
                print(f"📋 将处理日志文件: {log_file}")
                content = log_path.read_text(encoding="utf-8")
                sample = content[:500] if len(content) > 500 else content
                print(f"   📄 样本内容: {sample}...")
            else:
                log_sanitizer.sanitize_log_file(log_file, backup=args.backup)

    # 3. 代码重复提取
    print("\n📋 步骤3: 代码重复提取")
    extractor = DuplicateCodeExtractor()

    if args.check_only:
        duplicates = extractor.analyze_duplicate_patterns()
        for category, files in duplicates.items():
            print(f"📋 发现 {len(files)} 个重复的 {category}")
            for file in files:
                print(f"   📄 {file}")
    else:
        common_files = extractor.extract_common_functions()
        print(f"📋 已提取 {len(common_files)} 个通用函数到共享模块")

    print("\n✅ 代码质量修复完成！")


if __name__ == "__main__":
    main()
