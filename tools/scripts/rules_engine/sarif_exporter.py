import json
from typing import Any


def to_sarif(results: list[Any], tool_name: str = "jcode-governance") -> str:
    """将检查结果转换为 SARIF 2.1.0 标准格式，以便 IDE/GitHub 集成。"""
    run: dict[str, Any] = {
        "tool": {"driver": {"name": tool_name, "version": "1.0.0"}},
        "results": [],
    }
    for res in results:
        for issue in res.issues:
            run["results"].append(
                {
                    "ruleId": issue.rule_id,
                    "message": {"text": issue.message},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": res.file},
                                "region": {
                                    "startLine": issue.line,
                                    "startColumn": max(1, issue.column),
                                },
                            }
                        }
                    ],
                }
            )
    return json.dumps({"version": "2.1.0", "runs": [run]}, indent=2)
