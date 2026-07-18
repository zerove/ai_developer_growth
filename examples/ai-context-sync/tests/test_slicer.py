"""Tests for src/slicer.py - ContextSlicer"""
import os
import sys
import tempfile
import shutil
import pytest

# Setup import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.slicer import ContextSlicer


@pytest.fixture
def project_dir():
    """Create a temporary project directory with CONTEXT.md files."""
    tmpdir = tempfile.mkdtemp()
    # Root CONTEXT.md
    with open(os.path.join(tmpdir, "CONTEXT.md"), "w") as f:
        f.write("# Root Context\nProject-level docs.")
    # Subdirectory CONTEXT.md
    sub = os.path.join(tmpdir, "src", "module_a")
    os.makedirs(sub)
    with open(os.path.join(sub, "CONTEXT.md"), "w") as f:
        f.write("# Module A Context\nModule-level docs.")
    # A regular file
    with open(os.path.join(sub, "code.py"), "w") as f:
        f.write("x = 1\n")
    # Another subdirectory without CONTEXT.md
    sub_b = os.path.join(tmpdir, "src", "module_b")
    os.makedirs(sub_b)
    with open(os.path.join(sub_b, "code.py"), "w") as f:
        f.write("y = 2\n")
    yield tmpdir
    shutil.rmtree(tmpdir)


class TestContextSlicer:
    def test_init_default_root(self):
        slicer = ContextSlicer()
        assert slicer.root_dir == "."

    def test_init_custom_root(self, project_dir):
        slicer = ContextSlicer(root_dir=project_dir)
        assert slicer.root_dir == project_dir

    def test_slice_empty_files_returns_root_context(self, project_dir):
        slicer = ContextSlicer(root_dir=project_dir)
        result = slicer.slice([])
        assert "Root Context" in result

    def test_slice_no_files_no_root_context(self):
        slicer = ContextSlicer(root_dir=tempfile.mkdtemp())
        result = slicer.slice([])
        assert result == ""

    def test_slice_finds_nested_context(self, project_dir):
        slicer = ContextSlicer(root_dir=project_dir)
        result = slicer.slice(["src/module_a/code.py"])
        assert "Root Context" in result
        assert "Module A Context" in result

    def test_slice_deduplicates_context_files(self, project_dir):
        slicer = ContextSlicer(root_dir=project_dir)
        # Same file twice should not duplicate context
        result = slicer.slice(["src/module_a/code.py", "src/module_a/code.py"])
        assert result.count("Root Context") == 1

    def test_slice_no_context_in_subdir(self, project_dir):
        slicer = ContextSlicer(root_dir=project_dir)
        result = slicer.slice(["src/module_b/code.py"])
        assert "Root Context" in result
        assert "Module A Context" not in result

    def test_find_context_files_direct(self, project_dir):
        slicer = ContextSlicer(root_dir=project_dir)
        files = slicer._find_context_files("src/module_a/code.py")
        # Should find root + module_a CONTEXT.md
        assert len(files) >= 2

    def test_slice_format_has_headers(self, project_dir):
        slicer = ContextSlicer(root_dir=project_dir)
        result = slicer.slice(["src/module_a/code.py"])
        assert "--- Context from" in result
