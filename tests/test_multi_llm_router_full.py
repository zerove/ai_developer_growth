"""multi_llm_router 全量: 路由表命中/默认回退/main 入口。67%→100%"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.scripts.multi_llm_router import MultiLLMRouter


class TestMultiLLMRouter:
    def test_known_task_routes_to_table(self) -> None:
        router = MultiLLMRouter()
        res = router.route_task("architecture_design")
        assert res["selected_model"] == "claude-opus-4-7"
        assert res["task_type"] == "architecture_design"
        assert "telemetry" in res["routing_basis"]

    def test_unknown_task_falls_back(self) -> None:
        router = MultiLLMRouter()
        res = router.route_task("nonexistent_kind")
        assert res["selected_model"] == "gemini-3.5-flash-lite"

    def test_custom_root_dir(self, tmp_path: Path) -> None:
        router = MultiLLMRouter(root_dir=tmp_path)
        assert router.root_dir == tmp_path

    def test_main_entry_prints_json(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "tools.scripts.multi_llm_router"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        payload = json.loads(proc.stdout.split(":", 1)[1])
        assert payload["task_type"] == "architecture_design"
