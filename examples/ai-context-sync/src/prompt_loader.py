import os
from typing import Any, Optional

import yaml
from jinja2 import Template


def load_prompt(prompt_id: str, context: Optional[dict[str, Any]] = None, version: str = "v1") -> tuple[str, str]:
    # Corrected path handling for the project
    # The file is in src/prompt_loader.py, needs to reach prompts/
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "prompts",
        prompt_id,
        f"{version}.yaml"
    )

    with open(prompt_path, "r") as f:
        data = yaml.safe_load(f)

    template = Template(data["user_template"])
    rendered = template.render(context or {})
    return data["system_prompt"], rendered
