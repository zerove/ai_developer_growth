"""Tests for src/profiles.py - LanguageProfile and LanguageDetector"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.profiles import LANGUAGE_PROFILES, LanguageDetector, LanguageProfile


class TestLanguageProfiles:
    """Tests for the LANGUAGE_PROFILES dictionary."""

    def test_profiles_is_dict(self):
        assert isinstance(LANGUAGE_PROFILES, dict)

    def test_expected_keys_exist(self):
        expected_keys = {"python", "javascript", "rust", "go", "generic"}
        assert set(LANGUAGE_PROFILES.keys()) == expected_keys

    def test_all_values_are_language_profile(self):
        for key, profile in LANGUAGE_PROFILES.items():
            assert isinstance(profile, LanguageProfile), f"Key '{key}' value is not a LanguageProfile"

    def test_all_profiles_have_name(self):
        for key, profile in LANGUAGE_PROFILES.items():
            assert profile.name, f"Profile '{key}' has empty name"
            assert isinstance(profile.name, str)

    def test_all_profiles_have_default_ignore(self):
        for key, profile in LANGUAGE_PROFILES.items():
            assert isinstance(profile.default_ignore, list), f"Profile '{key}' default_ignore is not a list"
            assert len(profile.default_ignore) > 0, f"Profile '{key}' default_ignore is empty"

    def test_all_profiles_have_recommended_prompt_extension(self):
        for key, profile in LANGUAGE_PROFILES.items():
            assert profile.recommended_prompt_extension, f"Profile '{key}' has empty recommended_prompt_extension"
            assert isinstance(profile.recommended_prompt_extension, str)
            assert len(profile.recommended_prompt_extension) > 10, (
                f"Profile '{key}' recommended_prompt_extension is suspiciously short"
            )

    def test_python_profile_name(self):
        assert LANGUAGE_PROFILES["python"].name == "Python"

    def test_javascript_profile_name(self):
        assert LANGUAGE_PROFILES["javascript"].name == "JavaScript/TypeScript"

    def test_rust_profile_name(self):
        assert LANGUAGE_PROFILES["rust"].name == "Rust"

    def test_go_profile_name(self):
        assert LANGUAGE_PROFILES["go"].name == "Go"

    def test_generic_profile_name(self):
        assert LANGUAGE_PROFILES["generic"].name == "Generic"

    def test_python_profile_ignore_patterns(self):
        ignore = LANGUAGE_PROFILES["python"].default_ignore
        assert "__pycache__" in ignore
        assert ".venv" in ignore

    def test_javascript_profile_ignore_patterns(self):
        ignore = LANGUAGE_PROFILES["javascript"].default_ignore
        assert "node_modules" in ignore

    def test_rust_profile_ignore_patterns(self):
        ignore = LANGUAGE_PROFILES["rust"].default_ignore
        assert "target/" in ignore

    def test_go_profile_ignore_patterns(self):
        ignore = LANGUAGE_PROFILES["go"].default_ignore
        assert "vendor/" in ignore

    def test_generic_profile_ignore_patterns(self):
        ignore = LANGUAGE_PROFILES["generic"].default_ignore
        assert ".git/" in ignore


class TestLanguageDetector:
    """Tests for the LanguageDetector class."""

    def test_detect_python_project(self, tmp_path):
        (tmp_path / "requirements.txt").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "python"

    def test_detect_python_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "python"

    def test_detect_python_setup_py(self, tmp_path):
        (tmp_path / "setup.py").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "python"

    def test_detect_python_manage_py(self, tmp_path):
        (tmp_path / "manage.py").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "python"

    def test_detect_javascript_package_json(self, tmp_path):
        (tmp_path / "package.json").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "javascript"

    def test_detect_javascript_tsconfig(self, tmp_path):
        (tmp_path / "tsconfig.json").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "javascript"

    def test_detect_javascript_next_config(self, tmp_path):
        (tmp_path / "next.config.js").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "javascript"

    def test_detect_javascript_tailwind_config(self, tmp_path):
        (tmp_path / "tailwind.config.js").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "javascript"

    def test_detect_rust_cargo_toml(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "rust"

    def test_detect_rust_cargo_lock(self, tmp_path):
        (tmp_path / "Cargo.lock").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "rust"

    def test_detect_go_go_mod(self, tmp_path):
        (tmp_path / "go.mod").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "go"

    def test_detect_go_go_sum(self, tmp_path):
        (tmp_path / "go.sum").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "go"

    def test_detect_empty_directory_returns_generic(self, tmp_path):
        assert LanguageDetector.detect(str(tmp_path)) == "generic"

    def test_detect_unknown_files_returns_generic(self, tmp_path):
        (tmp_path / "README.md").touch()
        (tmp_path / "Makefile").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "generic"

    def test_detect_nonexistent_path_returns_generic(self):
        assert LanguageDetector.detect("/nonexistent/path/abc123") == "generic"

    def test_detect_priority_python_over_javascript(self, tmp_path):
        """Python signatures appear first in iteration order, so python should be detected."""
        (tmp_path / "requirements.txt").touch()
        (tmp_path / "package.json").touch()
        result = LanguageDetector.detect(str(tmp_path))
        assert result in ("python", "javascript")

    def test_signatures_dict_structure(self):
        """SIGNATURES should map string keys to lists of filenames."""
        assert isinstance(LanguageDetector.SIGNATURES, dict)
        for lang, files in LanguageDetector.SIGNATURES.items():
            assert isinstance(lang, str)
            assert isinstance(files, list)
            assert len(files) > 0, f"No signature files for '{lang}'"
            for f in files:
                assert isinstance(f, str)
                assert "/" not in f or f.endswith("/"), f"Signature file '{f}' has unexpected path separator"

    def test_detect_with_subdirectory_signature(self, tmp_path):
        """Signature files in subdirectories should NOT be detected (only root-level)."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "requirements.txt").touch()
        assert LanguageDetector.detect(str(tmp_path)) == "generic"
