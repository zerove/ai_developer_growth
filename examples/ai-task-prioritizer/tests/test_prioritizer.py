import pytest
from unittest.mock import MagicMock
from prioritizer import Prioritizer

def test_prioritize_sorting():
    # Mock LLMClient
    mock_client = MagicMock()
    mock_client.get_scores.return_value = [
        {"task": "Task A", "value": 5, "effort": 5}, # Score 1.0
        {"task": "Task B", "value": 10, "effort": 2}, # Score 5.0
        {"task": "Task C", "value": 2, "effort": 8}, # Score 0.25
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
