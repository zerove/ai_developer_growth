"""LSP Server for ADG Governance rules engine.

Provides IDE diagnostics for supported languages using the Language Server Protocol.
Requires: pip install lsprotocol pygls

Usage:
    python -m tools.scripts.rules_engine.lsp_server

Supported features:
- Diagnostics (real-time code quality feedback)
- Hover (rule documentation on hover)
- Code actions (quick-fix suggestions)
"""

from __future__ import annotations

# mypy: disable-error-code="untyped-decorator"
import re
import sys
from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.logger import logger

try:
    from pygls.lsp.server import LanguageServer
    from pygls.lsp.types import (
        CodeAction,
        CodeActionKind,
        CodeActionParams,
        Diagnostic,
        DiagnosticSeverity,
        DidChangeTextDocumentParams,
        DidOpenTextDocumentParams,
        Hover,
        HoverParams,
        Position,
        Range,
        TextEdit,
    )

    HAS_PYGLS = True
except ImportError:
    HAS_PYGLS = False


def _map_severity(severity: str) -> int:
    """Map rule severity to LSP DiagnosticSeverity."""
    if not HAS_PYGLS:
        return 1
    mapping = {
        "error": DiagnosticSeverity.Error,
        "warning": DiagnosticSeverity.Warning,
        "info": DiagnosticSeverity.Information,
    }
    return mapping.get(severity, DiagnosticSeverity.Information)  # type: ignore[no-any-return]


def _text_to_range(text: str, pattern: str, line_offset: int = 0) -> Range | None:
    """Find pattern in text and return LSP Range."""
    if not HAS_PYGLS:
        return None
    for match in re.finditer(pattern, text, re.MULTILINE):
        start_line = text[: match.start()].count("\n") + line_offset
        start_col = match.start() - text.rfind("\n", 0, match.start()) - 1
        end_line = text[: match.end()].count("\n") + line_offset
        end_col = match.end() - text.rfind("\n", 0, match.end()) - 1
        return Range(
            start=Position(line=start_line, character=max(0, start_col)),
            end=Position(line=end_line, character=max(0, end_col)),
        )
    return None


def _check_document(content: str, language: str) -> list[Diagnostic]:
    """Check a document against language rules and return diagnostics."""
    if not HAS_PYGLS:
        return []

    try:
        from tools.scripts._common import rules_dir

        from .rule_loader import load_rules_for_language
    except ImportError:
        return []

    try:
        rules = load_rules_for_language(language, rules_dir())
    except Exception:
        return []

    diagnostics: list[Diagnostic] = []
    anti_patterns = rules.get("anti_patterns", [])

    for rule in anti_patterns:
        pattern = rule.get("pattern", "")
        if not pattern:
            continue
        try:
            for match in re.finditer(pattern, content, re.MULTILINE):
                start_line = content[: match.start()].count("\n")
                start_col = match.start() - (content.rfind("\n", 0, match.start()) + 1)
                end_line = content[: match.end()].count("\n")
                end_col = match.end() - (content.rfind("\n", 0, match.end()) + 1)

                diag = Diagnostic(
                    range=Range(
                        start=Position(line=start_line, character=max(0, start_col)),
                        end=Position(line=end_line, character=max(0, end_col)),
                    ),
                    message=rule.get("message", "Code quality issue"),
                    severity=_map_severity(rule.get("severity", "warning")),
                    source="adg-governance",
                    code=rule.get("id", ""),
                    code_description={"href": ""} if rule.get("fix_hint") else None,
                )
                diagnostics.append(diag)
        except re.error:
            # Invalid regex pattern
            pass

    return diagnostics


LANG_MAP = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "rust": "rust",
    "java": "java",
    "csharp": "csharp",
    "go": "go",
    "kotlin": "kotlin",
    "swift": "swift",
}

EXT_LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".go": "go",
    ".kt": "kotlin",
    ".swift": "swift",
}


