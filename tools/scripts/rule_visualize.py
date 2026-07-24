#!/usr/bin/env python3
"""Rule Visualization (#9): web interface for browsing and testing rules.

Launches a local web server that displays rules in an interactive UI.

Usage:
    python tools/scripts/rule_visualize.py
    python tools/scripts/rule_visualize.py --port 8080
    python tools/scripts/rule_visualize.py --lang python
"""

from __future__ import annotations

import argparse
import sys

from tools.scripts._common import rules_dir as _rules_dir
from tools.scripts.rules.loader import load_rules
from tools.scripts.rules.web_base import RuleWebServer, run_server


def get_all_rules() -> dict:
    """Load all rules organized by language."""
    langs_dir = _rules_dir() / "languages"
    result: dict[str, dict] = {}

    if langs_dir.exists():
        for lang_dir in sorted(langs_dir.iterdir()):
            if not lang_dir.is_dir():
                continue
            rules = load_rules(lang_dir.name)
            anti = rules.get("anti_patterns", [])
            naming = rules.get("naming_conventions", [])
            complexity = rules.get("complexity", [])
            result[lang_dir.name] = {
                "anti_patterns": anti,
                "naming_conventions": naming,
                "complexity": complexity,
                "total": len(anti) + len(naming) + len(complexity),
            }

    return result


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Language Rules - Visual Browser</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; }
        .header { background: #161b22; border-bottom: 1px solid #30363d; padding: 16px 24px; display: flex; align-items: center; gap: 16px; }
        .header h1 { font-size: 20px; color: #58a6ff; }
        .header .stats { color: #8b949e; font-size: 14px; }
        .container { display: flex; height: calc(100vh - 60px); }
        .sidebar { width: 240px; background: #161b22; border-right: 1px solid #30363d; overflow-y: auto; padding: 12px; }
        .sidebar h3 { color: #8b949e; font-size: 12px; text-transform: uppercase; margin: 12px 0 8px; }
        .lang-btn { display: block; width: 100%; text-align: left; padding: 8px 12px; background: transparent; border: none; color: #c9d1d9; cursor: pointer; border-radius: 6px; font-size: 14px; }
        .lang-btn:hover { background: #21262d; }
        .lang-btn.active { background: #1f6feb22; color: #58a6ff; border-left: 2px solid #58a6ff; }
        .lang-btn .count { float: right; color: #8b949e; font-size: 12px; }
        .main { flex: 1; overflow-y: auto; padding: 24px; }
        .search { width: 100%; padding: 10px 16px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 14px; margin-bottom: 16px; }
        .search:focus { border-color: #58a6ff; outline: none; }
        .rule-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
        .rule-card .header { display: flex; align-items: center; gap: 8px; padding: 0; background: transparent; border: none; }
        .rule-id { font-family: monospace; color: #58a6ff; font-size: 14px; }
        .severity { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
        .severity.error { background: #da363333; color: #f85149; }
        .severity.warning { background: #d2992233; color: #d29922; }
        .severity.info { background: #388bfd22; color: #58a6ff; }
        .category { color: #8b949e; font-size: 12px; }
        .pattern { background: #0d1117; padding: 8px 12px; border-radius: 4px; font-family: monospace; font-size: 13px; color: #7ee787; margin: 8px 0; overflow-x: auto; }
        .message { color: #c9d1d9; font-size: 14px; margin: 4px 0; }
        .fix-hint { color: #8b949e; font-size: 13px; font-style: italic; }
        .tab-bar { display: flex; gap: 4px; margin-bottom: 16px; }
        .tab { padding: 6px 16px; background: transparent; border: 1px solid #30363d; border-radius: 6px; color: #8b949e; cursor: pointer; font-size: 13px; }
        .tab.active { background: #1f6feb22; color: #58a6ff; border-color: #58a6ff; }
        .test-area { margin-top: 12px; }
        .test-input { width: 100%; padding: 8px; background: #0d1117; border: 1px solid #30363d; border-radius: 4px; color: #c9d1d9; font-family: monospace; font-size: 13px; }
        .test-result { margin-top: 8px; padding: 8px; border-radius: 4px; font-size: 13px; }
        .test-result.match { background: #da363333; color: #f85149; }
        .test-result.no-match { background: #23863633; color: #3fb950; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 AI Language Rules</h1>
        <div class="stats" id="stats">Loading...</div>
    </div>
    <div class="container">
        <div class="sidebar" id="sidebar"></div>
        <div class="main">
            <input type="text" class="search" id="search" placeholder="Search rules... (pattern, message, ID)">
            <div class="tab-bar" id="tabs"></div>
            <div id="rules"></div>
        </div>
    </div>
    <script>
        let allRules = {};
        let currentLang = '';
        let currentCategory = 'anti_patterns';

        async function loadRules() {
            const resp = await fetch('/api/rules');
            allRules = await resp.json();
            renderSidebar();
            const firstLang = Object.keys(allRules)[0];
            if (firstLang) selectLang(firstLang);
        }

        function renderSidebar() {
            const sidebar = document.getElementById('sidebar');
            let html = '<h3>Languages</h3>';
            for (const [lang, data] of Object.entries(allRules)) {
                html += `<button class="lang-btn" onclick="selectLang('${lang}')" id="btn-${lang}">
                    ${lang} <span class="count">${data.total}</span>
                </button>`;
            }
            sidebar.innerHTML = html;
            document.getElementById('stats').textContent =
                `${Object.keys(allRules).length} languages, ${Object.values(allRules).reduce((s, d) => s + d.total, 0)} rules`;
        }

        function selectLang(lang) {
            currentLang = lang;
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(`btn-${lang}`)?.classList.add('active');
            renderTabs();
            renderRules();
        }

        function renderTabs() {
            const data = allRules[currentLang];
            const tabs = document.getElementById('tabs');
            tabs.innerHTML = `
                <button class="tab active" onclick="selectCategory('anti_patterns', this)">Anti-patterns (${data.anti_patterns.length})</button>
                <button class="tab" onclick="selectCategory('naming_conventions', this)">Naming (${data.naming_conventions.length})</button>
                <button class="tab" onclick="selectCategory('complexity', this)">Complexity (${data.complexity.length})</button>
            `;
        }

        function selectCategory(cat, el) {
            currentCategory = cat;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            renderRules();
        }

        function renderRules(filter = '') {
            const data = allRules[currentLang];
            const rules = data[currentCategory] || [];
            const container = document.getElementById('rules');
            const lf = filter.toLowerCase();

            const filtered = rules.filter(r =>
                !lf || r.id?.toLowerCase().includes(lf) ||
                r.message?.toLowerCase().includes(lf) ||
                r.pattern?.toLowerCase().includes(lf)
            );

            container.innerHTML = filtered.map(r => `
                <div class="rule-card">
                    <div class="header">
                        <span class="rule-id">${r.id || '?'}</span>
                        <span class="severity ${r.severity || 'info'}">${r.severity || '?'}</span>
                        <span class="category">${r.category || ''}</span>
                    </div>
                    ${r.pattern ? `<div class="pattern">${escHtml(r.pattern)}</div>` : ''}
                    <div class="message">${escHtml(r.message || '')}</div>
                    ${r.fix_hint ? `<div class="fix-hint">💡 ${escHtml(r.fix_hint)}</div>` : ''}
                    ${r.pattern ? `<div class="test-area">
                        <input class="test-input" placeholder="Test code..." oninput="testPattern(this, '${escAttr(r.pattern)}')">
                        <div class="test-result" id="result-${r.id}"></div>
                    </div>` : ''}
                </div>
            `).join('');
        }

        function testPattern(input, pattern) {
            const resultEl = document.getElementById(`result-${input.closest('.rule-card').querySelector('.rule-id').textContent}`);
            if (!resultEl) return;
            try {
                const re = new RegExp(pattern);
                const match = re.test(input.value);
                if (input.value) {
                    resultEl.className = `test-result ${match ? 'match' : 'no-match'}`;
                    resultEl.textContent = match ? '⚠️ Pattern matches!' : '✅ No match';
                } else {
                    resultEl.textContent = '';
                    resultEl.className = 'test-result';
                }
            } catch(e) {
                resultEl.textContent = 'Invalid regex';
                resultEl.className = 'test-result';
            }
        }

        function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
        function escAttr(s) { return s.replace(/'/g, "\\\'").replace(/"/g, '&quot;'); }

        document.getElementById('search').addEventListener('input', (e) => renderRules(e.target.value));
        loadRules();
    </script>
</body>
</html>"""


class VisualizeHandler(RuleWebServer):
    """HTTP handler for rule visualization."""

    page_title = "AI Language Rules - Visual Browser"

    def handle_api(self, path, query, data=None):  # noqa: ANN001
        if path == "/api/rules":
            return get_all_rules()
        elif path == "/api/languages":
            rules = get_all_rules()
            return {k: v["total"] for k, v in rules.items()}
        elif path == "/api/stats":
            rules = get_all_rules()
            total = sum(v["total"] for v in rules.values())
            return {
                "languages": len(rules),
                "total_rules": total,
                "by_lang": {k: v["total"] for k, v in rules.items()},
            }
        return {"error": "Unknown endpoint"}

    def get_html_content(self):
        return HTML_TEMPLATE


def main() -> int:
    parser = argparse.ArgumentParser(description="Rule Visualization Web UI")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--lang", type=str, help="Pre-select a language")
    args = parser.parse_args()

    run_server(VisualizeHandler, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
