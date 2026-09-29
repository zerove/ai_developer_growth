"""Tests for rules/cli.py (0% → target 90%)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.rules_loader.cli import add_common_args, cli_main, output_results


class TestAddCommonArgs:
    """Tests for add_common_args()."""

    def test_adds_json_flag(self) -> None:
        parser = argparse.ArgumentParser()
        add_common_args(parser)
        args = parser.parse_args(["--json"])
        assert args.json_output is True

    def test_adds_format(self) -> None:
        parser = argparse.ArgumentParser()
        add_common_args(parser)
        args = parser.parse_args(["--format", "json"])
        assert args.format == "json"

    def test_format_default(self) -> None:
        parser = argparse.ArgumentParser()
        add_common_args(parser)
        args = parser.parse_args([])
        assert args.format == "text"

    def test_adds_verbose(self) -> None:
        parser = argparse.ArgumentParser()
        add_common_args(parser)
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True

    def test_adds_output(self, tmp_path: Path) -> None:
        parser = argparse.ArgumentParser()
        add_common_args(parser)
        args = parser.parse_args(["-o", str(tmp_path / "out.txt")])
        assert args.output == tmp_path / "out.txt"

    def test_all_defaults(self) -> None:
        parser = argparse.ArgumentParser()
        add_common_args(parser)
        args = parser.parse_args([])
        assert args.json_output is False
        assert args.format == "text"
        assert args.verbose is False
        assert args.output is None

    def test_format_choices(self) -> None:
        parser = argparse.ArgumentParser()
        add_common_args(parser)
        for fmt in ("text", "json", "html", "csv"):
            args = parser.parse_args(["--format", fmt])
            assert args.format == fmt

    def test_invalid_format_rejected(self) -> None:
        parser = argparse.ArgumentParser()
        add_common_args(parser)
        with pytest.raises(SystemExit):
            parser.parse_args(["--format", "xml"])


class TestOutputResults:
    """Tests for output_results()."""

    def test_text_string(self, capsys: Any) -> None:
        ret = output_results("hello world")
        assert ret == 0
        assert capsys.readouterr().out.strip() == "hello world"

    def test_json_list(self, capsys: Any) -> None:
        ret = output_results([1, 2, 3], fmt="json")
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert data == [1, 2, 3]

    def test_json_dict(self, capsys: Any) -> None:
        ret = output_results({"key": "val"}, fmt="json")
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert data["key"] == "val"

    def test_json_flag_overrides_format(self, capsys: Any) -> None:
        ret = output_results({"a": 1}, json_output=True)
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert data["a"] == 1

    def test_formatter_called(self, capsys: Any) -> None:
        def formatter(data: object, verbose: bool) -> str:
            return f"formatted: {data} (verbose={verbose})"

        ret = output_results("test", formatter=formatter, verbose=True)
        assert ret == 0
        assert "formatted: test (verbose=True)" in capsys.readouterr().out

    def test_dict_to_str_fallback(self, capsys: Any) -> None:
        ret = output_results({"a": 1})
        assert ret == 0
        assert "{'a': 1}" in capsys.readouterr().out

    def test_output_to_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "sub" / "output.txt"
        ret = output_results("file content", output_file=out_file)
        assert ret == 0
        assert out_file.read_text() == "file content"

    def test_to_dict_object(self, capsys: Any) -> None:
        class MyObj:
            def to_dict(self) -> dict[str, Any]:
                return {"x": 42}

        ret = output_results(MyObj(), fmt="json")
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert data["x"] == 42

    def test_list_with_to_dict_objects(self, capsys: Any) -> None:
        class MyObj:
            def __init__(self, v: int) -> None:
                self.v = v

            def to_dict(self) -> dict[str, Any]:
                return {"v": self.v}

        ret = output_results([MyObj(1), MyObj(2)], fmt="json")
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert data == [{"v": 1}, {"v": 2}]

    def test_verbose_flag_passed(self, capsys: Any) -> None:
        def formatter(data: object, verbose: bool) -> str:
            return "yes" if verbose else "no"

        output_results("x", formatter=formatter, verbose=True)
        assert capsys.readouterr().out.strip() == "yes"


class TestCliMain:
    """Tests for cli_main()."""

    def test_calls_main_fn(self) -> None:
        main_fn = MagicMock(return_value=0)
        with pytest.raises(SystemExit) as exc_info:
            cli_main(main_fn)
        assert exc_info.value.code == 0
        main_fn.assert_called_once()

    def test_nonzero_exit(self) -> None:
        main_fn = MagicMock(return_value=1)
        with pytest.raises(SystemExit) as exc_info:
            cli_main(main_fn)
        assert exc_info.value.code == 1

    @patch("tools.scripts.rules_loader.cli.handle_error")
    def test_exception_calls_handle_error(self, mock_handle: MagicMock) -> None:
        main_fn = MagicMock(side_effect=ValueError("boom"))
        cli_main(main_fn, script_name="test")
        mock_handle.assert_called_once()
        assert mock_handle.call_args[1]["script"] == "test"

    @patch("tools.scripts.rules_loader.cli.handle_error")
    def test_keyboard_interrupt(self, mock_handle: MagicMock, capsys: Any) -> None:
        main_fn = MagicMock(side_effect=KeyboardInterrupt)
        with pytest.raises(SystemExit) as exc_info:
            cli_main(main_fn)
        assert exc_info.value.code == 130
        assert "Interrupted" in capsys.readouterr().err

    @patch("tools.scripts.rules_loader.cli.handle_error")
    def test_script_name_from_argv(self, mock_handle: MagicMock) -> None:
        main_fn = MagicMock(side_effect=RuntimeError("err"))
        with patch("sys.argv", ["/path/to/my_script.py"]):
            cli_main(main_fn)
        mock_handle.assert_called_once()
        assert mock_handle.call_args[1]["script"] == "my_script"
