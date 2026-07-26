"""Tests for adg_cli.py - AI Developer Governance CLI."""

from __future__ import annotations

import json
from pathlib import Path

from tools.scripts.adg_cli import (
    Issue,
    _severity_rank,
    _simple_yaml_parse,
    check_file,
    detect_language,
    load_rules_for_language,
)


class TestSeverityRank:
    def test_error_is_lowest(self):
        assert _severity_rank("error") < _severity_rank("warning")

    def test_warning_is_lower_than_info(self):
        assert _severity_rank("warning") < _severity_rank("info")

    def test_unknown_is_highest(self):
        assert _severity_rank("unknown") > _severity_rank("info")


class TestDetectLanguage:
    def test_python_project(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        result = detect_language(tmp_path)
        assert result["language"] == "python"
        assert result["confidence"] >= 0.9

    def test_rust_project(self, tmp_path: Path):
        (tmp_path / "Cargo.toml").write_text("[package]\nname='test'\n")
        result = detect_language(tmp_path)
        assert result["language"] == "rust"
        assert result["confidence"] >= 0.9

    def test_typescript_project(self, tmp_path: Path):
        (tmp_path / "tsconfig.json").write_text("{}")
        result = detect_language(tmp_path)
        assert result["language"] == "typescript"

    def test_go_project(self, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module test\n")
        result = detect_language(tmp_path)
        assert result["language"] == "go"

    def test_java_project(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        result = detect_language(tmp_path)
        assert result["language"] == "java"

    def test_extension_counting(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "b.py").write_text("pass")
        (tmp_path / "c.rs").write_text("fn main() {}")
        result = detect_language(tmp_path)
        assert result["language"] == "python"
        assert result["confidence"] > 0.5

    def test_empty_directory(self, tmp_path: Path):
        result = detect_language(tmp_path)
        assert result["language"] == "unknown"
        assert result["confidence"] == 0.0


class TestLoadRules:
    def test_load_python_rules(self):
        rules = load_rules_for_language("python")
        assert "anti_patterns" in rules
        assert len(rules["anti_patterns"]) > 0
        # Should have bare except rule
        ids = [r.get("id") for r in rules["anti_patterns"]]
        assert "py-bare-except" in ids

    def test_load_rust_rules(self):
        rules = load_rules_for_language("rust")
        assert "anti_patterns" in rules
        ids = [r.get("id") for r in rules["anti_patterns"]]
        assert "rs-unwrap" in ids

    def test_load_unknown_language(self):
        rules = load_rules_for_language("nonexistent")
        assert "anti_patterns" in rules
        # Should still have security rules
        assert len(rules["anti_patterns"]) > 0

    def test_security_rules_included(self):
        rules = load_rules_for_language("python")
        ids = [r.get("id") for r in rules["anti_patterns"]]
        assert "common-hardcoded-secret" in ids


class TestCheckFile:
    def test_bare_except_detected(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("try:\n    pass\nexcept:\n    pass\n")
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules, "error")
        rule_ids = [i.rule_id for i in issues]
        assert "py-bare-except" in rule_ids

    def test_hardcoded_secret_detected(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text('password = "secret123"\n')
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules, "error")
        rule_ids = [i.rule_id for i in issues]
        assert "py-hardcoded-secret" in rule_ids or "common-hardcoded-secret" in rule_ids

    def test_clean_code_no_errors(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "def process(items: list[str]) -> dict[str, int]:\n    return {i: len(i) for i in items}\n"
        )
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules, "error")
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) == 0

    def test_severity_filter(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("try:\n    pass\nexcept:\n    pass\n")
        rules = load_rules_for_language("python")
        # Only errors
        issues = check_file(test_file, rules, "error")
        assert all(i.severity == "error" for i in issues)

    def test_nonexistent_file(self, tmp_path: Path):
        test_file = tmp_path / "nonexistent.py"
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules)
        assert issues == []

    def test_empty_file(self, tmp_path: Path):
        test_file = tmp_path / "empty.py"
        test_file.write_text("")
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules)
        assert issues == []


