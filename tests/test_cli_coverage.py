#!/usr/bin/env python3
"""
CLI 主函数测试 (in-process 方式，提升覆盖率)

覆盖 ai_quality_gate.py, check_ai_annotation.py, validate_agent_definition.py
check_metadata.py 的 main() 函数。
"""

from pathlib import Path
from unittest.mock import patch

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent


# ==============================================================================
# ai_quality_gate.py CLI 测试
# ==============================================================================


class TestQualityGateCLI:
    """ai_quality_gate.py CLI 测试"""

    def test_main_no_args(self, capsys):
        """无参数运行"""
        with patch("sys.argv", ["ai_quality_gate"]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "AI 代码质量门禁" in out

    def test_main_full(self, capsys):
        """--full 参数"""
        with patch("sys.argv", ["ai_quality_gate", "--full"]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "annotation, security, type, error, structure" in out

    def test_main_check_annotation(self, capsys):
        """--check-annotation"""
        with patch("sys.argv", ["ai_quality_gate", "--check-annotation"]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "annotation" in out

    def test_main_check_security(self, capsys):
        """--check-security"""
        with patch("sys.argv", ["ai_quality_gate", "--check-security"]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "security" in out

    def test_main_check_type(self, capsys):
        """--check-type"""
        with patch("sys.argv", ["ai_quality_gate", "--check-type"]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "type" in out

    def test_main_check_error(self, capsys):
        """--check-error"""
        with patch("sys.argv", ["ai_quality_gate", "--check-error"]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "error" in out

    def test_main_check_structure(self, capsys):
        """--check-structure"""
        with patch("sys.argv", ["ai_quality_gate", "--check-structure"]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "structure" in out

    def test_main_check_patterns(self, capsys):
        """--check-patterns"""
        with patch("sys.argv", ["ai_quality_gate", "--check-patterns"]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "annotation, security, type, error, structure" in out

    def test_main_file_check(self, capsys, tmp_path):
        """--file"""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")
        with patch("sys.argv", ["ai_quality_gate", "--file", str(test_file)]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "test.py" in out

    def test_main_path_check(self, capsys, tmp_path):
        """--path"""
        (tmp_path / "a.py").write_text("x = 1\n")
        with patch("sys.argv", ["ai_quality_gate", "--path", str(tmp_path)]):
            from tools.scripts.ai_quality_gate import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "a.py" in out


# ==============================================================================
# check_ai_annotation.py CLI 测试
# ==============================================================================


class TestAnnotationCLI:
    """check_ai_annotation.py CLI 测试"""

    def test_main_no_args(self, capsys):
        """无参数运行"""
        with patch("sys.argv", ["check_ai_annotation"]):
            from tools.scripts.check_ai_annotation import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "AI 代码标注检查" in out

    def test_main_file_check(self, capsys, tmp_path):
        """--file 检查已标注文件"""
        test_file = tmp_path / "clean.py"
        test_file.write_text("# [AI-GEN] Generated by AI\nx = 1\n")
        with patch("sys.argv", ["check_ai_annotation", "--file", str(test_file)]):
            from tools.scripts.check_ai_annotation import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "✅" in out

    def test_main_file_missing_annotation(self, capsys, tmp_path):
        """--file 缺少标注"""
        test_file = tmp_path / "unmarked.py"
        test_file.write_text("# AI-generated code\ndef foo(): pass\n")
        with patch("sys.argv", ["check_ai_annotation", "--file", str(test_file)]):
            from tools.scripts.check_ai_annotation import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "❌" in out

    def test_main_strict_mode(self, capsys, tmp_path):
        """--strict 模式"""
        test_file = tmp_path / "no_annot.py"
        test_file.write_text("x = 1\n")
        with patch(
            "sys.argv", ["check_ai_annotation", "--file", str(test_file), "--strict"]
        ):
            from tools.scripts.check_ai_annotation import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "⚠️" in out

    def test_main_fix_mode(self, capsys, tmp_path):
        """--fix 自动添加标注"""
        test_file = tmp_path / "to_fix.py"
        test_file.write_text("x = 1\n")
        # Ensure we run main with proper arguments and capture the full output
        with patch(
            "sys.argv",
            [
                "check_ai_annotation",
                "--file",
                str(test_file),
                "--fix",
                "--model",
                "test",
            ],
        ):
            from tools.scripts.check_ai_annotation import main

            try:
                main()
            except SystemExit:
                pass

        # Explicitly capture stdout
        out = capsys.readouterr().out
        # Debugging: Print out to verify content
        print(f"DEBUG_OUT: {out}")
        assert "🔧" in out
        assert "# [AI-GEN]" in test_file.read_text()

    def test_main_fix_already_annotated(self, capsys, tmp_path):
        """--fix 已标注文件不重复"""
        test_file = tmp_path / "already.py"
        test_file.write_text("# [AI-GEN] Generated by AI\nx = 1\n")
        with patch(
            "sys.argv", ["check_ai_annotation", "--file", str(test_file), "--fix"]
        ):
            from tools.scripts.check_ai_annotation import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "🔧" not in out

    def test_main_path_check(self, capsys, tmp_path):
        """--path 检查目录"""
        (tmp_path / "ok.py").write_text("# [AI-GEN] Generated by AI\nx = 1\n")
        with patch("sys.argv", ["check_ai_annotation", "--path", str(tmp_path)]):
            from tools.scripts.check_ai_annotation import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "ok.py" in out


# ==============================================================================
# validate_agent_definition.py CLI 测试
# ==============================================================================


class TestValidateAgentCLI:
    """validate_agent_definition.py CLI 测试"""

    def test_main_default_path(self, capsys):
        """默认 agents/ 目录"""
        with patch("sys.argv", ["validate_agent_definition"]):
            from tools.scripts.validate_agent_definition import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "Agent 定义验证" in out

    def test_main_file_check(self, capsys):
        """--file 验证"""
        agent_file = ROOT / "agents" / "knowledge-curator.md"
        if agent_file.exists():
            with patch(
                "sys.argv", ["validate_agent_definition", "--file", str(agent_file)]
            ):
                from tools.scripts.validate_agent_definition import main

                try:
                    main()
                except SystemExit:
                    pass
            out = capsys.readouterr().out
            assert "✅" in out or "❌" in out

    def test_main_custom_path(self, capsys, tmp_path):
        """--path 自定义目录"""
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()
        agent_file = agent_dir / "test-agent.md"
        agent_file.write_text(
            "---\nname: test-agent\nformat: md\n"
            "描述: A test agent for validation\n---\n"
            "## agent: test-agent (A test agent for validation)\n\n"
            "### 工具\nbash\n\n"
            "### 约束\nMust follow all rules and regulations strictly\n\n"
            "### 指令\nRun tools/scripts/test.py\n"
        )
        with patch("sys.argv", ["validate_agent_definition", "--path", str(agent_dir)]):
            from tools.scripts.validate_agent_definition import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "Agent 定义验证" in out

    def test_main_invalid_file(self, capsys, tmp_path):
        """验证无效文件"""
        bad_file = tmp_path / "bad.md"
        bad_file.write_text("# Just a random file\nNo agent definition here\n")
        with patch("sys.argv", ["validate_agent_definition", "--file", str(bad_file)]):
            from tools.scripts.validate_agent_definition import main

            try:
                main()
            except SystemExit:
                pass
        out = capsys.readouterr().out
        assert "❌" in out


# ==============================================================================
# check_metadata.py CLI 测试
# ==============================================================================


class TestCheckMetadataCLI:
    """check_metadata.py CLI 测试"""

    def test_main_runs(self, capsys):
        """main 函数正常运行"""
        from tools.scripts.check_metadata import main

        main()
        out = capsys.readouterr().out
        assert "Scanning" in out or "All files" in out

    def test_main_with_no_docs_dir(self, capsys, tmp_path):
        """docs 目录不存在时"""
        original_cwd = Path.cwd()
        try:
            import os

            os.chdir(tmp_path)
            from tools.scripts.check_metadata import main

            main()
            out = capsys.readouterr().out
            assert "Error" in out
        finally:
            os.chdir(original_cwd)
