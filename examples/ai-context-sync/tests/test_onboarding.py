"""Tests for onboarding.py - OnboardingSession."""

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from src.onboarding import OnboardingSession


class TestOnboardingSession:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init(self):
        mock_llm = MagicMock()
        session = OnboardingSession(mock_llm, self.tmpdir)
        assert session.root_dir == self.tmpdir
        assert session.current_focus == "Global"

    def test_find_files_for_area_by_directory(self):
        mock_llm = MagicMock()
        os.makedirs(os.path.join(self.tmpdir, "src"))
        with open(os.path.join(self.tmpdir, "src", "CONTEXT.md"), "w") as f:
            f.write("# Context")
        session = OnboardingSession(mock_llm, self.tmpdir)
        files = session._find_files_for_area("src")
        assert len(files) >= 1
        assert any("CONTEXT.md" in f for f in files)

    def test_find_files_for_area_by_filename(self):
        mock_llm = MagicMock()
        with open(os.path.join(self.tmpdir, "config.yaml"), "w") as f:
            f.write("key: value")
        session = OnboardingSession(mock_llm, self.tmpdir)
        files = session._find_files_for_area("config")
        assert len(files) >= 1
        assert any("config.yaml" in f for f in files)

    def test_find_files_for_area_no_match(self):
        mock_llm = MagicMock()
        session = OnboardingSession(mock_llm, self.tmpdir)
        files = session._find_files_for_area("nonexistent")
        assert files == ["CONTEXT.md"]

    def test_start_no_context(self):
        mock_llm = MagicMock()
        session = OnboardingSession(mock_llm, self.tmpdir)
        with patch("src.onboarding.logger") as mock_logger:
            session.start()
            mock_logger.error.assert_called()
