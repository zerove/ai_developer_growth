#!/usr/bin/env python3
"""
jcode Skill Runner - 多 Agent 编排器

用法:
    python .jcode/scripts/multi-agent-orch.py waterfall "<需求描述>"
    python .jcode/scripts/multi-agent-orch.py fanout "<需求描述>"
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE = ROOT / "examples" / "multi-agent-orch"


def _load_orch():
    """从示例项目导入编排包（mock LLM 模式，无需 API key）。"""
    sys.path.insert(0, str(EXAMPLE))
    try:
        from multi_agent_orch import demo  # type: ignore[import-not-found]
    except ImportError as e:
        print(f"❌ 无法加载 multi_agent_orch: {e}")
        sys.exit(1)
    return demo


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("waterfall", "fanout"):
        print('用法: multi-agent-orch.py <waterfall|fanout> "<需求描述>"')
        sys.exit(1)

    mode, request = args[0], " ".join(args[1:])
    demo = _load_orch()
    print(f"[multi-agent-orch] 模式={mode} 需求={request[:50]}")
    if mode == "waterfall":
        demo.run_waterfall(request)
    else:
        demo.run_fan_out(request)


if __name__ == "__main__":
    main()