class TestFrameworkDetection:
    def test_django_detection_manage_py(self, tmp_path: Path):
        """Test Django detection from manage.py."""
        # Create manage.py with Django content
        manage_py = tmp_path / "manage.py"
        manage_py.write_text(
            "#!/usr/bin/env python\n"
            "import os\n"
            "import sys\n"
            'os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")\n'
        )

        # Create views.py to make it a Python project
        views_py = tmp_path / "views.py"
        views_py.write_text("from django.http import JsonResponse\n")

        result = detect_language(tmp_path)
        assert result["framework"] == "django"

    def test_django_detection_requirements(self, tmp_path: Path):
        """Test Django detection from requirements.txt."""
        # Create requirements.txt with Django
        req_txt = tmp_path / "requirements.txt"
        req_txt.write_text("Django==4.2\n")

        # Create a Python file
        py_file = tmp_path / "app.py"
        py_file.write_text("import django\n")

        result = detect_language(tmp_path)
        assert result["framework"] == "django"

    def test_fastapi_detection(self, tmp_path: Path):
        """Test FastAPI detection from requirements.txt."""
        # Create requirements.txt with FastAPI
        req_txt = tmp_path / "requirements.txt"
        req_txt.write_text("fastapi==0.104.1\n")

        # Create a Python file
        py_file = tmp_path / "main.py"
        py_file.write_text("from fastapi import FastAPI\n")

        result = detect_language(tmp_path)
        assert result["framework"] == "fastapi"

    def test_react_detection(self, tmp_path: Path):
        """Test React detection from package.json."""
        # Create package.json with React
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text(
            json.dumps({"name": "my-react-app", "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"}})
        )

        # Create a JS file
        js_file = tmp_path / "index.js"
        js_file.write_text('import React from "react";\n')

        result = detect_language(tmp_path)
        assert result["framework"] == "react"

    def test_vue_detection(self, tmp_path: Path):
        """Test Vue detection from package.json."""
        # Create package.json with Vue
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text(json.dumps({"name": "my-vue-app", "dependencies": {"vue": "^3.3.0"}}))

        # Create a JS file
        js_file = tmp_path / "main.js"
        js_file.write_text('import { createApp } from "vue";\n')

        result = detect_language(tmp_path)
        assert result["framework"] == "vue"

    def test_spring_detection(self, tmp_path: Path):
        """Test Spring detection from pom.xml."""
        # Create pom.xml with Spring
        pom_xml = tmp_path / "pom.xml"
        pom_xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<project>\n"
            "  <parent>\n"
            "    <groupId>org.springframework.boot</groupId>\n"
            "    <artifactId>spring-boot-starter-parent</artifactId>\n"
            "  </parent>\n"
            "</project>\n"
        )

        # Create a Java file
        java_file = tmp_path / "Application.java"
        java_file.write_text("import org.springframework.boot.SpringApplication;\n")

        result = detect_language(tmp_path)
        assert result["framework"] == "spring"

    def test_actix_detection(self, tmp_path: Path):
        """Test Actix detection from Cargo.toml."""
        # Create Cargo.toml with actix
        cargo_toml = tmp_path / "Cargo.toml"
        cargo_toml.write_text('[package]\nname = "my-app"\n\n[dependencies]\nactix-web = "4"\n')

        # Create a Rust file
        rs_file = tmp_path / "main.rs"
        rs_file.write_text("use actix_web::{web, App, HttpServer};\n")

        result = detect_language(tmp_path)
        assert result["framework"] == "actix"

    def test_express_detection(self, tmp_path: Path):
        """Test Express detection from package.json."""
        # Create package.json with express
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text(json.dumps({"name": "express-app", "dependencies": {"express": "^4.18.2"}}))

        # Create a JS file
        js_file = tmp_path / "app.js"
        js_file.write_text("const express = require('express');\n")

        result = detect_language(tmp_path)
        assert result["framework"] == "express"

    def test_nextjs_detection(self, tmp_path: Path):
        """Test Next.js detection from package.json."""
        # Create package.json with next
        pkg_json = tmp_path / "package.json"
        pkg_json.write_text(json.dumps({"name": "nextjs-app", "dependencies": {"next": "14.0.0", "react": "^18.2.0"}}))

        result = detect_language(tmp_path)
        assert result["framework"] == "nextjs"

    def test_springboot_detection(self, tmp_path: Path):
        """Test Spring Boot detection from pom.xml."""
        # Create pom.xml with Spring Boot
        pom_xml = tmp_path / "pom.xml"
        pom_xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<project>\n"
            "  <parent>\n"
            "    <groupId>org.springframework.boot</groupId>\n"
            "    <artifactId>spring-boot-starter-parent</artifactId>\n"
            "  </parent>\n"
            "</project>\n"
        )

        result = detect_language(tmp_path)
        assert result["framework"] == "spring"


class TestSimpleYamlParse:
    def test_parse_anti_patterns(self, tmp_path: Path):
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text(
            "language: python\n"
            "anti_patterns:\n"
            "- id: test-rule\n"
            "  name: Test Rule\n"
            "  severity: error\n"
            "  pattern: 'test\\s+pattern'\n"
            "  message: Test message\n"
        )
        result = _simple_yaml_parse(yaml_file)
        assert result["language"] == "python"
        assert len(result["anti_patterns"]) == 1
        assert result["anti_patterns"][0]["id"] == "test-rule"


class TestIssue:
    def test_to_dict(self):
        issue = Issue(
            rule_id="test",
            severity="error",
            category="test",
            file="test.py",
            line=1,
            column=1,
            message="test message",
            fix_hint="fix it",
        )
        d = issue.to_dict()
        assert d["rule_id"] == "test"
        assert d["severity"] == "error"
        assert d["line"] == 1
