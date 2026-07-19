#!/usr/bin/env python3
import os
import sys
import argparse
from openai import OpenAI


def load_context() -> str:
    context_file = "CONTEXT.md"
    if not os.path.exists(context_file):
        return "# Project Context\n\n## Current Progress\n- Initial project setup."
    with open(context_file, "r", encoding="utf-8") as f:
        return f.read()


def save_context(content: str) -> None:
    with open("CONTEXT.md", "w", encoding="utf-8") as f:
        f.write(content)


def update_context_with_llm(current_context: str, changes: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    if not api_key:
        print("错误: 请设置环境变量 OPENAI_API_KEY")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=api_base)

    prompt = (
        "You are a project context manager. I will provide you with the current CONTEXT.md "
        "and a summary of recent changes. Your task is to update the 'Current Progress' "
        "section of CONTEXT.md to reflect these changes while maintaining the overall structure. "
        "Ensure the tone is professional and concise. Return ONLY the full updated content of CONTEXT.md.\n\n"
        f"--- CURRENT CONTEXT.md ---\n{current_context}\n\n"
        f"--- RECENT CHANGES ---\n{changes}\n\n"
        "--- UPDATED CONTEXT.md ---"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM 调用失败: {e}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Context Manager - 自动更新 CONTEXT.md")
    parser.add_argument("changes", nargs="?", help="变更总结或提交信息")
    args = parser.parse_args()

    changes = args.changes
    if not changes:
        changes = input("请输入最近的变更总结或提交信息: ")

    if not changes:
        print("没有提供变更信息，退出。")
        return

    print("正在读取当前上下文...")
    current_context = load_context()

    print("正在使用 AI 更新上下文...")
    updated_context = update_context_with_llm(current_context, changes)

    save_context(updated_context)
    print("\n成功更新 CONTEXT.md!")


if __name__ == "__main__":
    main()
