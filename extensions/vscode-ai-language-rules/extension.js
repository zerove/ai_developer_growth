"use strict";
const { execSync } = require("child_process");
const path = require("path");
const vscode = require("vscode");

/**
 * AI Language Rules VS Code Extension
 * Runs `adg check --json` for multi-language code quality validation
 */

class AILanguageRulesProvider {
  constructor() {
    this.diagnosticCollection = vscode.languages.createDiagnosticCollection("ai-language-rules");
    this.outputChannel = vscode.window.createOutputChannel("AI Language Rules");
  }

  async validateDocument(document) {
    const config = vscode.workspace.getConfiguration("aiLanguageRules");
    if (!config.get("enabled", true)) return;

    const filePath = document.fileName;
    if (!this.isSupportedFile(filePath)) return;

    try {
      const result = await this.runAdgCheck(filePath);
      this.updateDiagnostics(document, result);
    } catch (err) {
      this.outputChannel.appendLine(`Error validating ${filePath}: ${err.message}`);
    }
  }

  isSupportedFile(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    const supported = [
      ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java",
      ".kt", ".cs", ".php", ".rb", ".swift", ".scala", ".dart",
      ".lua", ".hs", ".clj", ".r", ".pl", ".pm", ".ps1", ".zig",
      ".c", ".cpp", ".h", ".hpp", ".m", ".f90", ".f",
    ];
    return supported.includes(ext);
  }

  /**
   * Run `adg check --json` and return the parsed result.
   */
  async runAdgCheck(filePath) {
    const adgPath = vscode.workspace.getConfiguration("aiLanguageRules").get("adgPath", "adg");
    const severity = vscode.workspace.getConfiguration("aiLanguageRules").get("severity", "warning");

    return new Promise((resolve, reject) => {
      try {
        const stdout = execSync(
          `${adgPath} check "${filePath}" --severity ${severity} --json 2>/dev/null`,
          { timeout: 15000, encoding: "utf-8" }
        );
        resolve(JSON.parse(stdout));
      } catch (e) {
        if (e.stderr && e.stderr.includes("command not found")) {
          this.outputChannel.appendLine("ADG: 'adg' CLI not found. Install with: pip install ai-dev-framework");
          resolve({ issues: [], summary: { error: 0, warning: 0, info: 0 } });
        } else if (e.stdout) {
          try { resolve(JSON.parse(e.stdout)); } catch { reject(e); }
        } else {
          reject(e);
        }
      }
    });
  }

  /**
   * Try to auto-fix a file via `adg fix --json`.
   */
  async fixDocument(document) {
    const adgPath = vscode.workspace.getConfiguration("aiLanguageRules").get("adgPath", "adg");
    try {
      const stdout = execSync(
        `${adgPath} fix --json "${document.fileName}" 2>/dev/null`,
        { timeout: 30000, encoding: "utf-8" }
      );
      const result = JSON.parse(stdout);
      this.outputChannel.appendLine(`Auto-fix: ${result.fixed} fixed, ${result.skipped} skipped`);
      // Re-check after fix
      await this.validateDocument(document);
      return result;
    } catch (e) {
      this.outputChannel.appendLine(`Auto-fix failed: ${e.message}`);
      return null;
    }
  }

  updateDiagnostics(document, result) {
    const diagnostics = [];
    const issues = result.issues || [];

    for (const issue of issues) {
      const line = Math.max(0, (issue.line || 1) - 1);
      const col = issue.column || 0;
      const range = new vscode.Range(line, col, line, col + 20);

      let severity;
      switch (issue.severity) {
        case "error": severity = vscode.DiagnosticSeverity.Error; break;
        case "warning": severity = vscode.DiagnosticSeverity.Warning; break;
        default: severity = vscode.DiagnosticSeverity.Information;
      }

      const diag = new vscode.Diagnostic(
        range,
        `[${issue.rule_id}] ${issue.message}`,
        severity
      );
      diag.source = "ai-language-rules";
      diag.code = issue.rule_id;

      if (issue.fix_hint) {
        diag.relatedInformation = [
          new vscode.DiagnosticRelatedInformation(
            new vscode.Location(document.uri, range),
            `Fix: ${issue.fix_hint}`
          ),
        ];
      }

      diagnostics.push(diag);
    }

    this.diagnosticCollection.set(document.uri, diagnostics);
  }

  dispose() {
    this.diagnosticCollection.dispose();
    this.outputChannel.dispose();
  }
}

function activate(context) {
  const provider = new AILanguageRulesProvider();

  // Validate on file open and save
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((doc) => provider.validateDocument(doc)),
    vscode.workspace.onDidSaveTextDocument((doc) => provider.validateDocument(doc)),
    vscode.commands.registerCommand("aiLanguageRules.validate", () => {
      const editor = vscode.window.activeTextEditor;
      if (editor) provider.validateDocument(editor.document);
    }),
    vscode.commands.registerCommand("aiLanguageRules.validateProject", async () => {
      const files = await vscode.workspace.findFiles(
        "**/*.{py,js,ts,tsx,jsx,rs,go,java,kt,cs,php,rb,swift,scala,dart,lua,hs,clj,r,pl,ps1,zig,c,cpp,h,hpp,m,f90,f}"
      );
      for (const file of files) {
        const doc = await vscode.workspace.openTextDocument(file);
        await provider.validateDocument(doc);
      }
    }),
    vscode.commands.registerCommand("aiLanguageRules.autoFix", () => {
      const editor = vscode.window.activeTextEditor;
      if (editor) provider.fixDocument(editor.document);
    }),
    provider
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