def create_server() -> Any:
    """Create and configure the ADG LSP server."""
    if not HAS_PYGLS:
        logger.info("Error: pygls required. Install: pip install pygls", file=sys.stderr)
        sys.exit(1)

    server = LanguageServer("adg-governance", "v1.0")

    @server.feature("textDocument/didOpen")
    def did_open(params: DidOpenTextDocumentParams) -> None:
        """Check document on open."""
        _publish_diagnostics(server, params.text_document.uri)

    @server.feature("textDocument/didChange")
    def did_change(params: DidChangeTextDocumentParams) -> None:
        """Check document on change."""
        _publish_diagnostics(server, params.text_document.uri)

    @server.feature("textDocument/hover")
    def hover(params: HoverParams) -> Hover | None:
        """Show rule info on hover."""
        document = server.workspace.get_document(params.text_document.uri)
        content = document.source
        line = content.splitlines()[params.position.line] if params.position.line < len(content.splitlines()) else ""

        try:
            from tools.scripts._common import rules_dir

            from .rule_loader import load_rules_for_language

            ext = Path(params.text_document.uri).suffix.lower()
            lang = EXT_LANG_MAP.get(ext)
            if not lang:
                return None
            rules = load_rules_for_language(lang, rules_dir())
            for rule in rules.get("anti_patterns", []):
                pattern = rule.get("pattern", "")
                if pattern and re.search(pattern, line):
                    md = f"### {rule.get('name', '')}\n\n"
                    md += f"**Rule ID:** `{rule.get('id', '')}`\n\n"
                    md += f"**Severity:** {rule.get('severity', '')}\n\n"
                    md += f"{rule.get('message', '')}\n\n"
                    if rule.get("fix_hint"):
                        md += f"**Fix:** {rule['fix_hint']}\n"
                    return Hover(contents={"kind": "markdown", "value": md})
        except Exception:
            pass
        return None

    @server.feature("textDocument/codeAction")
    def code_actions(params: CodeActionParams) -> list[CodeAction]:
        """Provide quick-fix code actions."""
        document = server.workspace.get_document(params.text_document.uri)
        content = document.source
        diagnostics = params.context.diagnostics if params.context else []

        actions: list[CodeAction] = []
        for diag in diagnostics:
            if diag.source != "adg-governance" or not diag.code:
                continue
            rule_id = diag.code if isinstance(diag.code, str) else str(diag.code)

            try:
                from tools.scripts._common import rules_dir

                from .rule_loader import load_rules_for_language

                ext = Path(params.text_document.uri).suffix.lower()
                lang = EXT_LANG_MAP.get(ext)
                if not lang:
                    continue
                rules = load_rules_for_language(lang, rules_dir())
                for rule in rules.get("anti_patterns", []):
                    if rule.get("id") == rule_id and rule.get("fix_hint"):
                        # Get the full line text
                        lines = content.splitlines()
                        line_text = lines[diag.range.start.line] if diag.range.start.line < len(lines) else ""
                        new_line = line_text  # Placeholder - actual fix requires pattern matching
                        actions.append(
                            CodeAction(
                                title=f"Fix: {rule.get('name', rule_id)}",
                                kind=CodeActionKind.QuickFix,
                                diagnostics=[diag],
                                edit={
                                    "changes": {
                                        params.text_document.uri: [
                                            TextEdit(
                                                range=Range(
                                                    start=Position(line=diag.range.start.line, character=0),
                                                    end=Position(line=diag.range.end.line, character=len(line_text)),
                                                ),
                                                new_text=new_line,
                                            )
                                        ]
                                    }
                                },
                            )
                        )
                        break
            except Exception:
                pass

        return actions

    return server


def _publish_diagnostics(server: LanguageServer, uri: str) -> None:
    """Publish diagnostics for a document."""
    try:
        document = server.workspace.get_document(uri)
        content = document.source
    except Exception:
        return

    ext = Path(uri).suffix.lower()
    lang = EXT_LANG_MAP.get(ext)

    if not lang:
        return

    diagnostics = _check_document(content, lang)
    server.publish_diagnostics(uri, diagnostics)


def main() -> None:
    """Start the ADG LSP server."""
    if not HAS_PYGLS:
        logger.info("Error: pygls required. Install: pip install pygls", file=sys.stderr)
        sys.exit(1)

    server = create_server()
    server.start_io()


if __name__ == "__main__":
    main()
