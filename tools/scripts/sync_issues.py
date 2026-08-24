#!/usr/bin/env python3
"""
GitHub Projects/Issue 双向同步工具

功能:
- 从 GitHub Projects 同步 Issue 到本地/远程
- 将本地变更推送到 GitHub Projects
- 支持自定义字段映射、标签同步、状态同步
- 支持增量同步、全量同步、冲突解决

用法:
    python sync_issues.py --sync-project PROJECT_NUMBER --repo OWNER/REPO
    python sync_issues.py --sync-issue ISSUE_NUMBER --repo OWNER/REPO
    python sync_issues.py --full-sync --repo OWNER/REPO --project PROJECT_NUMBER
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests
from github import Github
from github.Issue import Issue
from github.Label import Label
from github.Milestone import Milestone


class GitHubProjectsSync:
    """GitHub Projects/Issue 同步器"""

    def __init__(self, token: str, repo: str, project_number: int):
        self.github = Github(token)
        self.repo = self.github.get_repo(repo)
        self.project = self.github.get_project(project_number)
        self.token = token
        self.repo_name = repo
        self.project_number = project_number

        # 缓存
        self._labels_cache: dict[str, Label] = {}
        self._milestones_cache: dict[str, Milestone] = {}
        self._project_columns_cache: dict[str, str] = {}  # column_name -> column_id

        self._init_caches()

    def _init_caches(self) -> None:
        """初始化缓存"""
        # 缓存标签
        for label in self.repo.get_labels():
            self._labels_cache[label.name.lower()] = label

        # 缓存里程碑
        for milestone in self.repo.get_milestones(state="all"):
            self._milestones_cache[milestone.title.lower()] = milestone

        # 缓存项目列
        if hasattr(self.project, "get_columns"):
            for column in self.project.get_columns():
                self._project_columns_cache[column.name] = str(column.id)

    # ==================== 同步核心逻辑 ====================

    def sync_issue_to_project(self, issue_number: int) -> dict[str, Any]:
        """将单个 Issue 同步到 Project"""
        issue = self.repo.get_issue(issue_number)

        # 检查是否已在 Project 中
        project_cards = self._get_project_cards()
        existing_card = None
        for card in project_cards:
            if card.content_url and f"/issues/{issue_number}" in card.content_url:
                existing_card = card
                break

        if existing_card:
            # 更新现有卡片
            return self._update_project_card(existing_card, issue)
        else:
            # 创建新卡片
            return self._create_project_card(issue)

    def _get_project_cards(self) -> list[Any]:
        """获取 Project 中所有卡片"""
        cards = []
        if hasattr(self.project, "get_columns"):
            for column in self.project.get_columns():
                cards.extend(list(column.get_cards()))
        return cards

    def _create_project_card(self, issue: Issue) -> dict[str, Any]:
        """在 Project 中创建卡片"""
        # 确定目标列（默认第一列或按标签/状态映射）
        column_id = self._get_target_column_id(issue)

        # 使用 GitHub REST API 创建卡片
        url = f"https://api.github.com/projects/columns/{column_id}/cards"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        data: dict[str, Any] = {"content_type": "Issue", "content_id": issue.id}

        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 201:
            return {"status": "created", "card": response.json()}
        else:
            return {"status": "error", "error": response.text}

    def _update_project_card(self, card: Any, issue: Issue) -> dict[str, Any]:
        """更新 Project 卡片（移动到正确的列）"""
        target_column_id = self._get_target_column_id(issue)

        if card.column_id == target_column_id:
            return {"status": "up_to_date"}

        # 移动卡片
        url = f"https://api.github.com/projects/columns/cards/{card.id}/moves"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        data = {"position": "top", "column_id": target_column_id}

        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 201:
            return {"status": "moved", "card": response.json()}
        else:
            return {"status": "error", "error": response.text}

    def _get_target_column_id(self, issue: Issue) -> str:
        """根据 Issue 状态/标签确定目标列"""
        # 状态映射
        state_mapping = {
            "open": "Todo",
            "closed": "Done",
        }

        # 标签映射优先
        label_mapping = {
            "ready": "Ready",
            "in-progress": "In Progress",
            "in-review": "In Review",
            "blocked": "Blocked",
            "done": "Done",
        }

        # 检查标签
        for label in issue.labels:
            if label.name.lower() in label_mapping:
                column_name = label_mapping[label.name.lower()]
                if column_name in self._project_columns_cache:
                    return self._project_columns_cache[column_name]

        # 回退到状态映射
        state = issue.state.lower()
        if state in state_mapping:
            column_name = state_mapping[state]
            if column_name in self._project_columns_cache:
                return self._project_columns_cache[column_name]

        # 默认第一列
        columns = list(self._project_columns_cache.values())
        return columns[0] if columns else ""

    def sync_project_to_issues(self) -> list[dict[str, Any]]:
        """从 Project 同步卡片状态回 Issue"""
        results = []
        project_cards = self._get_project_cards()

        for card in project_cards:
            if not card.content_url or "/issues/" not in card.content_url:
                continue

            issue_number = int(card.content_url.split("/issues/")[-1])
            issue = self.repo.get_issue(int(issue_number))

            # 根据列名更新 Issue 状态/标签
            result = self._sync_card_to_issue(issue, card.column_id, card.note)
            results.append({"issue": issue.number, "result": result})

        return results

    def _sync_card_to_issue(self, issue: Issue, column_id: str, note: str = "") -> dict[str, Any]:
        """将卡片状态同步回 Issue"""
        # 获取列名
        column_name = ""
        for name, cid in self._project_columns_cache.items():
            if cid == column_id:
                column_name = name
                break

        if not column_name:
            return {"status": "unknown_column"}

        # 列名到标签/状态映射
        column_to_label = {
            "Ready": "ready",
            "In Progress": "in-progress",
            "In Review": "in-review",
            "Blocked": "blocked",
            "Done": "done",
        }

        column_to_state = {
            "Done": "closed",
            "Todo": "open",
            "Backlog": "open",
        }

        changes = []

        # 更新标签
        if column_name in column_to_label:
            label_name = column_to_label[column_name]
            if not any(label.name.lower() == label_name.lower() for label in issue.labels):
                issue.add_to_labels(label_name)
                changes.append(f"added label: {label_name}")

        # 更新状态
        if column_name in column_to_state:
            target_state = column_to_state[column_name]
            if issue.state != target_state:
                if target_state == "closed":
                    issue.edit(state="closed")
                else:
                    issue.edit(state="open")
                changes.append(f"state changed to: {target_state}")

        return {"status": "synced", "changes": changes}

    def full_sync(self, dry_run: bool = False) -> dict[str, Any]:
        """全量同步：双向同步所有 Issue 和 Project 卡片"""
        print(f"开始全量同步: {self.repo_name} -> Project #{self.project_number}")

        results: dict[str, Any] = {
            "issues_to_project": [],
            "project_to_issues": [],
            "errors": [],
        }

        # 1. 将所有开放 Issue 同步到 Project
        open_issues = list(self.repo.get_issues(state="open"))
        print(f"发现 {len(open_issues)} 个开放 Issue")

        for issue in self.repo.get_issues(state="all"):
            try:
                if not dry_run:
                    result = self.sync_issue_to_project(issue.number)
                    results["issues_to_project"].append({"issue": issue.number, "result": result})
            except Exception as e:
                results["errors"].append({"issue": issue.number, "error": str(e)})

        # 2. 从 Project 同步回 Issue
        project_results = self.sync_project_to_issues()
        results["project_to_issues"] = project_results

        return results

    def sync_specific_issues(self, issue_numbers: list[int]) -> dict[str, Any]:
        """同步指定的 Issue 列表"""
        results = []
        for num in issue_numbers:
            try:
                result = self.sync_issue_to_project(num)
                results.append({"issue": num, "result": "success", "detail": result})
            except Exception as e:
                results.append({"issue": num, "result": "error", "error": str(e)})
        return {"results": results}

    # ==================== 工具方法 ====================

    def get_project_info(self) -> dict[str, Any]:
        """获取 Project 信息"""
        return {
            "id": self.project.id,
            "name": self.project.name,
            "number": self.project.number,
            "columns": list(self._project_columns_cache.keys()),
            "columns_count": len(self._project_columns_cache),
        }

    def list_project_issues(self) -> list[dict[str, Any]]:
        """列出 Project 中的所有 Issue"""
        cards = self._get_project_cards()
        issues = []
        for card in cards:
            if card.content_url and "/issues/" in card.content_url:
                issue_num = int(card.content_url.split("/issues/")[-1])
                issue = self.repo.get_issue(issue_num)
                issues.append(
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "state": issue.state,
                        "labels": [label.name for label in issue.labels],
                        "assignees": [assignee.login for assignee in issue.assignees],
                        "column": (card.column_name if hasattr(card, "column_name") else "Unknown"),
                    }
                )
        return issues


def create_sync_tool() -> GitHubProjectsSync:
    """创建同步器实例"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("请设置 GITHUB_TOKEN 环境变量")

    return GitHubProjectsSync(token, "", 0)  # 实际使用时需要传入 repo 和 project_number


