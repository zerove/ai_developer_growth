"""Tests for cmd_recommend: AI-powered rule recommendations.

覆盖 tools/scripts/adg_cli/commands/cmd/cmd_recommend.py 5 个函数：
- _apply_recommendations
- _build_new_rules
- _load_existing_rules
- _save_rules
- cmd_recommend (主入口)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts.adg_cli.commands.cmd.cmd_recommend import (
    _apply_recommendations,
    _build_new_rules,
    _load_existing_rules,
    _save_rules,
    cmd_recommend,
)


@pytest.fixture
def sample_recommendation() -> dict:
    """单个推荐项的样本数据。"""
    return {
        "rule_id": "py-eval-exec",
        "name": "Avoid eval/exec",
        "severity": "error",
        "category": "security",
        "reason": "eval() is dangerous",
        "affected_files": 3,
        "example": {"file": "a.py", "line": 5, "code": "eval(x)"},
    }


@pytest.fixture
def sample_result(sample_recommendation: dict) -> dict:
    """完整的 recommend_rules 输出。"""
    return {
        "language": "python",
        "framework": None,
        "files_scanned": 5,
        "files_with_issues": 2,
        "total_recommendations": 1,
        "recommendations": [sample_recommendation],
    }


class TestBuildNewRules:
    """_build_new_rules: 从推荐构建新规则列表。"""

    def test_adds_new_rule_when_id_not_in_existing(
        self, sample_recommendation: dict
    ) -> None:
        """rule_id 不在 existing_ids 中时新增。"""
        result = _build_new_rules(
            {"recommendations": [sample_recommendation]}, set()
        )
        assert len(result) == 1
        assert result[0]["id"] == "py-eval-exec"
        assert result[0]["severity"] == "error"
        assert "Auto-generated" in result[0]["fix_hint"]

    def test_skips_existing_rule(
        self, sample_recommendation: dict
    ) -> None:
        """rule_id 已存在时跳过。"""
        result = _build_new_rules(
            {"recommendations": [sample_recommendation]},
            {"py-eval-exec"},
        )
        assert result == []

    def test_returns_empty_for_no_recommendations(self) -> None:
        """空推荐列表返回 []。"""
        result = _build_new_rules({"recommendations": []}, set())
        assert result == []


class TestLoadExistingRules:
    """_load_existing_rules: 加载已有 rules.yml。"""

    def test_returns_empty_when_file_not_exists(self, tmp_path: Path) -> None:
        """rules.yml 不存在时返回默认空结构。"""
        rules_file = tmp_path / "rules.yml"
        result = _load_existing_rules(rules_file)
        assert result == {"anti_patterns": []}

    def test_loads_existing_rules(self, tmp_path: Path) -> None:
        """rules.yml 存在时正确加载。"""
        import yaml

        rules_file = tmp_path / "rules.yml"
        rules_file.write_text(yaml.dump({"anti_patterns": [{"id": "x"}], "extra": "data"}))
        result = _load_existing_rules(rules_file)
        assert len(result["anti_patterns"]) == 1
        assert result["anti_patterns"][0]["id"] == "x"
        assert result["extra"] == "data"

    def test_handles_invalid_yaml_gracefully(self, tmp_path: Path) -> None:
        """无效 YAML 时回退到默认空结构。"""
        rules_file = tmp_path / "rules.yml"
        rules_file.write_text(":\n  - invalid: [unclosed")
        result = _load_existing_rules(rules_file)
        assert result == {"anti_patterns": []}


class TestSaveRules:
    """_save_rules: 保存 rules.yml。"""

    def test_saves_with_metadata(self, tmp_path: Path) -> None:
        """保存时自动加 config_version + source 元数据。"""
        import yaml

        rules_file = tmp_path / "rules.yml"
        rules = {"anti_patterns": [{"id": "test", "severity": "warning"}]}
        _save_rules(rules_file, rules)
        loaded = yaml.safe_load(rules_file.read_text())
        assert loaded["config_version"] == "1.0"
        assert loaded["source"] == "auto-generated-by-recommend"
        assert len(loaded["anti_patterns"]) == 1

    def test_creates_file(self, tmp_path: Path) -> None:
        """不存在的文件会被创建。"""
        rules_file = tmp_path / "rules.yml"
        _save_rules(rules_file, {"anti_patterns": []})
        assert rules_file.exists()


class TestApplyRecommendations:
    """_apply_recommendations: 写推荐到 .adg/rules.yml。"""

    def test_creates_adg_dir_and_rules_file(
        self, tmp_path: Path, sample_result: dict
    ) -> None:
        """首次应用时创建 .adg/rules.yml。"""
        import yaml

        result = _apply_recommendations(tmp_path, sample_result)
        assert result == 0
        rules_file = tmp_path / ".adg" / "rules.yml"
        assert rules_file.exists()
        loaded = yaml.safe_load(rules_file.read_text())
        assert len(loaded["anti_patterns"]) == 1

    def test_no_new_rules_when_all_exist(
        self, tmp_path: Path, sample_result: dict, capsys
    ) -> None:
        """所有推荐都已存在时不写文件。"""
        import yaml

        # 预先写入已有规则
        adg_dir = tmp_path / ".adg"
        adg_dir.mkdir()
        rules_file = adg_dir / "rules.yml"
        rules_file.write_text(
            yaml.dump({"anti_patterns": [{"id": "py-eval-exec", "severity": "error"}]})
        )
        result = _apply_recommendations(tmp_path, sample_result)
        assert result == 0
        captured = capsys.readouterr()
        assert "No new rules to apply" in captured.out

    def test_appends_to_existing_rules(
        self, tmp_path: Path, sample_result: dict
    ) -> None:
        """追加新规则到已有 rules.yml。"""
        import yaml

        adg_dir = tmp_path / ".adg"
        adg_dir.mkdir()
        rules_file = adg_dir / "rules.yml"
        rules_file.write_text(
            yaml.dump({"anti_patterns": [{"id": "existing", "severity": "info"}]})
        )
        _apply_recommendations(tmp_path, sample_result)
        loaded = yaml.safe_load(rules_file.read_text())
        ids = {r["id"] for r in loaded["anti_patterns"]}
        assert "existing" in ids
        assert "py-eval-exec" in ids


class TestCmdRecommend:
    """cmd_recommend: 主入口（AI 推荐 CLI 命令）。"""

    def test_json_output(self, tmp_path: Path, sample_result: dict, capsys) -> None:
        """--json 标志输出 JSON 格式。"""
        (tmp_path / "a.py").write_text("x = 1\n")
        args = argparse.Namespace(
            path=str(tmp_path),
            max=10,
            json=True,
            apply=False,
        )
        with patch(
            "tools.ai_recommender.recommend_rules",
            return_value=sample_result,
        ):
            result = cmd_recommend(args)
        assert result == 0
        captured = capsys.readouterr()
        # 输出是合法 JSON
        loaded = json.loads(captured.out)
        assert loaded["language"] == "python"
        assert loaded["total_recommendations"] == 1

    def test_text_output(self, tmp_path: Path, sample_result: dict, capsys) -> None:
        """无 --json 时输出文本格式。"""
        (tmp_path / "a.py").write_text("x = 1\n")
        args = argparse.Namespace(
            path=str(tmp_path),
            max=10,
            json=False,
            apply=False,
        )
        with patch(
            "tools.ai_recommender.recommend_rules",
            return_value=sample_result,
        ):
            result = cmd_recommend(args)
        assert result == 0
        captured = capsys.readouterr()
        # 不应是 JSON
        assert not captured.out.strip().startswith("{")

    def test_apply_flag_creates_rules_file(
        self, tmp_path: Path, sample_result: dict
    ) -> None:
        """--apply 标志自动写入 .adg/rules.yml。"""
        (tmp_path / "a.py").write_text("x = 1\n")
        args = argparse.Namespace(
            path=str(tmp_path),
            max=10,
            json=False,
            apply=True,
        )
        with patch(
            "tools.ai_recommender.recommend_rules",
            return_value=sample_result,
        ):
            result = cmd_recommend(args)
        assert result == 0
        rules_file = tmp_path / ".adg" / "rules.yml"
        assert rules_file.exists()
