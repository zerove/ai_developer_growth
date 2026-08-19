"""Tests for low coverage modules to improve overall test coverage."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.scripts.semantic_code_graph import CodeNode, SemanticCodeGraph
from tools.scripts.session_memory_vectorizer import (
    main as session_main,
)
from tools.scripts.session_memory_vectorizer import (
    search_memory,
    vectorize_sessions,
)
from tools.scripts.smart_commit import (
    generate_commit_message,
    get_staged_files,
)
from tools.scripts.smart_commit import (
    main as smart_commit_main,
)
from tools.scripts.tdd_state_machine import TDDStateMachine


class TestCodeNode(unittest.TestCase):
    """Test CodeNode class."""

    def test_code_node_creation(self):
        node = CodeNode("test_func", "function", "test.py", 10)
        self.assertEqual(node.name, "test_func")
        self.assertEqual(node.node_type, "function")
        self.assertEqual(node.file_path, "test.py")
        self.assertEqual(node.line, 10)
        self.assertEqual(node.dependencies, set())
        self.assertEqual(node.dependents, set())

    def test_code_node_to_dict(self):
        node = CodeNode("test_func", "function", "test.py", 10)
        node.dependencies.add("dep1")
        node.dependents.add("dep2")
        result = node.to_dict()
        self.assertEqual(result["name"], "test_func")
        self.assertEqual(result["node_type"], "function")
        self.assertEqual(result["file_path"], "test.py")
        self.assertEqual(result["line"], 10)
        self.assertIn("dep1", result["dependencies"])
        self.assertIn("dep2", result["dependents"])


class TestSemanticCodeGraph(unittest.TestCase):
    """Test SemanticCodeGraph class."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.root_dir = Path(self.temp_dir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_semantic_code_graph_initialization(self):
        graph = SemanticCodeGraph(self.root_dir)
        self.assertEqual(graph.root_dir, self.root_dir)
        self.assertEqual(graph.nodes, {})

    def test_build_graph_empty_directory(self):
        graph = SemanticCodeGraph(self.root_dir)
        graph.build_graph()
        self.assertEqual(graph.nodes, {})

    def test_build_graph_with_python_file(self):
        test_file = self.root_dir / "test_module.py"
        test_file.write_text("""
def hello():
    return world()

class MyClass(BaseClass):
    def method(self):
        return helper()
""")
        graph = SemanticCodeGraph(self.root_dir)
        graph.build_graph()
        self.assertGreater(len(graph.nodes), 0)

    def test_query_impact(self):
        test_file = self.root_dir / "test_module.py"
        test_file.write_text("""
def target_func():
    return helper()

def caller():
    return target_func()
""")
        graph = SemanticCodeGraph(self.root_dir)
        graph.build_graph()
        results = graph.query_impact("target_func")
        self.assertGreater(len(results), 0)

    def test_save_to_json(self):
        test_file = self.root_dir / "test_module.py"
        test_file.write_text("def test(): pass")
        graph = SemanticCodeGraph(self.root_dir)
        graph.build_graph()
        output_path = self.root_dir / "output.json"
        graph.save_to_json(output_path)
        self.assertTrue(output_path.exists())
        with open(output_path) as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)