# ==================== CLI 入口 ====================


def _build_sync_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="GitHub Projects/Issue 双向同步工具")
    parser.add_argument("--repo", required=True, help="仓库 (格式: owner/repo)")
    parser.add_argument("--project", type=int, required=True, help="Project 编号")
    parser.add_argument("--token", help="GitHub Token (默认读取 GITHUB_TOKEN 环境变量)")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # full-sync
    sync_parser = subparsers.add_parser("full-sync", help="全量双向同步")
    sync_parser.add_argument("--dry-run", action="store_true", help="试运行")

    # sync-issue
    issue_parser = subparsers.add_parser("sync-issue", help="同步指定 Issue")
    issue_parser.add_argument("--issue", type=int, required=True, help="Issue 编号")

    # sync-project

    # list-project

    # project-info

    # sync-specific
    specific_parser = subparsers.add_parser("sync-issues", help="同步指定 Issue 列表")
    specific_parser.add_argument("--issues", nargs="+", type=int, required=True, help="Issue 编号列表")

    return parser


def _execute_sync_command(sync: GitHubProjectsSync, args: argparse.Namespace) -> None:
    """执行同步子命令并打印 JSON 结果。"""
    if args.command == "full-sync":
        result = sync.full_sync(dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "sync-issue":
        result = sync.sync_issue_to_project(args.issue)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "sync-project":
        project_result: list[dict[str, Any]] = sync.sync_project_to_issues()
        print(json.dumps(project_result, indent=2, ensure_ascii=False))

    elif args.command == "list-project":
        issues = sync.list_project_issues()
        print(json.dumps(issues, indent=2, ensure_ascii=False))

    elif args.command == "project-info":
        info = sync.get_project_info()
        print(json.dumps(info, indent=2, ensure_ascii=False))

    elif args.command == "sync-issues":
        result = sync.sync_specific_issues(args.issues)
        print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> int:
    parser = _build_sync_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    args.token or os.getenv("GITHUB_TOKEN")
    if not args.token and not os.getenv("GITHUB_TOKEN"):
        print("错误: 请提供 GitHub Token (--token 或 GITHUB_TOKEN 环境变量)")
        return 1

    try:
        sync = GitHubProjectsSync(args.token, args.repo, args.project)
        _execute_sync_command(sync, args)
        return 0
    except Exception as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
