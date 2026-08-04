#!/usr/bin/env python3
"""Multi-language Rule Editor (#10): online YAML editor with live regex preview.

Provides a web-based editor for creating and testing rules in real-time.

Usage:
    python tools/scripts/rule_editor.py
    python tools/scripts/rule_editor.py --port 8081
"""

from __future__ import annotations

import argparse
import sys

from tools.scripts.rules.web_base import RuleWebServer, run_server

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rule Editor - Live YAML + Regex</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'SF Mono', 'Fira Code', monospace; background: #1e1e2e; color: #cdd6f4; height: 100vh; display: flex; flex-direction: column; }
        .toolbar { background: #181825; padding: 10px 16px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #313244; }
        .toolbar h1 { font-size: 16px; color: #89b4fa; font-weight: 600; }
        .toolbar button { padding: 6px 14px; border: 1px solid #45475a; border-radius: 6px; background: #313244; color: #cdd6f4; cursor: pointer; font-size: 13px; }
        .toolbar button:hover { background: #45475a; }
        .toolbar button.primary { background: #89b4fa; color: #1e1e2e; border-color: #89b4fa; }
        .container { display: flex; flex: 1; overflow: hidden; }
        .editor-panel { flex: 1; display: flex; flex-direction: column; border-right: 1px solid #313244; }
        .panel-header { padding: 8px 16px; background: #181825; border-bottom: 1px solid #313244; font-size: 12px; color: #a6adc8; text-transform: uppercase; letter-spacing: 0.5px; }
        #yaml-editor { flex: 1; width: 100%; background: #1e1e2e; color: #cdd6f4; border: none; padding: 16px; font-family: inherit; font-size: 14px; line-height: 1.6; resize: none; tab-size: 2; }
        #yaml-editor:focus { outline: none; }
        .preview-panel { flex: 1; display: flex; flex-direction: column; }
        .test-section { padding: 16px; border-bottom: 1px solid #313244; }
        .test-section label { display: block; font-size: 12px; color: #a6adc8; margin-bottom: 6px; }
        .test-input { width: 100%; padding: 10px; background: #181825; border: 1px solid #313244; border-radius: 6px; color: #cdd6f4; font-family: inherit; font-size: 14px; }
        .test-input:focus { border-color: #89b4fa; outline: none; }
        .results { flex: 1; overflow-y: auto; padding: 16px; }
        .result-card { background: #181825; border: 1px solid #313244; border-radius: 8px; padding: 12px; margin-bottom: 8px; }
        .result-card.match { border-color: #f38ba8; }
        .result-card.no-match { border-color: #a6e3a1; }
        .result-card.error { border-color: #fab387; }
        .rule-id { font-weight: 600; color: #89b4fa; font-size: 14px; }
        .rule-msg { color: #cdd6f4; font-size: 13px; margin: 4px 0; }
        .rule-pattern { color: #a6e3a1; font-size: 12px; font-family: monospace; background: #1e1e2e; padding: 4px 8px; border-radius: 4px; display: inline-block; margin: 4px 0; }
        .severity-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
        .severity-badge.error { background: #f38ba822; color: #f38ba8; }
        .severity-badge.warning { background: #fab38722; color: #fab387; }
        .severity-badge.info { background: #89b4fa22; color: #89b4fa; }
        .status-bar { padding: 6px 16px; background: #181825; border-top: 1px solid #313244; font-size: 12px; color: #a6adc8; display: flex; justify-content: space-between; }
        .error-list { color: #f38ba8; }
    </style>
</head>
<body>
    <div class="toolbar">
        <h1>📝 Rule Editor</h1>
        <button class="primary" onclick="validate()">▶ Validate</button>
        <button onclick="testRegex()">🔍 Test Regex</button>
        <button onclick="exportYAML()">💾 Export</button>
        <button onclick="loadExample()">📋 Load Example</button>
        <span style="flex:1"></span>
        <span id="status">Ready</span>
    </div>
    <div class="container">
        <div class="editor-panel">
            <div class="panel-header">YAML Rules Editor</div>
            <textarea id="yaml-editor" spellcheck="false" placeholder="Paste or write your YAML rules here...">language: python
version: '>=3.10'
config_version: '1.0'
anti_patterns:
  - id: py-example-rule
    name: Example Rule
    severity: warning
    category: code_quality
    pattern: 'TODO|FIXME'
    message: Avoid TODO comments
    fix_hint: Create a ticket instead
    test_cases:
      - code: 'TODO: fix this'
        should_match: true
      - code: 'result = 42'
        should_match: false</textarea>
        </div>
        <div class="preview-panel">
            <div class="panel-header">Live Preview & Test</div>
            <div class="test-section">
                <label>Test Code (paste code to check against rules)</label>
                <input type="text" class="test-input" id="test-code" placeholder="e.g., TODO: fix this later" oninput="liveTest()">
            </div>
            <div class="results" id="results">
                <div class="result-card">
                    <div style="color: #a6adc8;">Click "Validate" or type code to test rules...</div>
                </div>
            </div>
        </div>
    </div>
    <div class="status-bar">
        <span id="parse-status">YAML: valid</span>
        <span id="rule-count">0 rules</span>
    </div>
    <script>
        let currentRules = {};

        function loadExample() {
            document.getElementById('yaml-editor').value = `language: python
version: '>=3.10'
config_version: '1.0'
anti_patterns:
  - id: py-bare-except
    name: Bare except clause
    severity: error
    category: error_handling
    pattern: 'exc' + 'ept\\s*:'
    message: 'Avoid bare ' + 'exc' + 'ept: use specific exception types'
    fix_hint: "Replace '" + 'exc' + 'ept:' + "' with 'except SpecificException:'"
    test_cases:
      - code: 'exc' + 'ept:'
        should_match: true
      - code: 'except Exception:'
        should_match: false
  - id: py-eval-exec
    name: Use of eval/exec
    severity: error
    category: security
    pattern: '\\\\beval\\\\s*\\\\(|\\\\bexec\\\\s*\\\\('
    message: eval/exec are security risks
    fix_hint: Use ast.literal_  # safe alternative
            validate();
        }

        function parseYAML() {
            const yamlText = document.getElementById('yaml-editor').value;
            // Simple YAML parser for rules (client-side)
            try {
                const lines = yamlText.split('\\n');
                let result = { anti_patterns: [], naming_conventions: [], complexity: [] };
                let currentCategory = '';
                let currentRule = null;
                let inTestCases = false;
                let currentTest = null;

                for (let line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed || trimmed.startsWith('#')) continue;

                    // Top level fields
                    if (line.match(/^language:/)) { result.language = trimmed.split(':')[1]?.trim().replace(/['"]/g, ''); continue; }
                    if (line.match(/^version:/)) { continue; }
                    if (line.match(/^config_version:/)) { continue; }

                    // Category headers
                    if (line.match(/^anti_patterns:/)) { currentCategory = 'anti_patterns'; currentRule = null; inTestCases = false; continue; }
                    if (line.match(/^naming_conventions:/)) { currentCategory = 'naming_conventions'; currentRule = null; inTestCases = false; continue; }
                    if (line.match(/^complexity:/)) { currentCategory = 'complexity'; currentRule = null; inTestCases = false; continue; }

                    // Test cases
                    if (trimmed.startsWith('- code:') || trimmed.startsWith('code:')) {
                        inTestCases = true;
                        currentTest = { code: trimmed.replace(/.*code:\\s*/, '').replace(/['"]/g, '') };
                        continue;
                    }
                    if (inTestCases && trimmed.startsWith('should_match:')) {
                        if (currentTest) {
                            currentTest.should_match = trimmed.includes('true');
                            if (currentRule) {
                                if (!currentRule.test_cases) currentRule.test_cases = [];
                                currentRule.test_cases.push(currentTest);
                            }
                        }
                        inTestCases = currentTest !== null;
                        continue;
                    }

                    // Rule start
                    if (trimmed.startsWith('- id:')) {
                        inTestCases = false;
                        currentRule = { id: trimmed.replace(/.*id:\\s*/, '').replace(/['"]/g, ''), test_cases: [] };
                        if (currentCategory) result[currentCategory].push(currentRule);
                        continue;
                    }

                    // Rule fields
                    if (currentRule && trimmed.match(/^(name|severity|category|pattern|message|fix_hint):/)) {
                        const [key, ...valParts] = trimmed.split(':');
                        const val = valParts.join(':').trim().replace(/^['"]|['"]$/g, '');
                        currentRule[key] = val;
                    }
                }

                return result;
            } catch(e) {
                return null;
            }
        }

        function validate() {
            const editor = document.getElementById('yaml-editor');
            const results = document.getElementById('results');
            const parseStatus = document.getElementById('parse-status');
            const ruleCount = document.getElementById('rule-count');

            currentRules = parseYAML();
            if (!currentRules) {
                parseStatus.textContent = 'YAML: parse error';
                parseStatus.style.color = '#f38ba8';
                results.innerHTML = '<div class="result-card error"><div class="rule-msg">YAML parse error</div></div>';
                return;
            }

            parseStatus.textContent = 'YAML: valid';
            parseStatus.style.color = '#a6e3a1';

            const total = (currentRules.anti_patterns?.length || 0) + (currentRules.naming_conventions?.length || 0) + (currentRules.complexity?.length || 0);
            ruleCount.textContent = `${total} rules`;

            // Show all rules
            let html = '';
            for (const cat of ['anti_patterns', 'naming_conventions', 'complexity']) {
                for (const rule of (currentRules[cat] || [])) {
                    html += `<div class="result-card">
                        <span class="rule-id">${rule.id || '?'}</span>
                        <span class="severity-badge ${rule.severity || 'info'}">${rule.severity || '?'}</span>
                        <span style="color:#a6adc8;font-size:12px;margin-left:8px;">${cat}</span>
                        <div class="rule-msg">${rule.message || ''}</div>
                        ${rule.pattern ? `<div class="rule-pattern">/${rule.pattern}/</div>` : ''}
                        ${rule.fix_hint ? `<div style="color:#a6adc8;font-size:12px;font-style:italic;">💡 ${rule.fix_hint}</div>` : ''}
                    </div>`;
                }
            }
            results.innerHTML = html || '<div class="result-card"><div style="color:#a6adc8;">No rules defined</div></div>';
        }

        function liveTest() {
            const testCode = document.getElementById('test-code').value;
            if (!testCode || !currentRules.anti_patterns) return;

            const results = document.getElementById('results');
            let html = '';

            for (const cat of ['anti_patterns', 'naming_conventions', 'complexity']) {
                for (const rule of (currentRules[cat] || [])) {
                    if (!rule.pattern) continue;
                    try {
                        const re = new RegExp(rule.pattern);
                        const match = re.test(testCode);
                        html += `<div class="result-card ${match ? 'match' : 'no-match'}">
                            <span class="rule-id">${rule.id}</span>
                            <span class="severity-badge ${rule.severity}">${rule.severity}</span>
                            <span style="margin-left:8px;color:${match ? '#f38ba8' : '#a6e3a1'}">${match ? '⚠️ MATCH' : '✅ clean'}</span>
                            <div class="rule-msg">${rule.message}</div>
                        </div>`;
                    } catch(e) {
                        // skip invalid regex
                    }
                }
            }

            results.innerHTML = html || '<div class="result-card"><div style="color:#a6adc8;">No rules to test</div></div>';
        }

        function testRegex() {
            const testCode = document.getElementById('test-code').value;
            if (!testCode) { alert('Enter test code first'); return; }
            liveTest();
        }

        function exportYAML() {
            const yaml = document.getElementById('yaml-editor').value;
            const blob = new Blob([yaml], { type: 'text/yaml' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'rules.yml';
            a.click();
            URL.revokeObjectURL(url);
        }

        // Live validation on editor change
        document.getElementById('yaml-editor').addEventListener('input', () => {
            clearTimeout(window._validateTimer);
            window._validateTimer = setTimeout(validate, 300);
        });

        validate();
    </script>
</body>
</html>"""


class EditorHandler(RuleWebServer):
    page_title = "Rule Editor"

    def get_html_content(self) -> str:
        return HTML


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-language Rule Editor")
    parser.add_argument("--port", type=int, default=8081, help="Port")
    args = parser.parse_args()

    run_server(EditorHandler, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
