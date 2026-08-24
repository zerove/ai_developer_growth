#!/usr/bin/env python3
"""
ADR Generator with LLM support.

Modes:
  - Interactive (default): 逐字段手动输入
  - Auto: 从标题+简述自动生成完整 ADR
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any


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
    title = input("决策标题: ")
    context = input("背景: ")
    alternatives = input("替代方案: ")
    decision = input("决策: ")
    consequences = input("后果: ")

    body = (
        f"## Context\n{context}\n\n"
        f"## Alternatives\n{alternatives}\n\n"
        f"## Decision\n{decision}\n\n"
        f"## Consequences\n{consequences}\n"
    )
    return title, body


def generate_from_llm_mode() -> tuple[str, str]:
    print("--- ADR 生成器 (LLM 模式) ---")
    title = input("决策标题: ")
    brief = input("简短描述 (一句话说明决策): ")

    print("\n🤖 正在用 LLM 生成 ADR 内容...")
    body = generate_from_llm(title, brief)
    print(f"\n--- 生成结果预览 ---\n{body}\n---\n")
    confirm = input("是否使用该内容? (y/n, 默认 y): ").strip().lower()
    if confirm == "n":
        print("已取消，回退到交互模式...")
        return generate_interactive()
    return title, body


def save_adr(title: str, body: str) -> str:
    adr_dir = "docs/adr/"
    os.makedirs(adr_dir, exist_ok=True)

    existing = [f for f in os.listdir(adr_dir) if f.startswith("ADR-")]
    index = len(existing) + 1
    filename = f"ADR-{index:03d}-{title.replace(' ', '_').lower()}.md"
    filepath = os.path.join(adr_dir, filename)

    date = datetime.now().strftime("%Y-%m-%d")
    content = f"# {index:03d}: {title}\n\n* 状态: Accepted\n* 日期: {date}\n\n{body}"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n✅ ADR 已生成: {filepath}")
    return filepath


def main() -> None:
    mode = input("选择模式 (1=交互, 2=LLM自动生成, 默认 2): ").strip()
    if mode == "1":
        title, body = generate_interactive()
    else:
        try:
            title, body = generate_from_llm_mode()
        except Exception as e:
            print(f"\n⚠️ LLM 调用失败: {e}")
            print("回退到交互模式...")
            title, body = generate_interactive()

    save_adr(title, body)


if __name__ == "__main__":
    main()
