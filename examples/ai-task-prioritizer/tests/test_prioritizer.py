import os
import sys
import tempfile
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

# Import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from llm_client import LLMClient
from main import main
from prioritizer import Prioritizer


def test_prioritize_sorting():
    # Mock LLMClient
    mock_client = MagicMock()
    mock_client.get_scores.return_value = [
        {"task": "Task A", "value": 5, "effort": 5},  # Score 1.0
        {"task": "Task B", "value": 10, "effort": 2},  # Score 5.0
        {"task": "Task C", "value": 2, "effort": 8},  # Score 0.25
    ]

    prioritizer = Prioritizer(mock_client)
    results = prioritizer.prioritize(["Task A", "Task B", "Task C"])

    # Check sorting order (B, A, C)
    assert results[0]["task"] == "Task B"
    assert results[1]["task"] == "Task A"
    assert results[2]["task"] == "Task C"

    # Check score calculation
    assert results[0]["score"] == 5.0
    assert results[2]["score"] == 0.25


def test_prioritizer_categories():
    """Test category assignment logic (covers lines 30-38)."""
    mock_client = MagicMock()
    mock_client.get_scores.return_value = [
        {"task": "Quick Win", "value": 8, "effort": 2},  # Quick Win
        {"task": "Major Project", "value": 8, "effort": 5},  # Major Project
        {"task": "Fill-in", "value": 3, "effort": 2},  # Fill-ins
        {"task": "Thankless", "value": 2, "effort": 5},  # Thankless Task
    ]

    prioritizer = Prioritizer(mock_client)
    results = prioritizer.prioritize(["Quick Win", "Major Project", "Fill-in", "Thankless"])

    categories = {r["task"]: r["category"] for r in results}
    assert categories["Quick Win"] == "Quick Win (立即执行)"
    assert categories["Major Project"] == "Major Project (计划执行)"
    assert categories["Fill-in"] == "Fill-ins (碎片时间)"
    assert categories["Thankless"] == "Thankless Task (考虑放弃)"


def test_prioritizer_division_by_zero():
    """Test division by zero - current code crashes."""
    mock_client = MagicMock()
    mock_client.get_scores.return_value = [
        {"task": "Zero Effort", "value": 5, "effort": 0},
    ]

    prioritizer = Prioritizer(mock_client)

    # Current code crashes on division by zero
    with pytest.raises(ZeroDivisionError):
        prioritizer.prioritize(["Zero Effort"])


def test_llm_client_init():
    """Test LLMClient initialization (covers lines 5-8)."""
    client = LLMClient(api_key="test-key")
    assert client.api_key == "test-key"

    # Test with env var
    with patch.dict(os.environ, {"LLM_API_KEY": "env-key"}):
        client = LLMClient()
        assert client.api_key == "env-key"


def test_llm_client_get_scores_without_key():
    """Test LLMClient.get_scores raises error without API key (covers lines 10-11)."""
    with patch.dict(os.environ, {}, clear=True):
        client = LLMClient(api_key=None)
        with pytest.raises(ValueError, match="LLM_API_KEY environment variable is not set"):
            client.get_scores(["task1"])


def test_llm_client_get_scores():
    """Test LLMClient.get_scores returns expected format (covers lines 13-16)."""
    with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}):
        client = LLMClient()
        results = client.get_scores(["Task 1", "Task 2"])

        assert len(results) == 2
        assert results[0]["task"] == "Task 1"
        assert "value" in results[0]
        assert "effort" in results[0]
        # Check that values are strings (as per current implementation)
        assert isinstance(results[0]["value"], str)
        assert isinstance(results[0]["effort"], str)


def test_llm_client_build_prompt():
    """Test _build_prompt method (covers lines 18-23)."""
    client = LLMClient(api_key="test")
    prompt = client._build_prompt(["Task A", "Task B"])

    assert "Value (1-10)" in prompt
    assert "Effort (1-10)" in prompt
    assert "Return a JSON object" in prompt
    assert "tasks" in prompt


def test_main_with_stdin(capsys):
    """Test main function with stdin input (covers lines 6-24, 26-38)."""
    input_data = "Task 1\nTask 2\nTask 3\n"
    mock_client = MagicMock()
    mock_client.get_scores.return_value = [
        {"task": "Task 1", "value": 5, "effort": 5},
        {"task": "Task 2", "value": 10, "effort": 2},
        {"task": "Task 3", "value": 3, "effort": 3},
    ]

    with patch("sys.stdin", StringIO(input_data)):
        with patch("main.LLMClient", return_value=mock_client):
            with patch("main.Prioritizer") as mock_prioritizer:
                mock_prioritizer_instance = MagicMock()
                mock_prioritizer_instance.prioritize.return_value = [
                    {"task": "Task 2", "value": 10, "effort": 2, "score": 5.0, "category": "Quick Win"},
                    {"task": "Task 3", "value": 3, "effort": 3, "score": 1.0, "category": "Fill-ins"},
                    {"task": "Task 1", "value": 5, "effort": 5, "score": 1.0, "category": "Fill-ins"},
                ]
                mock_prioritizer.return_value = mock_prioritizer_instance

                # Simulate command line args
                with patch.object(sys, "argv", ["main.py", "-"]):
                    main()

    captured = capsys.readouterr()
    assert "Analyzing 3 tasks" in captured.out
    assert "Task 2" in captured.out


def test_main_with_file(capsys):
    """Test main function with file input (covers lines 12-20)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Task 1\nTask 2\n")
        temp_file = f.name

    try:
        mock_client = MagicMock()
        mock_client.get_scores.return_value = [
            {"task": "Task 1", "value": 5, "effort": 5},
            {"task": "Task 2", "value": 10, "effort": 2},
        ]

        with patch("main.LLMClient", return_value=mock_client):
            with patch("main.Prioritizer") as mock_prioritizer:
                mock_prioritizer_instance = MagicMock()
                mock_prioritizer_instance.prioritize.return_value = [
                    {"task": "Task 2", "value": 10, "effort": 2, "score": 5.0, "category": "Quick Win"},
                    {"task": "Task 1", "value": 5, "effort": 5, "score": 1.0, "category": "Fill-ins"},
                ]
                mock_prioritizer.return_value = mock_prioritizer_instance

                with patch.object(sys, "argv", ["main.py", temp_file]):
                    main()

        captured = capsys.readouterr()
        assert "Analyzing 2 tasks" in captured.out
    finally:
        os.unlink(temp_file)


def test_main_file_not_found(capsys):
    """Test main function with non-existent file (covers lines 18-20)."""
    with patch.object(sys, "argv", ["main.py", "nonexistent.txt"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "File nonexistent.txt not found" in captured.out


def test_main_empty_input(capsys):
    """Test main function with empty input (covers lines 22-24)."""
    with patch("sys.stdin", StringIO("")):
        with patch.object(sys, "argv", ["main.py", "-"]):
            main()

    captured = capsys.readouterr()
    assert "No tasks found" in captured.out


def test_main_exception_handling(capsys):
    """Test main function exception handling (covers lines 40-42)."""
    with patch("sys.stdin", StringIO("Task 1\n")):
        with patch("main.LLMClient") as mock_llm:
            mock_client = MagicMock()
            mock_llm.return_value = mock_client

            with patch("main.Prioritizer") as mock_prioritizer:
                mock_prioritizer_instance = MagicMock()
                mock_prioritizer_instance.prioritize.side_effect = Exception("Test error")
                mock_prioritizer.return_value = mock_prioritizer_instance

                with patch.object(sys, "argv", ["main.py", "-"]):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Test error" in captured.out
