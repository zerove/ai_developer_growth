"""Shared fixtures for ai-context-sync tests."""

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def adr_dir():
    """Create a temporary ADR directory with test ADR files."""
    tmpdir = tempfile.mkdtemp()

    # ADR-001: No dependencies
    with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
        f.write("# ADR-001: Use REST API\n\nWe will use REST for external APIs.\n")

    # ADR-002: Depends on ADR-001
    with open(os.path.join(tmpdir, "ADR-002.md"), "w") as f:
        f.write(
            "# ADR-002: Add Authentication\n\n- **Depends On:** [ADR-001]\n\nWe add JWT auth to the REST API.\n"
        )

    # ADR-003: Depends on ADR-002, supersedes ADR-001
    with open(os.path.join(tmpdir, "ADR-003.md"), "w") as f:
        f.write(
            "# ADR-003: OAuth2 Migration\n\n"
            "- **Depends On:** [ADR-002]\n"
            "- **Supersedes:** [ADR-001]\n\n"
            "Migrate from JWT to OAuth2.\n"
        )

    # Invalid ADR file (no matching header)
    with open(os.path.join(tmpdir, "ADR-999.md"), "w") as f:
        f.write("# Random Notes\n\nSome random content.\n")

    yield tmpdir
    shutil.rmtree(tmpdir)


@pytest.fixture
def empty_adr_dir():
    """Create an empty temporary ADR directory."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)
