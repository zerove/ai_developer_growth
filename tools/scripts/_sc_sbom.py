"""SBOM 生成器 (从 supply_chain.py 拆分).

SBOMGenerator 类: 多语言依赖解析 (Python/npm/Cargo/Go/Maven/Gradle/Ruby/PHP/.NET).
由 supply_chain.py facade 统一 re-export.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from ._sc_models import SBOM, Dependency

logger = logging.getLogger(__name__)


class SBOMGenerator:
    """SBOM 生成器"""

    def __init__(self) -> None:
        pass

    def generate_from_python(self, project_root: Path) -> SBOM:
        """从 Python 项目生成 SBOM"""
        sbom = SBOM()
        sbom.name = project_root.name

        # 读取 pyproject.toml 或 requirements.txt
        deps = self._parse_python_deps(project_root)
        for dep in deps:
            sbom.packages.append(dep)

        # 添加关系
        for i, dep in enumerate(sbom.packages):
            sbom.relationships.append(
                {
                    "spdxElementId": f"SPDXRef-Package-{i}",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": "SPDXRef-Package-ROOT",
                }
            )

        return sbom

    def _collect_all_dependencies(self, project_root: Path) -> list[Dependency]:
        """收集全部生态的依赖声明。"""
        all_deps: list[Dependency] = []
        parsers = [
            self._parse_python_deps,
            self._parse_npm_deps,
            self._parse_cargo_deps,
            self._parse_go_deps,
            self._parse_maven_deps,
            self._parse_gradle_deps,
            self._parse_gemfile_deps,
            self._parse_composer_deps,
            self._parse_nuget_deps,
        ]
        for parser in parsers:
            all_deps.extend(parser(project_root))
        return all_deps

    @staticmethod
    def _dedupe_dependencies(deps: list[Dependency]) -> list[Dependency]:
        """按 name+version+ecosystem 去重。"""
        seen: set[tuple[str, str, str]] = set()
        unique: list[Dependency] = []
        for dep in deps:
            key = (dep.name, dep.version, dep.ecosystem)
            if key not in seen:
                seen.add(key)
                unique.append(dep)
        return unique

    def generate_from_project(self, project_root: Path) -> SBOM:
        """自动检测项目语言并生成完整 SBOM"""
        sbom = SBOM()
        sbom.name = project_root.name

        sbom.packages = self._dedupe_dependencies(self._collect_all_dependencies(project_root))

        # 添加关系
        for i in range(len(sbom.packages)):
            sbom.relationships.append(
                {
                    "spdxElementId": f"SPDXRef-Package-{i}",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": "SPDXRef-Package-ROOT",
                }
            )

        return sbom

    def _parse_python_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Python 依赖"""
        deps = []

        # 尝试解析 pyproject.toml
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            deps.extend(self._parse_pyproject(pyproject))

        # 尝试解析 requirements.txt
        req_file = project_root / "requirements.txt"
        if req_file.exists():
            deps.extend(self._parse_requirements(req_file))

        # 尝试解析 poetry.lock
        poetry_lock = project_root / "poetry.lock"
        if poetry_lock.exists():
            deps.extend(self._parse_poetry_lock(poetry_lock))

        # 尝试解析 pipenv.lock
        pipenv_lock = project_root / "Pipfile.lock"
        if pipenv_lock.exists():
            deps.extend(self._parse_pipenv_lock(pipenv_lock))

        return deps

    def _parse_pyproject(self, path: Path) -> list[Dependency]:
        """解析 pyproject.toml 依赖 (project.dependencies + tool.poetry.dependencies).

        V2.20 P4-42 拆分: 抽 _parse_project_dependencies + _parse_poetry_dependencies
        收口两个 dep 块解析, 主函数仅 try/except + 调用.
        """
        deps: list[Dependency] = []
        try:
            import tomllib

            with open(path, "rb") as f:
                data = tomllib.load(f)
            deps.extend(self._parse_project_dependencies(data))
            deps.extend(self._parse_poetry_dependencies(data))
        except Exception as e:
            logger.warning(f"Failed to parse pyproject.toml: {e}")
        return deps

    def _parse_project_dependencies(self, data: dict[str, object]) -> list[Dependency]:
        """解析 [project] dependencies 块.

        Args:
            data: tomllib 解析后的字典

        Returns:
            dependency 列表
        """
        project = data.get("project", {})
        deps: list[Dependency] = []
        for dep_spec in project.get("dependencies", []):  # type: ignore[attr-defined]
            dep = self._parse_dep_spec(dep_spec)
            if dep:
                deps.append(dep)
        return deps

    def _parse_poetry_dependencies(self, data: dict[str, object]) -> list[Dependency]:
        """解析 [tool.poetry] dependencies 块 (排除 python).

        Args:
            data: tomllib 解析后的字典

        Returns:
            dependency 列表
        """
        poetry = data.get("tool", {}).get("poetry", {})  # type: ignore[attr-defined]
        deps: list[Dependency] = []
        for name, spec in poetry.get("dependencies", {}).items():
            if name == "python":
                continue
            dep = self._parse_poetry_dep(name, spec)
            if dep:
                deps.append(dep)
        return deps

    def _parse_requirements(self, path: Path) -> list[Dependency]:
        """解析 requirements.txt.

        V2.20 P4-49 拆分: 抽 _parse_requirements_line 收口单行解析 (strip + 注释守卫 + dep_spec),
        主函数仅 try/except + content 加载 + 遍历.
        """
        deps: list[Dependency] = []
        try:
            content = path.read_text()
            for line in content.splitlines():
                dep = self._parse_requirements_line(line)
                if dep:
                    deps.append(dep)
        except Exception as e:
            logger.warning(f"Failed to parse requirements.txt: {e}")
        return deps

    def _parse_requirements_line(self, line: str) -> Dependency | None:
        """解析 requirements.txt 单行 (实例级 helper).

        Args:
            line: 单行文本

        Returns:
            Dependency 对象 (None if 空行/注释)
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        return self._parse_dep_spec(line)

    def _parse_poetry_lock(self, path: Path) -> list[Dependency]:
        deps = []
        try:
            import tomllib

            with open(path, "rb") as f:
                data = tomllib.load(f)

            for pkg in data.get("package", []):
                dep = Dependency(
                    name=pkg.get("name", ""),
                    version=pkg.get("version", ""),
                    ecosystem="pypi",
                    is_direct=True,
                )
                deps.append(dep)
        except Exception as e:
            logger.warning(f"Failed to parse poetry.lock: {e}")
        return deps

    def _parse_pipenv_lock(self, path: Path) -> list[Dependency]:
        deps = []
        try:
            with open(path) as f:
                data = json.load(f)

            for name, info in data.get("default", {}).items():
                version = info.get("version", "").lstrip("==")
                dep = Dependency(
                    name=name,
                    version=version,
                    ecosystem="pypi",
                    is_direct=True,
                )
                deps.append(dep)
        except Exception as e:
            logger.warning(f"Failed to parse Pipfile.lock: {e}")
        return deps

    @staticmethod
    def _parse_package_json(project_root: Path) -> list[Dependency]:
        """解析 package.json 的直接依赖。"""
        deps: list[Dependency] = []
        package_json = project_root / "package.json"
        if not package_json.exists():
            return deps
        try:
            with open(package_json) as f:
                data = json.load(f)
            for dep_type in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
                for name, version in data.get(dep_type, {}).items():
                    deps.append(Dependency(name=name, version=version.lstrip("^~>="), ecosystem="npm", is_direct=True))
        except Exception as e:
            logger.warning(f"Failed to parse package.json: {e}")
        return deps

    @staticmethod
    def _parse_package_lock(project_root: Path) -> list[Dependency]:
        """解析 package-lock.json 获取准确版本和传递依赖 (v2 packages 格式)。"""
        deps: list[Dependency] = []
        lock_file = project_root / "package-lock.json"
        if not lock_file.exists():
            return deps
        try:
            with open(lock_file) as f:
                data = json.load(f)
            for path, info in data.get("packages", {}).items():
                if path == "":
                    continue
                name = path.split("node_modules/")[-1]
                deps.append(
                    Dependency(
                        name=name,
                        version=info.get("version", ""),
                        ecosystem="npm",
                        is_direct=not info.get("dev", False),
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to parse package-lock.json: {e}")
        return deps

    def _parse_npm_deps(self, project_root: Path) -> list[Dependency]:
        """解析 npm 依赖 (package.json + package-lock.json)"""
        return self._parse_package_json(project_root) + self._parse_package_lock(project_root)

    @staticmethod
    def _load_toml(path: Path) -> dict[str, Any]:
        """加载 TOML 文件; 失败返回空字典。"""
        import tomllib

        with open(path, "rb") as f:
            return tomllib.load(f)

    def _parse_cargo_toml(self, project_root: Path) -> list[Dependency]:
        """解析 Cargo.toml 的直接依赖声明.

        V2.20 P4-43 拆分: 抽 _extract_cargo_version 收口 spec 字符串/字典类型判断,
        主函数仅 3 类 dep 遍历 + Dependency 构造.
        """
        deps: list[Dependency] = []
        cargo_toml = project_root / "Cargo.toml"
        if not cargo_toml.exists():
            return deps
        try:
            data = self._load_toml(cargo_toml)
            for dep_type in ["dependencies", "dev-dependencies", "build-dependencies"]:
                for name, spec in data.get(dep_type, {}).items():
                    version = self._extract_cargo_version(spec)
                    deps.append(Dependency(name=name, version=version, ecosystem="cargo", is_direct=True))
        except Exception as e:
            logger.warning(f"Failed to parse Cargo.toml: {e}")
        return deps

    @staticmethod
    def _extract_cargo_version(spec: object) -> str:
        """从 Cargo.toml spec 提取版本字符串.

        Args:
            spec: TOML spec (str 直接为版本 / dict 含 version 键 / 其他空字符串)

        Returns:
            version 字符串
        """
        if isinstance(spec, str):
            return spec
        if isinstance(spec, dict):
            return spec.get("version", "")
        return ""

    def _parse_cargo_lock(self, project_root: Path) -> list[Dependency]:
        """解析 Cargo.lock 的全部传递依赖。"""
        deps: list[Dependency] = []
        cargo_lock = project_root / "Cargo.lock"
        if not cargo_lock.exists():
            return deps
        try:
            data = self._load_toml(cargo_lock)
            for pkg in data.get("package", []):
                deps.append(
                    Dependency(
                        name=pkg.get("name", ""),
                        version=pkg.get("version", ""),
                        ecosystem="cargo",
                        is_direct=False,  # Cargo.lock 包含所有传递依赖
                    )
                )
        except Exception as e:
            logger.warning(f"Failed to parse Cargo.lock: {e}")
        return deps

    def _parse_cargo_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Cargo 依赖 (Cargo.toml + Cargo.lock)"""
        return self._parse_cargo_toml(project_root) + self._parse_cargo_lock(project_root)

    def _parse_go_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Go 依赖 (go.mod + go.sum).

        V2.20 P4-39 拆分: 抽 _parse_go_require_line 收口单行解析,
        主函数仅 try/except 包裹 + state machine 遍历.
        """
        deps: list[Dependency] = []
        go_mod = project_root / "go.mod"
        if not go_mod.exists():
            return deps
        try:
            content = go_mod.read_text()
            in_require = False
            for line in content.splitlines():
                dep, in_require = self._parse_go_require_line(line.strip(), in_require)
                if dep is not None:
                    deps.append(dep)
        except Exception as e:
            logger.warning(f"Failed to parse go.mod: {e}")
        return deps

    def _parse_go_require_line(self, line: str, in_require: bool) -> tuple[Dependency | None, bool]:
        """解析单行 go.mod (V2.22 P6-3 拆分: 抽 _handle_require_block_marker + _build_go_dependency, 方法级 helper).

        Args:
            line: 已 strip 的行
            in_require: 当前是否在 require () 块内

        Returns:
            (Dependency 或 None, 更新后的 in_require 状态)
        """
        new_in_require, is_block_marker = self._handle_require_block_marker(line, in_require)
        if is_block_marker:
            return None, new_in_require
        if not (in_require or line.startswith("require ")):
            return None, in_require
        return self._build_go_dependency(line, in_require)

    def _handle_require_block_marker(self, line: str, in_require: bool) -> tuple[bool, bool]:
        """处理 require ( ... ) 块起止标记 (方法级 helper, 内部修改 self 状态).

        Args:
            line: 已 strip 的行
            in_require: 当前是否在 require 块内

        Returns:
            (new_in_require, is_block_marker) 元组:
            - new_in_require: 更新后的状态
            - is_block_marker: True 表示 'require (' 或 ')' 块起止
        """
        if line.startswith("require ("):
            return True, True
        if in_require and line == ")":
            return False, True
        return in_require, False

    def _build_go_dependency(self, line: str, in_require: bool) -> tuple[Dependency | None, bool]:
        """从 go.mod 单行构造 Dependency (方法级 helper).

        Args:
            line: 已 strip 的行 (需以 'require ' 开头)
            in_require: 当前是否在 require 块内

        Returns:
            (Dependency 或 None, in_require 状态)
        """
        parts = line.replace("require ", "").split()
        if len(parts) < 2:
            return None, in_require
        return (
            Dependency(
                name=parts[0],
                version=parts[1],
                ecosystem="go",
                is_direct=True,
            ),
            in_require,
        )

    def _parse_maven_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Maven 依赖 (pom.xml).

        V2.20 P4-40 拆分: 抽 _extract_maven_dep 收口单 dep XML 解析,
        _parse_pom_xml 收口 XML 加载 + 遍历, 主函数仅文件存在 + try/except.
        """
        deps: list[Dependency] = []
        pom_xml = project_root / "pom.xml"
        if not pom_xml.exists():
            return deps
        try:
            deps = self._parse_pom_xml(pom_xml)
        except Exception as e:
            logger.warning(f"Failed to parse pom.xml: {e}")
        return deps

    def _parse_pom_xml(self, pom_xml: Path) -> list[Dependency]:
        """解析 pom.xml 文件, 提取所有 dependencies.

        Args:
            pom_xml: pom.xml 路径

        Returns:
            dependency 列表
        """
        import xml.etree.ElementTree as ET

        tree = ET.parse(pom_xml)  # nosec B320 - parsing local trusted pom.xml
        root = tree.getroot()
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}

        deps: list[Dependency] = []
        for dep_elem in root.findall(".//m:dependency", ns):
            dep = self._extract_maven_dep(dep_elem, ns)
            if dep is not None:
                deps.append(dep)
        return deps

    def _extract_maven_dep(self, dep_elem: object, ns: dict[str, str]) -> Dependency | None:
        """从 XML dependency 元素提取 Dependency 对象.

        Args:
            dep_elem: XML dependency 元素
            ns: Maven 命名空间

        Returns:
            Dependency 对象 (None if groupId/artifactId 缺失)
        """
        group_id = dep_elem.find("m:groupId", ns)  # type: ignore[attr-defined]
        artifact_id = dep_elem.find("m:artifactId", ns)  # type: ignore[attr-defined]
        version_elem = dep_elem.find("m:version", ns)  # type: ignore[attr-defined]
        scope_elem = dep_elem.find("m:scope", ns)  # type: ignore[attr-defined]

        if group_id is None or artifact_id is None:
            return None

        version = version_elem.text if version_elem is not None else ""
        scope = scope_elem.text if scope_elem is not None else "compile"
        return Dependency(
            name=f"{group_id.text}:{artifact_id.text}",
            version=version or "",
            ecosystem="maven",
            is_direct=scope == "compile",
        )

    def _parse_gradle_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Gradle 依赖 (build.gradle / build.gradle.kts)。"""
        deps: list[Dependency] = []
        for gradle_name in ("build.gradle", "build.gradle.kts"):
            gradle_file = project_root / gradle_name
            if not gradle_file.exists():
                continue
            try:
                content = gradle_file.read_text(encoding="utf-8", errors="ignore")
            except OSError as e:
                logger.warning(f"Failed to parse {gradle_name}: {e}")
                continue
            # 匹配 implementation/api/testImplementation 'group:artifact:version' 两种引号风格
            import re

            pattern = re.compile(
                r"""(?:implementation|api|compile|runtimeOnly|testImplementation)\s+['"]([^'":]+):([^'":]+):([^'"]+)['"]"""
            )
            for match in pattern.finditer(content):
                group, artifact, version = match.group(1), match.group(2), match.group(3)
                deps.append(
                    Dependency(
                        name=f"{group}:{artifact}",
                        version=version.strip(),
                        ecosystem="maven",
                        is_direct=True,
                    )
                )
        return deps

    def _parse_gemfile_deps(self, project_root: Path) -> list[Dependency]:
        """解析 Ruby 依赖 (Gemfile + Gemfile.lock)。"""
        deps: list[Dependency] = []
        gemfile = project_root / "Gemfile"
        if not gemfile.exists():
            return deps
        try:
            content = gemfile.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            logger.warning(f"Failed to parse Gemfile: {e}")
            return deps
        import re

        # 匹配 gem "rails", "~> 7.0" 与 gem 'sinatra', '4.0'
        for match in re.compile(r"""^\s*gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""", re.M).finditer(content):
            name = match.group(1)
            version = (match.group(2) or "").lstrip("~><= ")
            deps.append(Dependency(name=name, version=version, ecosystem="rubygems", is_direct=True))
        return deps

    def _parse_composer_deps(self, project_root: Path) -> list[Dependency]:
        """解析 PHP 依赖 (composer.json require 段)。"""
        composer_json = project_root / "composer.json"
        if not composer_json.exists():
            return []
        try:
            with open(composer_json, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning(f"Failed to parse composer.json: {e}")
            return []
        deps = []
        for name, constraint in (data.get("require") or {}).items():
            if name == "php":
                continue
            version = constraint.lstrip("v^~>=< ")
            deps.append(Dependency(name=name, version=version, ecosystem="packagist", is_direct=True))
        return deps

    def _parse_nuget_deps(self, project_root: Path) -> list[Dependency]:
        """解析 .NET 依赖 (csproj 的 PackageReference)。"""
        deps: list[Dependency] = []
        csproj_files = list(project_root.rglob("*.csproj"))
        if not csproj_files:
            return deps
        import re

        for csproj in csproj_files[:20]:  # 防御超大仓库
            try:
                content = csproj.read_text(encoding="utf-8", errors="ignore")
            except OSError as e:
                logger.warning(f"Failed to parse {csproj.name}: {e}")
                continue
            for match in re.compile(r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"').finditer(content):
                deps.append(
                    Dependency(
                        name=match.group(1),
                        version=match.group(2),
                        ecosystem="nuget",
                        is_direct=True,
                    )
                )
        return deps

    def _parse_dep_spec(self, spec: str) -> Dependency | None:
        """解析依赖规格 (包名 + 版本约束)。

        额外保留版本约束符 (">=" / "==" 等): 清单里的 ">=0.23" 只是下界,
        不是可安装版本 (PyPI 上真实版本是 0.23.0), 存在性校验必须区分
        "下界约束" 与 "精确锁定"。
        """
        # 简化解析: package>=1.0, package==1.0, package~=1.0
        match = re.match(r"^([A-Za-z0-9_.-]+)([=<>!~]+.*)?$", spec.strip())
        if match:
            name = match.group(1)
            constraint = match.group(2) or ""
            version = constraint.lstrip("=<>~!") if constraint else ""
            return Dependency(
                name=name,
                version=version,
                ecosystem="pypi",
                specifier=self._extract_specifier(constraint),
            )
        return None

    @staticmethod
    def _extract_specifier(constraint: str) -> str | None:
        """从约束文本里取出比较符 (如 ">=6.0" → ">=")。

        Args:
            constraint: 约束文本 (可能为空)

        Returns:
            比较符; 无比较符时返回 None
        """
        match = re.match(r"^(==|>=|<=|~=|!=|>|<)", constraint)
        return match.group(1) if match else None

    def _parse_poetry_dep(self, name: str, spec: str | dict[str, Any]) -> Dependency | None:
        if isinstance(spec, str):
            return Dependency(name=name, version=spec, ecosystem="pypi")
        elif isinstance(spec, dict):
            return Dependency(name=name, version=spec.get("version", ""), ecosystem="pypi")
        return None
