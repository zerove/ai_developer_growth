"""End-to-end integration test for the full AI-Native workflow."""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core import AIContextSync


class TestEndToEndFlow:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, ".ai-sync.json")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_core_init_dry_run(self):
        with open(self.config_path, "w") as f:
            import json
            json.dump({"llm": {"provider": "openai", "model": "gpt-4o"}, "settings": {}}, f)
        sync = AIContextSync(config_path=self.config_path, dry_run=True)
        assert sync.dry_run is True
        assert sync.config is not None

    def test_guard_check_returns_string(self):
        with open(self.config_path, "w") as f:
            import json
            json.dump({"llm": {}, "settings": {}}, f)
        sync = AIContextSync(config_path=self.config_path, dry_run=True)
        result = sync.guard_check()
        assert isinstance(result, str)

    def test_spec_audit_returns_string(self):
        with open(self.config_path, "w") as f:
            import json
            json.dump({"llm": {}, "settings": {}}, f)
        sync = AIContextSync(config_path=self.config_path, dry_run=True)
        result = sync.spec_audit()
        assert isinstance(result, str)

    def test_get_aggregated_context(self):
        with open(self.config_path, "w") as f:
            import json
            json.dump({"llm": {}, "settings": {"context_file": os.path.join(self.tmpdir, "CONTEXT.md")}}, f)
        with open(os.path.join(self.tmpdir, "CONTEXT.md"), "w") as f:
            f.write("# Test Context\nProject description.")
        sync = AIContextSync(config_path=self.config_path, dry_run=True)
        result = sync.get_aggregated_context(["dummy_file.py"])
        assert isinstance(result, str)

    def test_config_roundtrip(self):
        with open(self.config_path, "w") as f:
            import json
            json.dump({"llm": {"provider": "anthropic", "model": "claude-3"}, "settings": {"test_timeout": 60}}, f)
        sync = AIContextSync(config_path=self.config_path, dry_run=True)
        assert sync.config.llm.provider == "anthropic"
        assert sync.config.settings.test_timeout == 60
