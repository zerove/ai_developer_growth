"""Extended tests for src/watcher.py — cover violation reporting, Critical fixes, WatchManager lifecycle."""

from unittest.mock import MagicMock, mock_open, patch

from src.watcher import AuditHandler


class TestAuditHandlerViolations:
    """Cover on_modified with violations including Critical severity."""

    def setup_method(self):
        self.mock_sync = MagicMock()
        self.mock_sync.config.settings.watcher_debounce = 0.0
        self.mock_sync.config.settings.ignore = ["node_modules", ".git"]
        self.mock_sync.config.settings.live_report_path = "docs/ai-audit-live.md"
        self.mock_sync.config.settings.config_path = "/project/.ai-sync.json"

    @patch("src.watcher.time.strftime", return_value="2025-01-01 00:00:00")
    @patch("src.watcher.time.time", return_value=1000.0)
    @patch("builtins.open", MagicMock())
    @patch("src.watcher.os.makedirs")
    def test_on_modified_with_violations_no_critical(
        self, _mock_makedirs, _mock_time, _mock_strftime
    ):
        """Non-Critical violations are listed without fix suggestions."""
        violation1 = MagicMock()
        violation1.severity = "Warning"
        violation1.rule_id = "SPEC-001"
        violation1.message = "Missing docstring"

        violation2 = MagicMock()
        violation2.severity = "Info"
        violation2.rule_id = "STYLE-003"
        violation2.message = "Line too long"

        self.mock_sync.auditor.audit.return_value = [violation1, violation2]

        handler = AuditHandler(self.mock_sync)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/src/main.py"

        handler.on_modified(event)

        self.mock_sync.auditor.audit.assert_called_once()
        self.mock_sync.auditor.generate_fix.assert_not_called()

    @patch("src.watcher.time.strftime", return_value="2025-01-01 00:00:00")
    @patch("src.watcher.time.time", return_value=1000.0)
    @patch("builtins.open", MagicMock())
    @patch("src.watcher.os.makedirs")
    def test_on_modified_with_critical_violation(
        self, _mock_makedirs, _mock_time, _mock_strftime
    ):
        """Critical violations trigger fix generation."""
        critical = MagicMock()
        critical.severity = "Critical"
        critical.rule_id = "ADR-001"
        critical.message = "Architecture violation"

        self.mock_sync.auditor.audit.return_value = [critical]
        self.mock_sync.auditor.get_relevant_specs.return_value = "relevant specs"
        self.mock_sync.auditor.generate_fix.return_value = "def fix(): pass"

        handler = AuditHandler(self.mock_sync)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/src/main.py"

        handler.on_modified(event)

        self.mock_sync.auditor.generate_fix.assert_called_once_with(
            critical, "N/A", "relevant specs"
        )

    @patch("src.watcher.time.strftime", return_value="2025-01-01 00:00:00")
    @patch("src.watcher.time.time", return_value=1000.0)
    @patch("builtins.open", MagicMock())
    @patch("src.watcher.os.makedirs")
    def test_on_modified_mixed_severities(
        self, _mock_makedirs, _mock_time, _mock_strftime
    ):
        """Mix of Critical and Warning violations generates fixes only for Critical."""
        critical = MagicMock()
        critical.severity = "Critical"
        critical.rule_id = "ADR-001"
        critical.message = "Violation"

        warning = MagicMock()
        warning.severity = "Warning"
        warning.rule_id = "SPEC-002"
        warning.message = "Minor issue"

        self.mock_sync.auditor.audit.return_value = [critical, warning]
        self.mock_sync.auditor.get_relevant_specs.return_value = "specs"
        self.mock_sync.auditor.generate_fix.return_value = "fix code"

        handler = AuditHandler(self.mock_sync)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/src/main.py"

        handler.on_modified(event)

        self.mock_sync.auditor.generate_fix.assert_called_once()

    @patch("src.watcher.time.strftime", return_value="2025-01-01 00:00:00")
    @patch("src.watcher.os.makedirs")
    @patch("builtins.open", MagicMock())
    def test_on_modified_debounce_prevents_rapid_fire(
        self, _mock_makedirs, _mock_strftime
    ):
        """Second call within debounce window is skipped."""
        self.mock_sync.auditor.audit.return_value = []
        self.mock_sync.config.settings.watcher_debounce = 1.0

        handler = AuditHandler(self.mock_sync)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/project/src/main.py"

        # First call at t=1000
        with patch("src.watcher.time.time", return_value=1000.0):
            handler.on_modified(event)
        assert self.mock_sync.auditor.audit.call_count == 1

        # Second call at t=1000.5 (within debounce)
        with patch("src.watcher.time.time", return_value=1000.5):
            handler.on_modified(event)
        assert self.mock_sync.auditor.audit.call_count == 1

        # Third call at t=1001.5 (outside debounce)
        with patch("src.watcher.time.time", return_value=1001.5):
            handler.on_modified(event)
        assert self.mock_sync.auditor.audit.call_count == 2


class TestWatchManagerExtended:
    """Cover WatchManager.start() and stop() lifecycle."""

    def setup_method(self):
        self.mock_sync = MagicMock()

    @patch("src.watcher.Observer")
    @patch("src.watcher.time.sleep", side_effect=KeyboardInterrupt)
    def test_start_and_stop(self, mock_sleep, mock_observer_cls):
        """start() begins observer; stop() stops and joins."""
        from src.watcher import WatchManager

        mock_observer = MagicMock()
        mock_observer_cls.return_value = mock_observer

        mgr = WatchManager(self.mock_sync)
        mgr.start(path="/project")

        mock_observer.schedule.assert_called_once()
        mock_observer.start.assert_called_once()
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

    @patch("src.watcher.Observer")
    def test_stop_calls_observer_stop_join(self, mock_observer_cls):
        """stop() directly calls observer.stop() and observer.join()."""
        from src.watcher import WatchManager

        mock_observer = MagicMock()
        mock_observer_cls.return_value = mock_observer

        mgr = WatchManager(self.mock_sync)
        mgr.stop()

        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

    @patch("src.watcher.time.strftime", return_value="2025-01-01 00:00:00")
    @patch("src.watcher.os.makedirs")
    def test_write_live_report_content(self, _mock_makedirs, _mock_strftime):
        """Verify live report contains expected sections."""
        self.mock_sync.config.settings.config_path = "/project/.ai-sync.json"

        handler = AuditHandler(self.mock_sync)

        m = mock_open()
        with patch("builtins.open", m):
            handler._write_live_report("test.py", "✅ All good")

        all_content = "".join(c[0][0] for c in m().write.call_args_list)
        assert "AI-Native Real-time Audit Dashboard" in all_content
        assert "test.py" in all_content
        assert "All good" in all_content

    @patch("src.watcher.time.strftime", return_value="2025-01-01 00:00:00")
    @patch("src.watcher.os.makedirs")
    def test_write_live_report_with_violations(self, _mock_makedirs, _mock_strftime):
        """Verify live report includes violation details."""
        self.mock_sync.config.settings.config_path = "/project/.ai-sync.json"

        handler = AuditHandler(self.mock_sync)

        violation_report = "Found 2 violation(s):\n1. [Critical] ADR-001: Bad"

        m = mock_open()
        with patch("builtins.open", m):
            handler._write_live_report("main.py", violation_report)

        all_content = "".join(c[0][0] for c in m().write.call_args_list)
        assert "ADR-001" in all_content
        assert "main.py" in all_content
        assert "Keep this file open" in all_content
