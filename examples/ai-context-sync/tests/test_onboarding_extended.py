"""Extended tests for src/onboarding.py — cover start() interactive flow, multiple areas."""
import os
import shutil
import tempfile
from unittest.mock import MagicMock, call, patch

from src.onboarding import OnboardingSession


class TestStartInteractiveFlow:
    """Cover start() normal interactive flow with mocked input()."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create a CONTEXT.md for the slicer
        with open(os.path.join(self.tmpdir, "CONTEXT.md"), "w") as f:
            f.write("# Project Context\nArchitecture overview.\n")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_start_normal_flow_exit_immediately(self):
        """User types 'exit' immediately after the initial prompt."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Overview:\n- Point 1\nSuggested Areas: auth, db, api"

        session = OnboardingSession(mock_llm, self.tmpdir)

        with patch("builtins.input", return_value="exit"), \
             patch("src.onboarding.logger"):
            session.start()

        # LLM was called once for initial prompt
        assert mock_llm.generate.call_count == 1

    def test_start_normal_flow_quit_keyword(self):
        """User types 'quit' to exit."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Overview\nSuggested Areas: auth"

        session = OnboardingSession(mock_llm, self.tmpdir)

        with patch("builtins.input", return_value="quit"), \
             patch("src.onboarding.logger"):
            session.start()

        assert mock_llm.generate.call_count == 1

    def test_start_normal_flow_q_keyword(self):
        """User types 'q' to exit."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Overview\nSuggested Areas: auth"

        session = OnboardingSession(mock_llm, self.tmpdir)

        with patch("builtins.input", return_value="q"), \
             patch("src.onboarding.logger"):
            session.start()

        assert mock_llm.generate.call_count == 1


class TestStartExploreMultipleAreas:
    """Cover start() when user explores areas before exiting."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "CONTEXT.md"), "w") as f:
            f.write("# Project Context\nFull overview.\n")
        # Create an area directory
        os.makedirs(os.path.join(self.tmpdir, "auth"))
        with open(os.path.join(self.tmpdir, "auth", "CONTEXT.md"), "w") as f:
            f.write("# Auth Context\nAuthentication module.\n")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_explore_multiple_areas_then_exit(self):
        """User explores 'auth', then 'api', then exits."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Context for area."

        session = OnboardingSession(mock_llm, self.tmpdir)

        with patch("builtins.input", side_effect=["auth", "api", "exit"]), \
             patch("src.onboarding.logger"):
            session.start()

        # Initial prompt + 2 area explorations = 3 calls
        assert mock_llm.generate.call_count == 3
        assert session.current_focus == "api"

    def test_explore_area_updates_current_focus(self):
        """Exploring an area updates the current_focus attribute."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Info."

        session = OnboardingSession(mock_llm, self.tmpdir)

        with patch("builtins.input", side_effect=["database", "exit"]), \
             patch("src.onboarding.logger"):
            session.start()

        assert session.current_focus == "database"


class TestStartNoContext:
    """Cover start() when global context is not found."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_start_no_context_logs_error(self):
        """When no CONTEXT.md exists, logs error and returns early."""
        mock_llm = MagicMock()
        session = OnboardingSession(mock_llm, self.tmpdir)

        with patch("src.onboarding.logger") as mock_logger:
            session.start()

        mock_logger.error.assert_called()
        # LLM should never be called
        mock_llm.generate.assert_not_called()

    def test_start_no_context_does_not_prompt_user(self):
        """When no context exists, input() is never called."""
        mock_llm = MagicMock()
        session = OnboardingSession(mock_llm, self.tmpdir)

        with patch("src.onboarding.logger"), \
             patch("builtins.input") as mock_input:
            session.start()

        mock_input.assert_not_called()


class TestFindFilesForAreaExtended:
    """Cover _find_files_for_area edge cases."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_find_files_case_insensitive(self):
        """Search is case-insensitive."""
        mock_llm = MagicMock()
        os.makedirs(os.path.join(self.tmpdir, "MyModule"))
        with open(os.path.join(self.tmpdir, "MyModule", "CONTEXT.md"), "w") as f:
            f.write("# Context")

        session = OnboardingSession(mock_llm, self.tmpdir)
        files = session._find_files_for_area("mymodule")
        assert any("CONTEXT.md" in f for f in files)

    def test_find_files_matches_in_subdirectories(self):
        """Search finds files in nested subdirectories."""
        mock_llm = MagicMock()
        nested = os.path.join(self.tmpdir, "a", "b", "c")
        os.makedirs(nested)
        with open(os.path.join(nested, "deep_file.py"), "w") as f:
            f.write("# deep")

        session = OnboardingSession(mock_llm, self.tmpdir)
        files = session._find_files_for_area("deep_file")
        assert any("deep_file.py" in f for f in files)
