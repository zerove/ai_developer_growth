"""Tests for watcher.py - AuditHandler and WatchManager."""

from unittest.mock import MagicMock, mock_open, patch


class TestAuditHandler:
    def setup_method(self):
        self.mock_sync = MagicMock()
        self.mock_sync.config.settings.watcher_debounce = 1.0
        self.mock_sync.config.settings.ignore = ["node_modules", ".git"]
        self.mock_sync.config.settings.live_report_path = "docs/ai-audit-live.md"
        self.mock_sync.auditor.audit.return_value = []

    def test_init_sets_debounce(self):
        from src.watcher import AuditHandler

        handler = AuditHandler(self.mock_sync)
        assert handler.debounce_interval == 1.0

    def test_on_modified_skips_directories(self):
        from src.watcher import AuditHandler

        handler = AuditHandler(self.mock_sync)
        event = MagicMock()
        event.is_directory = True
        handler.on_modified(event)
        self.mock_sync.auditor.audit.assert_not_called()

    def test_on_modified_skips_hidden_files(self):
        from src.watcher import AuditHandler

        handler = AuditHandler(self.mock_sync)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/path/to/.hidden_file"
        handler.on_modified(event)
        self.mock_sync.auditor.audit.assert_not_called()

    def test_on_modified_skips_ignored_patterns(self):
        from src.watcher import AuditHandler

        handler = AuditHandler(self.mock_sync)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/path/to/node_modules/package.json"
        handler.on_modified(event)
        self.mock_sync.auditor.audit.assert_not_called()

    def test_on_modified_calls_auditor(self):
        from src.watcher import AuditHandler

        handler = AuditHandler(self.mock_sync)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/path/to/src/main.py"
        handler.on_modified(event)
        self.mock_sync.auditor.audit.assert_called_once()

    def test_on_modified_debounce(self):
        from src.watcher import AuditHandler

        handler = AuditHandler(self.mock_sync)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/path/to/src/main.py"
        handler.on_modified(event)
        assert self.mock_sync.auditor.audit.call_count == 1

    def test_write_live_report(self):
        from src.watcher import AuditHandler

        handler = AuditHandler(self.mock_sync)
        with patch("builtins.open", mock_open()) as mock_file:
            handler._write_live_report("test.py", "All good")
            handle = mock_file()
            all_content = "".join(c[0][0] for c in handle.write.call_args_list)
            assert "test.py" in all_content
            assert "All good" in all_content
