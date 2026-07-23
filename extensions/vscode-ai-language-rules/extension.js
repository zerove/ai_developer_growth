"use strict";
const { spawn } = require("child_process");
const path = require("path");
const vscode = require("vscode");

/**
 * AI Language Rules VS Code Extension
 * Runs the Python validation engine as a subprocess
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
    const ext = path.extname(filePath).toLowerCase();

    // Map VS Code language IDs to our language names
    const langMap = {
      ".py": "python", ".js": "javascript", ".ts": "typescript",
      ".tsx": "typescript", ".jsx": "javascript", ".rs": "rust",
      ".go": "go", ".java": "java", ".kt": "kotlin",
      ".cs": "csharp", ".php": "php", ".rb": "ruby",
      ".swift": "swift", ".scala": "scala", ".dart": "dart",
      ".lua": "lua", ".hs": "haskell", ".clj": "clojure",
      ".r": "r", ".R": "r", ".pl": "perl", ".pm": "perl",
      ".ps1": "powershell", ".zig": "zig", ".c": "c",
      ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
      ".m": "matlab", ".f90": "fortran", ".f": "fortran",
      ".graphql": "graphql", ".gql": "graphql",
      ".asm": "assembly", ".s": "assembly",
    };

    const language = langMap[ext];
    if (!language) return;

    try {
      const result = await this.runValidation(filePath, language);
      this.updateDiagnostics(document, result);
    } catch (err) {
      this.outputChannel.appendLine(`Error validating ${filePath}: ${err.message}`);
    }
  }

  async runValidation(filePath, language) {
    return new Promise((resolve, reject) => {
      const scriptPath = path.join(
        vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath || "",
        "tools", "scripts", "validate_language_rules.py"
      );

      const proc = spawn("python", [
        scriptPath,
        "--lang", language,
        "--format", "json",
        filePath,
      ], { cwd: vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (data) => { stdout += data; });
      proc.stderr.on("data", (data) => { stderr += data; });

      proc.on("close", (code) => {
        if (code === 0 || stdout) {
          try {
            resolve(JSON.parse(stdout));
          } catch {
            resolve({ results: [] });
          }
        } else {
          reject(new Error(stderr || "Validation failed"));
        }
      });

      proc.on("error", reject);
    });
  }

  updateDiagnostics(document, result) {
    const diagnostics = [];
    const results = result.results || [];

    for (const fileResult of results) {
      for (const issue of fileResult.issues || []) {
        const line = Math.max(0, (issue.line || 1) - 1);
        const col = issue.column || 0;
        const range = new vscode.Range(line, col, line, col + 20);

        let severity;
        switch (issue.severity) {
          case "error": severity = vscode.DiagnosticSeverity.Error; break;
          case "warning": severity = vscode.DiagnosticSeverity.Warning; break;
          default: severity = vscode.DiagnosticSeverity.Information;
        }

        const diag = new vscode.Diagnostic(range, issue.message, severity);
        diag.source = "ai-language-rules";
        diag.code = issue.rule_id;

        if (issue.fix_hint) {
          diag.relatedInformation = [
            new vscode.DiagnosticRelatedInformation(
              new vscode.Location(document.uri, range),
              `Fix: ${issue.fix_hint}`
            )
          ];
        }

        diagnostics.push(diag);
      }
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
      const files = await vscode.workspace.findFiles("**/*.{py,js,ts,tsx,jsx,rs,go,java,kt,cs,php,rb,swift,scala,dart,lua,hs,clj,r,pl,ps1,zig,c,cpp,h,hpp,m,f90,f,graphql,asm}");
      for (const file of files) {
        const doc = await vscode.workspace.openTextDocument(file);
        await provider.validateDocument(doc);
      }
    }),
    provider
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
