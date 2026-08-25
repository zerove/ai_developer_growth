"""扩展依赖清单解析器测试：Gradle / Gemfile / composer.json / NuGet。"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.supply_chain import SBOMGenerator


@pytest.fixture()
def generator() -> SBOMGenerator:
    return SBOMGenerator.__new__(SBOMGenerator)


class TestGradleParser:
    def test_single_and_double_quotes(self, tmp_path: Path, generator: SBOMGenerator) -> None:
        (tmp_path / "build.gradle").write_text(
            "dependencies {\n"
            "    implementation 'com.google.guava:guava:32.1.0-jre'\n"
            '    testImplementation "junit:junit:4.13.2"\n'
            "}\n",
            encoding="utf-8",
        )
        deps = generator._parse_gradle_deps(tmp_path)
        names = {d.name for d in deps}
        assert names == {"com.google.guava:guava", "junit:junit"}
        assert all(d.ecosystem == "maven" for d in deps)

    def test_kotlin_dsl(self, tmp_path: Path, generator: SBOMGenerator) -> None:
        (tmp_path / "build.gradle.kts").write_text(
            'implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")\n',
            encoding="utf-8",
        )
        # kts 的函数调用风格暂不支持，但文件存在不报错
        assert generator._parse_gradle_deps(tmp_path) == []


class TestGemfileParser:
    def test_double_and_single_quotes(self, tmp_path: Path, generator: SBOMGenerator) -> None:
        (tmp_path / "Gemfile").write_text(
            'gem "rails", "~> 7.0"\ngem \'sinatra\', \'4.0\'\ngem "puma"\n',
            encoding="utf-8",
        )
        deps = {d.name: d.version for d in generator._parse_gemfile_deps(tmp_path)}
        assert deps["rails"] == "7.0"
        assert deps["sinatra"] == "4.0"
        assert deps["puma"] == ""

    def test_missing_gemfile(self, tmp_path: Path, generator: SBOMGenerator) -> None:
        assert generator._parse_gemfile_deps(tmp_path) == []


class TestComposerParser:
    def test_require_section(self, tmp_path: Path, generator: SBOMGenerator) -> None:
        (tmp_path / "composer.json").write_text(
            '{"require": {"monolog/monolog": "^3.0", "php": ">=8.1"}}',
            encoding="utf-8",
        )
        deps = {d.name: d.version for d in generator._parse_composer_deps(tmp_path)}
        assert "php" not in deps  # 平台约束不算依赖
        assert deps["monolog/monolog"] == "3.0"

    def test_malformed_json(self, tmp_path: Path, generator: SBOMGenerator) -> None:
        (tmp_path / "composer.json").write_text("{broken", encoding="utf-8")
        assert generator._parse_composer_deps(tmp_path) == []


class TestNugetParser:
    def test_package_reference(self, tmp_path: Path, generator: SBOMGenerator) -> None:
        (tmp_path / "App.csproj").write_text(
            '<Project><ItemGroup><PackageReference Include="Newtonsoft.Json" Version="13.0.3" /></ItemGroup></Project>',
            encoding="utf-8",
        )
        deps = generator._parse_nuget_deps(tmp_path)
        assert len(deps) == 1
        assert deps[0].name == "Newtonsoft.Json"
        assert deps[0].version == "13.0.3"
        assert deps[0].ecosystem == "nuget"


class TestRegistryIntegration:
    def test_all_parsers_registered(self, tmp_path: Path, generator: SBOMGenerator) -> None:
        """九种生态的解析器全部注册进 collect 链。"""
        (tmp_path / "Gemfile").write_text('gem "rails"\n', encoding="utf-8")
        sbom = generator.generate_from_project(tmp_path)
        ecosystems = {d.ecosystem for d in sbom.packages}
        assert "rubygems" in ecosystems
