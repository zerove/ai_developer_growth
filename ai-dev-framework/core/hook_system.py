"""
Jcode Hooks - 通用钩子系统

适用于任何项目的自动化触发器。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable


@dataclass
class Hook:
    """钩子定义"""
    name: str
    agent: str
    action: str
    description: str
    enabled: bool = True
    condition: Optional[str] = None


@dataclass
class HookConfig:
    """钩子配置"""
    version: str = "1.0"
    on_commit: list[Hook] = field(default_factory=list)
    on_pr: list[Hook] = field(default_factory=list)
    on_merge: list[Hook] = field(default_factory=list)
    scheduled: list[Hook] = field(default_factory=list)

    @classmethod
    def load(cls, config_path: str) -> "HookConfig":
        """从文件加载配置"""
        with open(config_path) as f:
            data = json.load(f)

        config = cls(version=data.get("version", "1.0"))

        for hook_data in data.get("hooks", {}).get("on_commit", []):
            config.on_commit.append(Hook(**hook_data))

        for hook_data in data.get("hooks", {}).get("on_pr", []):
            config.on_pr.append(Hook(**hook_data))

        for hook_data in data.get("hooks", {}).get("on_merge", []):
            config.on_merge.append(Hook(**hook_data))

        for hook_data in data.get("hooks", {}).get("scheduled", []):
            # scheduled hooks use 'schedule' instead of 'condition'
            if "schedule" in hook_data:
                hook_data["condition"] = hook_data.pop("schedule")
            config.scheduled.append(Hook(**hook_data))

        return config

    def save(self, config_path: str) -> None:
        """保存配置到文件"""
        data = {
            "version": self.version,
            "hooks": {
                "on_commit": [
                    {
                        "name": h.name,
                        "agent": h.agent,
                        "action": h.action,
                        "description": h.description,
                        "enabled": h.enabled,
                        "condition": h.condition,
                    }
                    for h in self.on_commit
                ],
                "on_pr": [
                    {
                        "name": h.name,
                        "agent": h.agent,
                        "action": h.action,
                        "description": h.description,
                        "enabled": h.enabled,
                        "condition": h.condition,
                    }
                    for h in self.on_pr
                ],
                "on_merge": [
                    {
                        "name": h.name,
                        "agent": h.agent,
                        "action": h.action,
                        "description": h.description,
                        "enabled": h.enabled,
                        "condition": h.condition,
                    }
                    for h in self.on_merge
                ],
                "scheduled": [
                    {
                        "name": h.name,
                        "agent": h.agent,
                        "action": h.action,
                        "description": h.description,
                        "enabled": h.enabled,
                        "schedule": h.condition,
                    }
                    for h in self.scheduled
                ],
            },
        }

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_enabled_hooks(self, event: str) -> list[Hook]:
        """获取指定事件的启用钩子"""
        hooks_map = {
            "commit": self.on_commit,
            "pr": self.on_pr,
            "merge": self.on_merge,
            "scheduled": self.scheduled,
        }
        hooks = hooks_map.get(event, [])
        return [h for h in hooks if h.enabled]


def create_default_config(project_type: str = "generic") -> HookConfig:
    """
    创建默认钩子配置

    Args:
        project_type: 项目类型 (generic, python, typescript, rust, go)

    Returns:
        HookConfig: 默认配置
    """
    config = HookConfig()

    # 通用钩子
    config.on_commit = [
        Hook(
            name="lint-check",
            agent="code-guardian",
            action="lint",
            description="提交时检查代码风格",
        ),
    ]

    config.on_pr = [
        Hook(
            name="full-audit",
            agent="code-guardian",
            action="full",
            description="PR 时运行完整审计",
        ),
        Hook(
            name="link-check",
            agent="doc-curator",
            action="check-links",
            description="PR 时检查文档链接",
            condition="files_contain('*.md')",
        ),
    ]

    config.on_merge = [
        Hook(
            name="update-index",
            agent="doc-curator",
            action="update-index",
            description="合并后更新文档索引",
        ),
    ]

    config.scheduled = [
        Hook(
            name="weekly-audit",
            agent="code-guardian",
            action="full",
            description="每周完整审计",
            condition="0 9 * * 1",  # 每周一 9:00
        ),
        Hook(
            name="monthly-report",
            agent="workflow-optimizer",
            action="report",
            description="每月效率报告",
            condition="0 9 1 * *",  # 每月 1 号 9:00
        ),
    ]

    # 根据项目类型添加特定钩子
    if project_type == "python":
        config.on_commit.append(
            Hook(
                name="pytest-check",
                agent="code-guardian",
                action="test",
                description="提交时运行 pytest",
            )
        )
    elif project_type == "typescript":
        config.on_commit.append(
            Hook(
                name="vitest-check",
                agent="code-guardian",
                action="test",
                description="提交时运行 vitest",
            )
        )

    return config


class HookExecutor:
    """钩子执行器"""

    def __init__(self, config: HookConfig):
        self.config = config
        self.executors: dict[str, Callable] = {}

    def register_executor(self, agent: str, action: str, executor: Callable) -> None:
        """注册执行器"""
        key = f"{agent}:{action}"
        self.executors[key] = executor

    def execute(self, event: str, context: Optional[dict] = None) -> list[dict]:
        """
        执行指定事件的钩子

        Args:
            event: 事件类型 (commit, pr, merge, scheduled)
            context: 上下文信息

        Returns:
            执行结果列表
        """
        results = []
        hooks = self.config.get_enabled_hooks(event)

        for hook in hooks:
            # 检查条件
            if hook.condition and not self._check_condition(hook.condition, context):
                continue

            # 执行钩子
            key = f"{hook.agent}:{hook.action}"
            executor = self.executors.get(key)

            if executor:
                try:
                    result = executor(context)
                    results.append({
                        "hook": hook.name,
                        "success": True,
                        "result": result,
                    })
                except Exception as e:
                    results.append({
                        "hook": hook.name,
                        "success": False,
                        "error": str(e),
                    })
            else:
                results.append({
                    "hook": hook.name,
                    "success": False,
                    "error": f"No executor for {key}",
                })

        return results

    def _check_condition(self, condition: str, context: Optional[dict]) -> bool:
        """检查条件"""
        # 简单条件解析
        if "files_contain(" in condition:
            # 提取文件模式
            start = condition.find("(") + 1
            end = condition.find(")")
            pattern = condition[start:end].strip("'\"")

            # 检查上下文
            if context and "changed_files" in context:
                for file in context["changed_files"]:
                    if pattern.replace("*", "") in file:
                        return True
                return False
            return True  # 无上下文时默认通过

        return True  # 默认通过


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python hook_system.py <command> [args]")
        print("Commands:")
        print("  init [project_type]")
        print("  list <config_path>")
        print("  validate <config_path>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        project_type = sys.argv[2] if len(sys.argv) > 2 else "generic"
        config = create_default_config(project_type)
        config.save(".jcode/hooks.json")
        print(f"✅ Hook config initialized for {project_type}")

    elif command == "list":
        config_path = sys.argv[2] if len(sys.argv) > 2 else ".jcode/hooks.json"
        config = HookConfig.load(config_path)

        print("Hooks:")
        print(f"  on_commit: {len(config.on_commit)}")
        print(f"  on_pr: {len(config.on_pr)}")
        print(f"  on_merge: {len(config.on_merge)}")
        print(f"  scheduled: {len(config.scheduled)}")

    elif command == "validate":
        config_path = sys.argv[2] if len(sys.argv) > 2 else ".jcode/hooks.json"
        try:
            config = HookConfig.load(config_path)
            print(f"✅ Config is valid")
            print(f"   Total hooks: {len(config.on_commit) + len(config.on_pr) + len(config.on_merge) + len(config.scheduled)}")
        except Exception as e:
            print(f"❌ Config validation failed: {e}")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
