"""Tests for src/reasoning.py - DecisionReasoner"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.reasoning import DecisionReasoner


class TestDecisionReasoner:
    def test_init(self, adr_dir):
        mock_llm = MagicMock()
        reasoner = DecisionReasoner(mock_llm, adr_dir)
        assert reasoner.adr_dir == adr_dir
        assert reasoner.graph is not None
        assert len(reasoner.graph.nodes) == 3

    def test_find_relevant_adrs(self, adr_dir):
        mock_llm = MagicMock()
        reasoner = DecisionReasoner(mock_llm, adr_dir)
        adrs = reasoner._find_relevant_adrs("REST API")
        assert len(adrs) >= 1
        assert any("REST" in a for a in adrs)

    def test_find_relevant_adrs_no_match(self, adr_dir):
        mock_llm = MagicMock()
        reasoner = DecisionReasoner(mock_llm, adr_dir)
        adrs = reasoner._find_relevant_adrs("quantum computing blockchain")
        assert len(adrs) == 0

    def test_find_relevant_adrs_empty_dir(self, empty_adr_dir):
        mock_llm = MagicMock()
        reasoner = DecisionReasoner(mock_llm, empty_adr_dir)
        adrs = reasoner._find_relevant_adrs("anything")
        assert adrs == []

    def test_find_relevant_adrs_nonexistent_dir(self):
        mock_llm = MagicMock()
        reasoner = DecisionReasoner(mock_llm, "/nonexistent/path")
        adrs = reasoner._find_relevant_adrs("REST")
        assert adrs == []

    def test_explain_decision_no_match(self, adr_dir):
        mock_llm = MagicMock()
        reasoner = DecisionReasoner(mock_llm, adr_dir)
        result = reasoner.explain_decision("quantum computing")
        assert (
            "no relevant adr" in result.lower()
            or "couldn't find" in result.lower()
            or "no specific" in result.lower()
        )

    def test_explain_decision_with_llm(self, adr_dir):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "This decision was made because..."
        reasoner = DecisionReasoner(mock_llm, adr_dir)
        result = reasoner.explain_decision("REST API")
        mock_llm.generate.assert_called_once()
        assert "This decision" in result

    def test_find_relevant_adrs_by_adr_id(self, adr_dir):
        mock_llm = MagicMock()
        reasoner = DecisionReasoner(mock_llm, adr_dir)
        adrs = reasoner._find_relevant_adrs("Tell me about ADR-001")
        assert len(adrs) >= 1
        assert "ADR-001" in adrs[0]

    def test_find_relevant_adrs_by_adr_id_no_match(self, adr_dir):
        mock_llm = MagicMock()
        reasoner = DecisionReasoner(mock_llm, adr_dir)
        adrs = reasoner._find_relevant_adrs("Explain ADR-9999 decision")
        assert isinstance(adrs, list)

    def test_explain_decision_by_adr_id(self, adr_dir):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "ADR-001 chose REST."
        reasoner = DecisionReasoner(mock_llm, adr_dir)
        result = reasoner.explain_decision("Summarize ADR-001")
        mock_llm.generate.assert_called_once()
        assert "ADR-001" in result

    def test_explain_decision_llm_failure(self, adr_dir):
        mock_llm = MagicMock()
        mock_llm.generate.return_value = ""
        reasoner = DecisionReasoner(mock_llm, adr_dir)
        result = reasoner.explain_decision("REST API")
        assert "Error" in result or "failed" in result.lower()
