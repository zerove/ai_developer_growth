"""Extended tests for src/auditor.py — cover Violation, FeedbackManager, SpecAuditor."""

import json
from unittest.mock import MagicMock, patch

from src.auditor import FeedbackManager, SpecAuditor, Violation
from src.exceptions import LLMError


# ---------------------------------------------------------------------------
# Violation dataclass
# ---------------------------------------------------------------------------
class TestViolation:
    def test_to_dict(self):
        v = Violation(rule_id="R1", message="msg", severity="Critical", file_path="a.py")
        d = v.to_dict()
        assert d == {
            "rule_id": "R1",
            "message": "msg",
            "severity": "Critical",
            "file_path": "a.py",
            "line_number": None,
            "status": "open",
        }

    def test_defaults(self):
        v = Violation(rule_id="R2", message="m", severity="Warning", file_path="b.py")
        assert v.line_number is None
        assert v.status == "open"

    def test_custom_fields(self):
        v = Violation(
            rule_id="R3",
            message="m",
            severity="Info",
            file_path="c.py",
            line_number=42,
            status="fixed",
        )
        assert v.line_number == 42
        assert v.status == "fixed"


# ---------------------------------------------------------------------------
# FeedbackManager
# ---------------------------------------------------------------------------
class TestFeedbackManager:
    def test_load_history_nonexistent_file(self, tmp_path):
        path = str(tmp_path / "missing.json")
        fm = FeedbackManager(history_file=path)
        assert fm.history == []

    def test_load_history_valid_file(self, tmp_path):
        path = tmp_path / "history.json"
        data = [
            {
                "rule_id": "R1",
                "file_path": "a.py",
                "message": "m",
                "severity": "Warning",
                "status": "open",
            }
        ]
        path.write_text(json.dumps(data), encoding="utf-8")
        fm = FeedbackManager(history_file=str(path))
        assert len(fm.history) == 1
        assert fm.history[0]["rule_id"] == "R1"

    def test_load_history_corrupt_file(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("NOT JSON {{{", encoding="utf-8")
        fm = FeedbackManager(history_file=str(path))
        assert fm.history == []

    def test_load_history_oserror(self, tmp_path):
        path = tmp_path / "unreadable.json"
        path.write_text("[]", encoding="utf-8")
        with patch("builtins.open", side_effect=OSError("permission denied")):
            fm = FeedbackManager(history_file=str(path))
        # OSError is caught, returns []
        assert fm.history == []

    def test_save_violation_new(self, tmp_path):
        path = tmp_path / "history.json"
        fm = FeedbackManager(history_file=str(path))
        v = Violation(rule_id="R1", message="msg", severity="Warning", file_path="a.py")
        fm.save_violation(v)
        assert len(fm.history) == 1
        assert fm.history[0]["rule_id"] == "R1"
        # File should be persisted
        persisted = json.loads(path.read_text(encoding="utf-8"))
        assert len(persisted) == 1

    def test_save_violation_duplicate_skipped(self, tmp_path):
        path = tmp_path / "history.json"
        fm = FeedbackManager(history_file=str(path))
        v1 = Violation(rule_id="R1", message="msg", severity="Warning", file_path="a.py")
        fm.save_violation(v1)
        v2 = Violation(rule_id="R1", message="msg", severity="Warning", file_path="a.py")
        fm.save_violation(v2)
        assert len(fm.history) == 1

    def test_save_violation_different_not_duplicate(self, tmp_path):
        path = tmp_path / "history.json"
        fm = FeedbackManager(history_file=str(path))
        v1 = Violation(rule_id="R1", message="msg", severity="Warning", file_path="a.py")
        fm.save_violation(v1)
        v2 = Violation(rule_id="R1", message="different msg", severity="Warning", file_path="a.py")
        fm.save_violation(v2)
        assert len(fm.history) == 2

    def test_update_status(self, tmp_path):
        path = tmp_path / "history.json"
        fm = FeedbackManager(history_file=str(path))
        v1 = Violation(rule_id="R1", message="m1", severity="Warning", file_path="a.py")
        v2 = Violation(rule_id="R2", message="m2", severity="Info", file_path="b.py")
        fm.save_violation(v1)
        fm.save_violation(v2)
        fm.update_status("R1", "fixed")
        assert fm.history[0]["status"] == "fixed"
        assert fm.history[1]["status"] == "open"
        # Verify persist
        persisted = json.loads(path.read_text(encoding="utf-8"))
        assert persisted[0]["status"] == "fixed"

    def test_persist_writes_json(self, tmp_path):
        path = tmp_path / "out.json"
        fm = FeedbackManager(history_file=str(path))
        v = Violation(rule_id="X", message="y", severity="Info", file_path="z.py")
        fm.save_violation(v)
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data[0]["rule_id"] == "X"


# ---------------------------------------------------------------------------
# SpecAuditor
# ---------------------------------------------------------------------------
class TestSpecAuditor:
    def _make_auditor(self, tmp_path):
        mock_client = MagicMock()
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        return (
            SpecAuditor(llm_client=mock_client, specs_dir=str(specs_dir)),
            mock_client,
            specs_dir,
        )

    def test_init(self, tmp_path):
        auditor, _, _ = self._make_auditor(tmp_path)
        assert auditor.specs_dir == str(tmp_path / "specs")

    def test_get_relevant_specs_with_files(self, tmp_path):
        auditor, _, specs_dir = self._make_auditor(tmp_path)
        (specs_dir / "style.md").write_text("Use type hints", encoding="utf-8")
        (specs_dir / "readme.txt").write_text("ignored", encoding="utf-8")
        result = auditor.get_relevant_specs("some diff")
        assert "type hints" in result
        assert "Spec: style.md" in result
        assert "readme.txt" not in result

    def test_get_relevant_specs_empty_dir(self, tmp_path):
        auditor, _, _ = self._make_auditor(tmp_path)
        result = auditor.get_relevant_specs("some diff")
        assert result == ""

    def test_get_relevant_specs_nonexistent_dir(self, tmp_path):
        mock_client = MagicMock()
        auditor = SpecAuditor(llm_client=mock_client, specs_dir=str(tmp_path / "nope"))
        result = auditor.get_relevant_specs("some diff")
        assert result == ""

    def test_verify_violation_returns_yes(self, tmp_path):
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        mock_client.generate.return_value = "YES - This is a real violation."
        v = Violation(rule_id="R1", message="bad", severity="Warning", file_path="a.py")
        assert auditor._verify_violation(v, "diff text", "spec text") is True

    def test_verify_violation_returns_no(self, tmp_path):
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        mock_client.generate.return_value = "NO - This is a false positive."
        v = Violation(rule_id="R1", message="bad", severity="Warning", file_path="a.py")
        assert auditor._verify_violation(v, "diff", "spec") is False

    def test_verify_violation_empty_response(self, tmp_path):
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        mock_client.generate.return_value = ""
        v = Violation(rule_id="R1", message="bad", severity="Warning", file_path="a.py")
        assert auditor._verify_violation(v, "diff", "spec") is False

    def test_verify_violation_none_response(self, tmp_path):
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        mock_client.generate.return_value = None
        v = Violation(rule_id="R1", message="bad", severity="Warning", file_path="a.py")
        assert auditor._verify_violation(v, "diff", "spec") is False

    def test_verify_violation_llm_error(self, tmp_path):
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        mock_client.generate.side_effect = LLMError("timeout")
        v = Violation(rule_id="R1", message="bad", severity="Warning", file_path="a.py")
        assert auditor._verify_violation(v, "diff", "spec") is False

    def test_generate_fix_success(self, tmp_path):
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        mock_client.generate.return_value = "def fixed(): pass"
        v = Violation(rule_id="R1", message="bad", severity="Critical", file_path="a.py")
        result = auditor.generate_fix(v, "diff", "spec")
        assert result == "def fixed(): pass"

    def test_generate_fix_empty_response(self, tmp_path):
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        mock_client.generate.return_value = ""
        v = Violation(rule_id="R1", message="bad", severity="Critical", file_path="a.py")
        result = auditor.generate_fix(v, "diff", "spec")
        assert result == "Could not generate a fix."

    def test_generate_fix_none_response(self, tmp_path):
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        mock_client.generate.return_value = None
        v = Violation(rule_id="R1", message="bad", severity="Critical", file_path="a.py")
        result = auditor.generate_fix(v, "diff", "spec")
        assert result == "Could not generate a fix."

    def test_generate_fix_llm_error(self, tmp_path):
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        mock_client.generate.side_effect = LLMError("api down")
        v = Violation(rule_id="R1", message="bad", severity="Critical", file_path="a.py")
        result = auditor.generate_fix(v, "diff", "spec")
        assert result == "Error generating fix."

    def test_audit_no_specs_returns_empty(self, tmp_path):
        """No spec files → immediate empty return."""
        auditor, mock_client, _ = self._make_auditor(tmp_path)
        result = auditor.audit("diff", "task")
        assert result == []
        mock_client.generate.assert_not_called()

    @patch("src.auditor.parse_llm_json")
    def test_audit_attack_returns_none(self, mock_parse, tmp_path):
        auditor, mock_client, specs_dir = self._make_auditor(tmp_path)
        (specs_dir / "spec.md").write_text("rule content", encoding="utf-8")
        mock_client.generate.return_value = "[]"
        mock_parse.return_value = None
        result = auditor.audit("diff", "task")
        assert result == []

    @patch("src.auditor.parse_llm_json")
    def test_audit_attack_returns_empty_list(self, mock_parse, tmp_path):
        auditor, mock_client, specs_dir = self._make_auditor(tmp_path)
        (specs_dir / "spec.md").write_text("rule content", encoding="utf-8")
        mock_client.generate.return_value = "[]"
        mock_parse.return_value = []
        result = auditor.audit("diff", "task")
        assert result == []

    @patch("src.auditor.parse_llm_json")
    def test_audit_confirms_violations(self, mock_parse, tmp_path):
        auditor, mock_client, specs_dir = self._make_auditor(tmp_path)
        (specs_dir / "spec.md").write_text("rule content", encoding="utf-8")
        mock_client.generate.return_value = "[]"
        mock_parse.return_value = [{"rule_id": "R1", "message": "bad code", "severity": "Warning"}]
        # Verification: first call is attack, subsequent are verify
        mock_client.generate.side_effect = [
            "[]",  # attack response
            "YES - real violation",  # verify call
        ]
        result = auditor.audit("diff", "task")
        assert len(result) == 1
        assert result[0].rule_id == "R1"

    @patch("src.auditor.parse_llm_json")
    def test_audit_rejects_false_positive(self, mock_parse, tmp_path):
        auditor, mock_client, specs_dir = self._make_auditor(tmp_path)
        (specs_dir / "spec.md").write_text("rule content", encoding="utf-8")
        mock_parse.return_value = [{"rule_id": "R1", "message": "not real", "severity": "Info"}]
        mock_client.generate.side_effect = [
            "[]",  # attack
            "NO - false positive",  # verify
        ]
        result = auditor.audit("diff", "task")
        assert result == []

    def test_audit_llm_error_returns_empty(self, tmp_path):
        auditor, mock_client, specs_dir = self._make_auditor(tmp_path)
        (specs_dir / "spec.md").write_text("rule content", encoding="utf-8")
        mock_client.generate.side_effect = LLMError("boom")
        result = auditor.audit("diff", "task")
        assert result == []

    @patch("src.auditor.parse_llm_json")
    def test_audit_candidates_with_defaults(self, mock_parse, tmp_path):
        """Candidates missing fields get defaults."""
        auditor, mock_client, specs_dir = self._make_auditor(tmp_path)
        (specs_dir / "spec.md").write_text("rule", encoding="utf-8")
        mock_parse.return_value = [{}]
        mock_client.generate.side_effect = [
            "[]",
            "YES",
        ]
        result = auditor.audit("diff", "task")
        assert len(result) == 1
        assert result[0].rule_id == "UNKNOWN"
        assert result[0].message == "No message provided"
        assert result[0].severity == "Info"
        assert result[0].file_path == "unknown"
