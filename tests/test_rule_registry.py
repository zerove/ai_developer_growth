"""Tests for rule_registry.py (19% → target 85%)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from tools.scripts.rule_registry import (
    _file_hash,
    _load_registry,
    _save_registry,
    cmd_info,
    cmd_init,
    cmd_install,
    cmd_list,
    cmd_publish,
    cmd_remove,
    cmd_search,
    init_registry,
    main,
)


@pytest.fixture()
def fake_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect registry to tmp_path."""
    monkeypatch.setattr("tools.scripts.rule_registry._registry_dir", lambda: tmp_path)
    monkeypatch.setattr("tools.scripts.rule_registry._packs_dir", lambda: tmp_path / "packs")
    return tmp_path


def _make_args(**kwargs: Any) -> argparse.Namespace:
    defaults = {
        "json": False,
        "name": None,
        "version": None,
        "description": None,
        "tags": None,
        "source": "",
        "pack": "",
        "query": "",
        "project_dir": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestInitRegistry:
    """Tests for init_registry() and cmd_init()."""

    def test_init_creates_dirs(self, fake_registry: Path) -> None:
        init_registry()
        assert (fake_registry / "packs").is_dir()
        assert (fake_registry / "registry.json").exists()

    def test_init_already_exists(self, fake_registry: Path, capsys: Any) -> None:
        init_registry()
        init_registry()
        assert "already exists" in capsys.readouterr().out

    def test_cmd_init(self, fake_registry: Path) -> None:
        cmd_init(_make_args())
        assert (fake_registry / "registry.json").exists()


class TestLoadSaveRegistry:
    """Tests for _load_registry() and _save_registry()."""

    def test_save_and_load(self, fake_registry: Path) -> None:
        data = {"packs": {"test": {"version": "1.0"}}, "version": "1.0"}
        _save_registry(data)
        loaded = _load_registry()
        assert loaded["packs"]["test"]["version"] == "1.0"

    def test_load_empty(self, fake_registry: Path) -> None:
        loaded = _load_registry()
        assert loaded == {"packs": {}, "version": "1.0"}


class TestFileHash:
    """Tests for _file_hash()."""

    def test_hash_valid_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h = _file_hash(f)
        assert len(h) == 16

    def test_hash_missing_file(self) -> None:
        h = _file_hash(Path("/nonexistent/file"))
        assert h == ""

    def test_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("data")
        assert _file_hash(f) == _file_hash(f)


class TestCmdList:
    """Tests for cmd_list()."""

    def test_empty_registry(self, fake_registry: Path, capsys: Any) -> None:
        cmd_list(_make_args())
        assert "No packs" in capsys.readouterr().out

    def test_list_with_packs(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry(
            {"packs": {"my-pack": {"version": "1.0", "rule_count": 5, "updated": "2024-01-01"}}, "version": "1.0"}
        )
        cmd_list(_make_args())
        assert "my-pack" in capsys.readouterr().out

    def test_list_json(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry({"packs": {"pk": {"version": "2.0"}}, "version": "1.0"})
        cmd_list(_make_args(json=True))
        data = json.loads(capsys.readouterr().out)
        assert "pk" in data


class TestCmdPublish:
    """Tests for cmd_publish()."""

    def test_publish_valid_yaml(self, fake_registry: Path, capsys: Any) -> None:
        src = fake_registry / "rules.yml"
        src.write_text(yaml.dump({"anti_patterns": [{"id": "a1"}]}))
        cmd_publish(_make_args(source=str(src), name="my-rules", version="1.0"))
        assert "Published" in capsys.readouterr().out

    def test_publish_missing_file(self, fake_registry: Path, capsys: Any) -> None:
        cmd_publish(_make_args(source="/nonexistent/file.yml"))
        assert "not found" in capsys.readouterr().out

    def test_publish_invalid_yaml(self, fake_registry: Path, capsys: Any) -> None:
        src = fake_registry / "empty.yml"
        src.write_text("")
        cmd_publish(_make_args(source=str(src)))
        assert "Invalid" in capsys.readouterr().out

    def test_publish_with_tags(self, fake_registry: Path, capsys: Any) -> None:
        src = fake_registry / "rules.yml"
        src.write_text(yaml.dump({"anti_patterns": [{"id": "a1"}]}))
        cmd_publish(_make_args(source=str(src), name="tagged", tags="security,best"))
        assert "Published" in capsys.readouterr().out
        reg = _load_registry()
        assert "security" in reg["packs"]["tagged"]["tags"]


class TestCmdInstall:
    """Tests for cmd_install()."""

    def test_install_pack(self, fake_registry: Path, capsys: Any, tmp_path: Path) -> None:
        # Publish first
        packs = fake_registry / "packs"
        packs.mkdir(exist_ok=True)
        (packs / "test-pack.yml").write_text("anti_patterns: []")
        _save_registry({"packs": {"test-pack": {"version": "1.0"}}, "version": "1.0"})

        cmd_install(_make_args(pack="test-pack", project_dir=str(tmp_path)))
        assert (tmp_path / ".ai-rules" / "test-pack.yml").exists()

    def test_install_missing_pack(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry({"packs": {}, "version": "1.0"})
        cmd_install(_make_args(pack="nonexistent"))
        assert "not found" in capsys.readouterr().out

    def test_install_missing_pack_file(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry({"packs": {"orph": {"version": "1.0"}}, "version": "1.0"})
        cmd_install(_make_args(pack="orph"))
        assert "not found" in capsys.readouterr().out.lower()


class TestCmdSearch:
    """Tests for cmd_search()."""

    def test_search_found(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry(
            {
                "packs": {"sec-rules": {"version": "1.0", "description": "security rules", "tags": ["security"]}},
                "version": "1.0",
            }
        )
        cmd_search(_make_args(query="security"))
        assert "Found" in capsys.readouterr().out

    def test_search_not_found(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry({"packs": {"a": {"version": "1.0", "description": "other", "tags": []}}, "version": "1.0"})
        cmd_search(_make_args(query="zzz"))
        assert "No packs matching" in capsys.readouterr().out

    def test_search_json(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry({"packs": {"my": {"version": "1.0", "description": "mine", "tags": []}}, "version": "1.0"})
        cmd_search(_make_args(query="mine", json=True))
        data = json.loads(capsys.readouterr().out)
        assert "my" in data


class TestCmdInfo:
    """Tests for cmd_info()."""

    def test_info_found(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry({"packs": {"mypack": {"version": "2.0", "description": "test"}}, "version": "1.0"})
        cmd_info(_make_args(pack="mypack"))
        assert "mypack" in capsys.readouterr().out

    def test_info_not_found(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry({"packs": {}, "version": "1.0"})
        cmd_info(_make_args(pack="nope"))
        assert "not found" in capsys.readouterr().out

    def test_info_json(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry({"packs": {"pk": {"version": "3.0"}}, "version": "1.0"})
        cmd_info(_make_args(pack="pk", json=True))
        data = json.loads(capsys.readouterr().out)
        assert "pk" in data


class TestCmdRemove:
    """Tests for cmd_remove()."""

    def test_remove_pack(self, fake_registry: Path, capsys: Any) -> None:
        packs = fake_registry / "packs"
        packs.mkdir(exist_ok=True)
        (packs / "old.yml").write_text("data")
        _save_registry({"packs": {"old": {"version": "1.0"}}, "version": "1.0"})
        cmd_remove(_make_args(pack="old"))
        assert "Removed" in capsys.readouterr().out
        assert not (packs / "old.yml").exists()

    def test_remove_not_found(self, fake_registry: Path, capsys: Any) -> None:
        _save_registry({"packs": {}, "version": "1.0"})
        cmd_remove(_make_args(pack="ghost"))
        assert "not found" in capsys.readouterr().out


class TestMain:
    """Tests for main() CLI entry point."""

    def test_no_command(self, fake_registry: Path, capsys: Any) -> None:
        with patch("sys.argv", ["registry"]):
            ret = main()
        assert ret == 0

    @patch("sys.argv", ["registry", "init"])
    def test_main_init(self, fake_registry: Path) -> None:
        ret = main()
        assert ret == 0
        assert (fake_registry / "registry.json").exists()

    @patch("sys.argv", ["registry", "list"])
    def test_main_list(self, fake_registry: Path) -> None:
        ret = main()
        assert ret == 0

    @patch("tools.scripts.rule_registry.handle_error")
    def test_main_exception(self, mock_handle: MagicMock, fake_registry: Path) -> None:
        with patch("sys.argv", ["registry", "init"]):
            with patch("tools.scripts.rule_registry.init_registry", side_effect=RuntimeError("fail")):
                ret = main()
        assert ret == 1
        mock_handle.assert_called_once()
