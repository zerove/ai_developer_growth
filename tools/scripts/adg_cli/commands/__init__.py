"""adg_cli/commands/ package facade."""

from __future__ import annotations

from tools.scripts.adg_cli.commands.cmd._cmd_rule_create import _cmd_rule_create  # noqa: F401
from tools.scripts.adg_cli.commands.cmd._cmd_rule_test import _cmd_rule_test  # noqa: F401
from tools.scripts.adg_cli.commands.cmd._cmd_rule_validate import _cmd_rule_validate  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_bench import cmd_bench  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_check import cmd_check  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_cicd import cmd_cicd  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_dashboard import cmd_dashboard  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_detect import cmd_detect  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_fix import cmd_fix  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_html_report import cmd_html_report  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_install_hooks import cmd_install_hooks  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_list_rules import cmd_list_rules  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_lsp import cmd_lsp  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_marketplace import cmd_marketplace  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_monorepo import cmd_monorepo  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_notify import cmd_notify  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_pattern_learner import cmd_pattern_learner  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_recommend import cmd_recommend  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_report import cmd_report  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_rule import cmd_rule  # noqa: F401
from tools.scripts.adg_cli.commands.cmd.cmd_trend import cmd_trend  # noqa: F401