class TestSessionMemoryVectorizer(unittest.TestCase):
    """Test session_memory_vectorizer module."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sessions_dir = Path(self.temp_dir) / "sessions"
        self.sessions_dir.mkdir()
        self.index_file = Path(self.temp_dir) / "memory_index.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_vectorize_sessions_empty_dir(self):
        result = vectorize_sessions(self.sessions_dir, self.index_file)
        self.assertEqual(result, {"entries": []})
        self.assertTrue(self.index_file.exists())

    def test_vectorize_sessions_with_markdown_files(self):
        note1 = self.sessions_dir / "note1.md"
        note1.write_text("# Test Note 1\nContent here")
        note2 = self.sessions_dir / "note2.md"
        note2.write_text("# Another Note\nMore content")

        result = vectorize_sessions(self.sessions_dir, self.index_file)
        self.assertEqual(len(result["entries"]), 2)
        titles = [e["title"] for e in result["entries"]]
        self.assertIn("Test Note 1", titles)
        self.assertIn("Another Note", titles)

    def test_vectorize_sessions_nested_directories(self):
        nested_dir = self.sessions_dir / "nested"
        nested_dir.mkdir()
        note = nested_dir / "nested_note.md"
        note.write_text("# Nested Note\nContent")

        result = vectorize_sessions(self.sessions_dir, self.index_file)
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["title"], "Nested Note")

    def test_search_memory_empty_index(self):
        result = search_memory(self.index_file, "query")
        self.assertEqual(result, [])

    def test_search_memory_with_matches(self):
        note1 = self.sessions_dir / "note1.md"
        note1.write_text("# Test Feature\nImplementation details")
        vectorize_sessions(self.sessions_dir, self.index_file)

        results = search_memory(self.index_file, "feature")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Test Feature")

    def test_search_memory_case_insensitive(self):
        note1 = self.sessions_dir / "note1.md"
        note1.write_text("# Test FEATURE\nContent")
        vectorize_sessions(self.sessions_dir, self.index_file)

        results = search_memory(self.index_file, "feature")
        self.assertEqual(len(results), 1)

    def test_search_memory_keyword_match(self):
        note1 = self.sessions_dir / "note1.md"
        note1.write_text("# Long Title With Multiple Words\nContent")
        vectorize_sessions(self.sessions_dir, self.index_file)

        results = search_memory(self.index_file, "multiple")
        self.assertEqual(len(results), 1)

    def test_main_vectorize(self):
        note1 = self.sessions_dir / "note1.md"
        note1.write_text("# Test\nContent")
        with patch(
            "sys.argv",
            ["session_memory_vectorizer.py", "--dir", str(self.sessions_dir), "--index", str(self.index_file)],
        ):
            result = session_main()
            self.assertEqual(result, 0)

    def test_main_search(self):
        note1 = self.sessions_dir / "note1.md"
        note1.write_text("# Test Feature\nContent")
        vectorize_sessions(self.sessions_dir, self.index_file)
        with patch(
            "sys.argv", ["session_memory_vectorizer.py", "--index", str(self.index_file), "--search", "feature"]
        ):
            result = session_main()
            self.assertEqual(result, 0)

    def test_main_invalid_index(self):
        with patch("sys.argv", ["session_memory_vectorizer.py", "--index", str(self.index_file), "--search", "query"]):
            result = session_main()
            self.assertEqual(result, 0)


class TestSmartCommit(unittest.TestCase):
    """Test smart_commit module."""

    @patch("subprocess.run")
    def test_get_staged_files_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="file1.py\nfile2.md\n", returncode=0)
        files = get_staged_files()
        self.assertEqual(files, ["file1.py", "file2.md"])

    @patch("subprocess.run")
    def test_get_staged_files_empty(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        files = get_staged_files()
        self.assertEqual(files, [])

    @patch("subprocess.run")
    def test_get_staged_files_error(self, mock_run):
        mock_run.side_effect = subprocess.SubprocessError("git error")
        files = get_staged_files()
        self.assertEqual(files, [])

    def test_generate_commit_message_empty(self):
        msg = generate_commit_message([])
        self.assertEqual(msg, "chore: update repository files")

    def test_generate_commit_message_docs_only(self):
        msg = generate_commit_message(["docs/readme.md", "guide.md"])
        self.assertEqual(msg, "docs: update knowledge base and documentation")

    def test_generate_commit_message_tests_only(self):
        msg = generate_commit_message(["test_file.py", "tests/unit.py"])
        self.assertEqual(msg, "test: add or update test suites")

    def test_generate_commit_message_ci(self):
        msg = generate_commit_message([".github/workflows/ci.yml"])
        self.assertEqual(msg, "ci: update GitHub Actions and workflows")

    def test_generate_commit_message_tools(self):
        msg = generate_commit_message(["tools/script.py"])
        self.assertEqual(msg, "feat(tools): enhance automation scripts and CLI tooling")

    def test_generate_commit_message_default(self):
        msg = generate_commit_message(["src/main.py"])
        self.assertEqual(msg, "refactor: update implementation and architecture components")

    def test_generate_commit_message_priority_docs_over_tests(self):
        # docs only triggers when NO tools AND NO tests (condition 1)
        # If tests present, condition 2 (tests and not tools) takes priority
        msg = generate_commit_message(["docs/readme.md", "test_file.py"])
        # has_docs=True, has_tests=True, has_tools=False -> condition 2 matches
        self.assertEqual(msg, "test: add or update test suites")

    def test_generate_commit_message_docs_only_no_tests_no_tools(self):
        # docs triggers when no tools and no tests
        msg = generate_commit_message(["docs/readme.md", "guide.md"])
        self.assertEqual(msg, "docs: update knowledge base and documentation")

    def test_generate_commit_message_priority_tests_over_tools(self):
        # tools takes priority over tests (condition 4 evaluated after condition 2)
        msg = generate_commit_message(["tests/unit.py", "tools/script.py"])
        # has_tests=True, has_tools=True -> condition 2 fails, condition 4 matches
        self.assertEqual(msg, "feat(tools): enhance automation scripts and CLI tooling")

    def test_generate_commit_message_priority_ci_over_tools(self):
        # ci takes priority over tools
        msg = generate_commit_message([".github/workflows/ci.yml", "tools/script.py"])
        self.assertEqual(msg, "ci: update GitHub Actions and workflows")

    @patch("subprocess.run")
    def test_main_dry_run(self, mock_run):
        mock_run.return_value = MagicMock(stdout="file.py\n", returncode=0)
        with patch("sys.argv", ["smart_commit.py", "--dry-run"]):
            result = smart_commit_main()
            self.assertEqual(result, 0)

    @patch("subprocess.run")
    def test_main_commit_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="file.py\n", returncode=0)
        with patch("sys.argv", ["smart_commit.py"]):
            result = smart_commit_main()
            self.assertEqual(result, 0)

    @patch("subprocess.run")
    def test_main_commit_failure(self, mock_run):
        mock_run.return_value = MagicMock(stdout="file.py\n", returncode=0)

        # Second call to git commit fails
        def side_effect(*args, **kwargs):
            if args[0][:2] == ["git", "diff"]:
                return MagicMock(stdout="file.py\n", returncode=0)
            elif args[0][:2] == ["git", "commit"]:
                raise subprocess.SubprocessError("commit failed")

        mock_run.side_effect = side_effect
        with patch("sys.argv", ["smart_commit.py"]):
            result = smart_commit_main()
            self.assertEqual(result, 1)


class TestTDDStateMachine(unittest.TestCase):
    """Test TDDStateMachine class."""

    def test_initial_state(self):
        sm = TDDStateMachine()
        self.assertEqual(sm.state, "RED")

    def test_transition_red_to_green(self):
        sm = TDDStateMachine()
        result = sm.transition("test_written_failing")
        self.assertTrue(result)
        self.assertEqual(sm.state, "GREEN")

    def test_transition_green_to_refactor(self):
        sm = TDDStateMachine()
        sm.transition("test_written_failing")
        result = sm.transition("implementation_passing")
        self.assertTrue(result)
        self.assertEqual(sm.state, "REFACTOR")

    def test_transition_refactor_to_red(self):
        sm = TDDStateMachine()
        sm.transition("test_written_failing")
        sm.transition("implementation_passing")
        result = sm.transition("refactor_complete")
        self.assertTrue(result)
        self.assertEqual(sm.state, "RED")

    def test_invalid_transition_red_wrong_action(self):
        sm = TDDStateMachine()
        result = sm.transition("implementation_passing")
        self.assertFalse(result)
        self.assertEqual(sm.state, "RED")

    def test_invalid_transition_green_wrong_action(self):
        sm = TDDStateMachine()
        sm.transition("test_written_failing")
        result = sm.transition("refactor_complete")
        self.assertFalse(result)
        self.assertEqual(sm.state, "GREEN")

    def test_validate_action_correct_phase(self):
        sm = TDDStateMachine()
        valid, msg = sm.validate_action("RED", "write_test")
        self.assertTrue(valid)
        self.assertEqual(msg, "Phase action validated.")

    def test_validate_action_wrong_phase(self):
        sm = TDDStateMachine()
        sm.transition("test_written_failing")  # Now in GREEN
        valid, msg = sm.validate_action("RED", "write_test")
        self.assertFalse(valid)
        self.assertIn("TDD Violation", msg)

    def test_full_cycle(self):
        sm = TDDStateMachine()
        self.assertEqual(sm.state, "RED")
        sm.transition("test_written_failing")
        self.assertEqual(sm.state, "GREEN")
        sm.transition("implementation_passing")
        self.assertEqual(sm.state, "REFACTOR")
        sm.transition("refactor_complete")
        self.assertEqual(sm.state, "RED")


if __name__ == "__main__":
    unittest.main()
