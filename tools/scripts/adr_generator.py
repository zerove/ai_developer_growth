#!/usr/bin/env python3
"""
ADR Generator with LLM support.

Modes:
  - Interactive (default): 逐字段手动输入
  - Auto: 从标题+简述自动生成完整 ADR
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _interactive() -> bool:
    """是否处于可提问的终端环境。

    非 TTY（hook / CI / 管道）里调用 input() 会抛 EOFError，
    ADR-060 记录了由此导致 community-catalyst 的 generate_adr 必然失败。
    """
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _prompt(message: str, default: str = "") -> str:
    """仅在可交互时提问，否则用默认值，避免 EOFError。"""
    if not _interactive():
        return default
    try:
        return input(message)
    except EOFError:
        return default


def _get_llm_client() -> Any:
    """Lazy import of LLMClient from examples/ai-context-sync."""
    _script_dir = Path(__file__).resolve().parent
    _ai_ctx_sync = _script_dir.parent.parent / "examples" / "ai-context-sync"
    import sys

    if str(_ai_ctx_sync) not in sys.path:
        sys.path.insert(0, str(_ai_ctx_sync))
    from src.llm_client import LLMClient  # noqa: E402

    return LLMClient


SYSTEM_PROMPT = (
    "You are a senior software architect. Generate a structured ADR document. "
    "Output ONLY the markdown body (no title header). Use these sections: "
    "## Context, ## Alternatives, ## Decision, ## Consequences. "
    "Be concise and technical."
)


def _get_llm_config() -> dict[str, str]:
    """获取 LLM 配置：环境变量 > 配置 > 默认值。"""
    try:
        from tools.scripts.app_config import get_setting

        # 环境变量优先
        provider: str = os.getenv("LLM_PROVIDER") or str(get_setting("llm_provider", "openai"))
        model: str = os.getenv("LLM_MODEL") or str(get_setting("llm_model", "gpt-4o"))
        return {
            "provider": provider,
            "model": model,
        }
    except Exception:
        return {
            "provider": os.getenv("LLM_PROVIDER", "openai"),
            "model": os.getenv("LLM_MODEL", "gpt-4o"),
        }


def generate_from_llm(title: str, brief: str) -> str:
    llm_cls = _get_llm_client()
    config = _get_llm_config()
    llm = llm_cls(provider=config["provider"], model=config["model"])
    prompt = (
        f"Generate an Architecture Decision Record for:\n"
        f"Title: {title}\n"
        f"Brief: {brief}\n\n"
        f"Include realistic technical context, 2-3 alternatives with trade-offs, "
        f"a clear decision rationale, and balanced consequences."
    )
    result = llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
    return result or ""


def generate_interactive() -> tuple[str, str]:
    print("--- ADR 生成器 (交互模式) ---")
    title = _prompt("决策标题: ")
    context = _prompt("背景: ")
    alternatives = _prompt("替代方案: ")
    decision = _prompt("决策: ")
    consequences = _prompt("后果: ")

    body = (
        f"## Context\n{context}\n\n"
        f"## Alternatives\n{alternatives}\n\n"
        f"## Decision\n{decision}\n\n"
        f"## Consequences\n{consequences}\n"
    )
    return title, body


def generate_from_llm_mode(title: str = "", brief: str = "") -> tuple[str, str]:
    print("--- ADR 生成器 (LLM 模式) ---")
    title = _prompt("决策标题: ", title)
    brief = _prompt("简短描述 (一句话说明决策): ", brief)

    print("\n🤖 正在用 LLM 生成 ADR 内容...")
    body = generate_from_llm(title, brief)
    print(f"\n--- 生成结果预览 ---\n{body}\n---\n")
    confirm = _prompt("是否使用该内容? (y/n, 默认 y): ", "y").strip().lower()
    if confirm == "n":
        print("已取消，回退到交互模式...")
        return generate_interactive()
    return title, body


def _next_adr_index(adr_dir: str) -> int:
    """下一个可用序号。

    早前用 len(existing) + 1，序号有缺口时会与既有文件撞名并静默覆盖
    （例：只有 ADR-001 与 ADR-005 时，len=2 -> 3）。改为取最大序号 + 1。
    """
    highest = 0
    for name in os.listdir(adr_dir):
        if not name.startswith("ADR-"):
            continue
        parts = name.split("-", 2)
        if len(parts) < 2 or not parts[1].isdigit():
            continue
        highest = max(highest, int(parts[1]))
    return highest + 1


def _slugify(title: str, max_len: int = 60) -> str:
    """把标题转成跨平台安全的文件名片段。

    早前用 title.replace(' ', '_')，于是 "test: 文件计数断言" 会生成含 ':' 的
    文件名——在 Windows 与部分归档/zip 工具上直接非法。改为只保留
    [A-Za-z0-9_-]，其余折叠成 '-'。
    """
    kept = [c if (c.isascii() and (c.isalnum() or c in "_-")) else "-" for c in title]
    slug = "".join(kept).lower()
    slug = re.sub(r"-{2,}", "-", slug).strip("-_")
    return slug[:max_len].strip("-_") or "adr"


def save_adr(title: str, body: str, adr_dir: str = "docs/adr/") -> str:
    os.makedirs(adr_dir, exist_ok=True)

    slug = _slugify(title)
    index = _next_adr_index(adr_dir)
    filepath = os.path.join(adr_dir, f"ADR-{index:03d}-{slug}.md")
    suffix = 1
    while os.path.exists(filepath):
        filepath = os.path.join(adr_dir, f"ADR-{index:03d}-{slug}-{suffix}.md")
        suffix += 1

    date = datetime.now().strftime("%Y-%m-%d")
    content = f"# {index:03d}: {title}\n\n* 状态: Accepted\n* 日期: {date}\n\n{body}"

    with open(filepath, "x", encoding="utf-8") as f:
        f.write(content)
    print(f"\n✅ ADR 已生成: {filepath}")
    return filepath


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ADR 生成器（支持非交互 / 自动化调用）")
    parser.add_argument("--pr", help="关联的 PR / commit 引用，写入 ADR 正文")
    parser.add_argument("--title", default="", help="决策标题（非交互模式必填）")
    parser.add_argument("--brief", default="", help="决策简述，用于 LLM 生成")
    parser.add_argument("--interactive", action="store_true", help="强制逐字段交互输入")
    parser.add_argument("--llm", action="store_true", help="使用 LLM 生成正文（默认）")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    parser.add_argument("--adr-dir", default="docs/adr/", help="输出目录")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # 非交互且缺少必要输入时明确失败，而不是让 input() 抛 EOFError。
    if not args.interactive and not args.title and not _interactive():
        print("❌ 非交互模式下必须提供 --title（--brief 建议一并提供）")
        print("   或加 --interactive 走逐字段输入。")
        return 1

    if args.interactive:
        title, body = generate_interactive()
    else:
        try:
            title, body = generate_from_llm_mode(args.title, args.brief)
        except Exception as e:  # noqa: BLE001 - LLM 不可用时降级，而非整体失败
            if not _interactive():
                print(f"❌ LLM 调用失败且当前非交互，无法回退: {e}")
                return 1
            print(f"\n⚠️ LLM 调用失败: {e}")
            print("回退到交互模式...")
            title, body = generate_interactive()

    if args.pr:
        body = f"{body}\n\n## 关联变更\n\n- PR / Commit: `{args.pr}`\n"

    if not title.strip():
        print("❌ 决策标题为空，未生成文件")
        return 1

    if args.dry_run:
        print(f"\n--- dry-run（不写入 {args.adr_dir}）---\n# {title}\n\n{body}")
        return 0

    save_adr(title, body, args.adr_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
