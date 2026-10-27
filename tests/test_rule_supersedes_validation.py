"""Validate ``supersedes`` declarations across rule YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tools.scripts._common import rules_dir
from tools.scripts.rules_engine.validators.pipeline import load_rules


def _rule_sources() -> list[tuple[str, Path, list[dict[str, Any]]]]:
    root = rules_dir()
    sources: list[tuple[str, Path, list[dict[str, Any]]]] = []
    common_path = root / "common" / "security.yml"
    if common_path.exists():
        data = yaml.safe_load(common_path.read_text(encoding="utf-8")) or {}
        sources.append(("common", common_path, data.get("anti_patterns", [])))
    for path in sorted((root / "languages").glob("*/rules.d/anti_patterns.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        sources.append((path.parent.parent.name, path, data.get("anti_patterns", [])))
    return sources


def _supersedes(rule: dict[str, Any]) -> list[str]:
    value = rule.get("supersedes", [])
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    return []


def _all_rule_ids(sources: list[tuple[str, Path, list[dict[str, Any]]]]) -> set[str]:
    return {rule["id"] for _, _, rules in sources for rule in rules if isinstance(rule.get("id"), str)}


def _rule_id_map() -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for _, _, rules in _rule_sources():
        for rule in rules:
            rule_id = rule.get("id")
            if isinstance(rule_id, str):
                graph[rule_id] = _supersedes(rule)
    return graph


def _has_cycle(graph: dict[str, list[str]]) -> bool:
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in visited:
            return False
        visited.add(node)
        active.add(node)
        if any(visit(target) for target in graph.get(node, []) if target in graph):
            return True
        active.remove(node)
        return False

    return any(visit(node) for node in graph)


def test_supersedes_shape_and_targets() -> None:
    sources = _rule_sources()
    common_ids = {
        rule["id"]
        for source, _, rules in sources
        if source == "common"
        for rule in rules
        if isinstance(rule.get("id"), str)
    }
    assert common_ids, "common/security.yml must define rule IDs"

    for source, path, rules in sources:
        file_ids = [rule["id"] for rule in rules if isinstance(rule.get("id"), str)]
        assert len(file_ids) == len(set(file_ids)), f"duplicate rule ID in {path}"

        for rule in rules:
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or "supersedes" not in rule:
                continue
            targets = _supersedes(rule)
            raw_value = rule["supersedes"]
            assert isinstance(raw_value, (str, list)), f"{source}:{rule_id} supersedes must be str/list"
            assert targets, f"{source}:{rule_id} supersedes must not be empty"
            assert all(isinstance(target, str) and target for target in targets), (
                f"{source}:{rule_id} supersedes entries must be non-empty strings"
            )
            assert len(targets) == len(set(targets)), f"{source}:{rule_id} has duplicate targets"
            assert rule_id not in targets, f"{source}:{rule_id} must not supersede itself"
            if source != "common":
                missing = set(targets) - common_ids
                assert not missing, f"{source}:{rule_id} supersedes non-common IDs: {missing}"


def test_supersedes_graph_has_no_cycles() -> None:
    assert not _has_cycle(_rule_id_map())


def test_loader_drops_superseded_common_rules() -> None:
    sources = _rule_sources()
    common_ids = {
        rule["id"]
        for source, _, rules in sources
        if source == "common"
        for rule in rules
        if isinstance(rule.get("id"), str)
    }
    assert common_ids

    for source, _, rules in sources:
        if source == "common":
            continue
        targets = {target for rule in rules if isinstance(rule.get("id"), str) for target in _supersedes(rule)}
        if not targets:
            continue
        loaded = load_rules(source, rules_dir())
        loaded_ids = {rule["id"] for rule in loaded.get("anti_patterns", []) if isinstance(rule.get("id"), str)}
        assert not targets & loaded_ids, f"{source} still loads superseded rules: {targets & loaded_ids}"


def test_all_rule_ids_are_globally_unique() -> None:
    ids = [rule["id"] for _, _, rules in _rule_sources() for rule in rules if isinstance(rule.get("id"), str)]
    assert len(ids) == len(set(ids)), "rule IDs must be unique across all YAML sources"
