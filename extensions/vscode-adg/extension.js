/**
 * ADG Code Quality — VS Code Extension
 *
 * 实时代码质量扫描，基于 `adg` CLI (ai-developer-governance).
 * 在保存文件时自动运行，在 Problems 面板显示结果。
 * 支持实时诊断、自动修复、规则查看、状态栏显示。
 */

const { execSync, spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const vscode = require("vscode");

/** @type {vscode.DiagnosticCollection} */
let diagnosticCollection;
/** @type {vscode.StatusBarItem} */
let statusBarItem;
/** @type {vscode.OutputChannel} */
let outputChannel;
/** @type {Map<string, vscode.Diagnostic[]>} */
let diagnosticMap = new Map();

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  console.log("ADG: activating...");

  diagnosticCollection = vscode.languages.createDiagnosticCollection("adg");
  context.subscriptions.push(diagnosticCollection);

  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  context.subscriptions.push(statusBarItem);

  outputChannel = vscode.window.createOutputChannel("ADG Governance");
  context.subscriptions.push(outputChannel);

  registerCommands(context);
  registerEventHandlers(context);
  updateStatusBar();
}

function deactivate() {
  if (diagnosticCollection) {
    diagnosticCollection.clear();
    diagnosticCollection.dispose();
  }
  if (statusBarItem) statusBarItem.dispose();
  if (outputChannel) outputChannel.dispose();
}

// ─────────────────────────────────────────────────────────────
// Command Registration
// ─────────────────────────────────────────────────────────────

function registerCommands(context) {
  const commands = [
    ["adg.check", cmdCheckFile],
    ["adg.checkProject", cmdCheckProject],
    ["adg.fix", cmdFixFile],
    ["adg.fixProject", cmdFixProject],
    ["adg.listRules", cmdListRules],
    ["adg.showOutput", cmdShowOutput],
    ["adg.installHooks", cmdInstallHooks],
    ["adg.scanFile", cmdCheckFile],
    ["adg.scanWorkspace", cmdCheckProject],
  ];

  for (const [id, handler] of commands) {
    context.subscriptions.push(vscode.commands.registerCommand(id, handler));
  }

  // Quick Fix provider
  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      { scheme: "file", pattern: "**/*" },
      new AdgCodeActionProvider(),
      { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
    )
  );
}

// ─────────────────────────────────────────────────────────────
// Event Handlers
// ─────────────────────────────────────────────────────────────

function registerEventHandlers(context) {
  const config = vscode.workspace.getConfiguration("adg");

  // On save
  if (config.get("scanOnSave", true)) {
    context.subscriptions.push(
      vscode.workspace.onDidSaveTextDocument((doc) => {
        if (isSupportedFile(doc.fileName)) scanDocument(doc);
      })
    );
  }

  // On open
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor && config.get("scanOnOpen", false)) {
        scanDocument(editor.document);
      }
    })
  );
}

// ─────────────────────────────────────────────────────────────
// Commands
// ─────────────────────────────────────────────────────────────

async function cmdCheckFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("ADG: No active editor");
    return;
  }

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Window, title: "ADG: Checking..." },
    async () => {
      await scanDocument(editor.document);
    }
  );
}

async function cmdCheckProject() {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showWarningMessage("ADG: No workspace folder");
    return;
  }

  outputChannel.appendLine("🔍 Running ADG project check...");
  outputChannel.show(true);

  const result = runAdgCheck(folder.uri.fsPath);
  if (!result) return;

  // Update diagnostics for open documents
  vscode.workspace.textDocuments.forEach((doc) => {
    if (isSupportedFile(doc.fileName)) {
      updateDiagnostics(result.issues || [], doc);
    }
  });
  updateStatusBar();

  outputChannel.appendLine(`Language: ${result.language}`);
  outputChannel.appendLine(`Files: ${result.files_checked}  Issues: ${result.issues?.length || 0}`);
  if (result.summary) {
    outputChannel.appendLine(`  Errors: ${result.summary.error}  Warnings: ${result.summary.warning}  Info: ${result.summary.info}`);
  }

  const issues = result.issues || [];
  if (issues.length > 0) {
    outputChannel.appendLine("\nIssues:");
    for (const issue of issues.slice(0, 50)) {
      outputChannel.appendLine(`  ${issue.file}:${issue.line} [${issue.severity}] ${issue.message}`);
    }
    if (issues.length > 50) outputChannel.appendLine(`  ... and ${issues.length - 50} more`);
  }

  showMessage(issues, result.summary);
}

async function cmdFixFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("ADG: No active editor");
    return;
  }

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Window, title: "ADG: Fixing..." },
    async () => {
      const fixResult = runAdgFix(editor.document.fileName);
      if (fixResult) {
        vscode.window.showInformationMessage(`ADG: Fixed ${fixResult.fixed} issues, ${fixResult.skipped} skipped`);
        await scanDocument(editor.document);
      }
    }
  );
}

async function cmdFixProject() {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showWarningMessage("ADG: No workspace folder");
    return;
  }

  outputChannel.appendLine("🔧 Running ADG auto-fix on project...");
  outputChannel.show(true);

  const fixResult = runAdgFix(folder.uri.fsPath);
  if (fixResult) {
    outputChannel.appendLine(`Fixed: ${fixResult.fixed}  Skipped: ${fixResult.skipped}  Errors: ${fixResult.errors}`);
    vscode.window.showInformationMessage(`ADG: Fixed ${fixResult.fixed} issues`);

    // Re-check open documents
    vscode.workspace.textDocuments.forEach((doc) => {
      if (isSupportedFile(doc.fileName)) scanDocument(doc);
    });
  }
}

async function cmdListRules() {
  const languages = [
    "python", "javascript", "typescript", "rust", "go", "java",
    "kotlin", "ruby", "php", "csharp", "swift", "c", "cpp"
  ];

  const selected = await vscode.window.showQuickPick(languages, {
    placeHolder: "Select language to list rules"
  });
  if (!selected) return;

  outputChannel.appendLine(`\nRules for ${selected}:`);
  outputChannel.show(true);

  try {
    const stdout = execSync(`adg list-rules --lang "${selected}" --json 2>/dev/null`, {
      timeout: 10000,
      encoding: "utf-8",
    });
    const rules = JSON.parse(stdout);
    if (Array.isArray(rules)) {
      outputChannel.appendLine(`Total: ${rules.length} rules\n`);
      for (const rule of rules) {
        outputChannel.appendLine(`  [${rule.severity}] ${rule.id}: ${rule.name || ""}`);
        if (rule.message) outputChannel.appendLine(`    ${rule.message}`);
      }
    }
  } catch (e) {
    outputChannel.appendLine(`Failed to list rules: ${e.message}`);
  }
}

function cmdShowOutput() {
  outputChannel.show(true);
}

async function cmdInstallHooks() {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) {
    vscode.window.showWarningMessage("ADG: No workspace folder");
    return;
  }

  try {
    execSync(`adg install-hooks "${folder.uri.fsPath}" 2>/dev/null`, {
      timeout: 10000,
      encoding: "utf-8",
    });
    vscode.window.showInformationMessage("ADG: Git hooks installed");
    outputChannel.appendLine("Git hooks installed successfully");
  } catch (e) {
    vscode.window.showErrorMessage(`Failed to install hooks: ${e.message}`);
  }
}

// ─────────────────────────────────────────────────────────────
// ADG CLI Runner
// ─────────────────────────────────────────────────────────────

function getAdgPath() {
  const config = vscode.workspace.getConfiguration("adg");
  return config.get("executablePath") || "adg";
}

/**
 * Run `adg check --json` on a target file/directory.
 * @param {string} target
 * @returns {{language?:string, files_checked?:number, issues?:Array, summary?:{error:number,warning:number,info:number}} | null}
 */
function runAdgCheck(target) {
  const config = vscode.workspace.getConfiguration("adg");
  const severity = config.get("severityThreshold") || "warning";

  try {
    const stdout = execSync(`${getAdgPath()} check "${target}" --severity ${severity} --json 2>/dev/null`, {
      timeout: 15000,
      encoding: "utf-8",
    });
    return JSON.parse(stdout);
  } catch (e) {
    if (e.stderr && e.stderr.includes("command not found")) {
      vscode.window.showWarningMessage("ADG: 'adg' command not found. Install with: pip install ai-dev-framework");
    }
    return null;
  }
}

/**
 * Run `adg fix --json` on a target file/directory.
 * @param {string} target
 * @returns {{fixed:number, skipped:number, errors:number} | null}
 */
function runAdgFix(target) {
  try {
    const stdout = execSync(`${getAdgPath()} fix --json "${target}" 2>/dev/null`, {
      timeout: 30000,
      encoding: "utf-8",
    });
    return JSON.parse(stdout);
  } catch (e) {
    outputChannel.appendLine(`ADG fix failed: ${e.message}`);
    return null;
  }
}

// ─────────────────────────────────────────────────────────────
// Diagnostics
// ─────────────────────────────────────────────────────────────

function severityToVscode(severity) {
  switch (severity) {
    case "error": return vscode.DiagnosticSeverity.Error;
    case "warning": return vscode.DiagnosticSeverity.Warning;
    case "info": return vscode.DiagnosticSeverity.Information;
    default: return vscode.DiagnosticSeverity.Warning;
  }
}

function updateDiagnostics(issues, document) {
  const diagnostics = issues
    .filter((issue) => normalizePath(issue.file) === normalizePath(document.fileName))
    .map((issue) => {
      const line = Math.max(0, (issue.line || 1) - 1);
      const col = Math.max(0, (issue.column || 0) - 1);
      const range = new vscode.Range(line, col, line, col + 80);

      const diagnostic = new vscode.Diagnostic(
        range,
        `[${issue.rule_id}] ${issue.message}`,
        severityToVscode(issue.severity)
      );
      diagnostic.source = "adg";
      diagnostic.code = issue.rule_id;

      if (issue.fix_hint) {
        diagnostic.relatedInformation = [
          new vscode.DiagnosticRelatedInformation(
            new vscode.Location(document.uri, range),
            `Fix: ${issue.fix_hint}`
          ),
        ];
      }

      return diagnostic;
    });

  diagnosticCollection.set(document.uri, diagnostics);
  diagnosticMap.set(document.fileName, diagnostics);
}

function normalizePath(p) {
  return path.normalize(p).toLowerCase();
}

async function scanDocument(doc) {
  if (!doc || doc.isUntitled || doc.lineCount === 0) return;
  if (!isSupportedFile(doc.fileName)) return;

  const result = runAdgCheck(doc.fileName);
  if (result) {
    updateDiagnostics(result.issues || [], doc);
    updateStatusBar();
  }
}

// ─────────────────────────────────────────────────────────────
// Status Bar
// ─────────────────────────────────────────────────────────────

function updateStatusBar() {
  let errorCount = 0;
  let warningCount = 0;

  diagnosticMap.forEach((diags) => {
    for (const d of diags) {
      if (d.severity === vscode.DiagnosticSeverity.Error) errorCount++;
      else if (d.severity === vscode.DiagnosticSeverity.Warning) warningCount++;
    }
  });

  if (errorCount > 0 || warningCount > 0) {
    statusBarItem.text = `$(shield) ADG: ${errorCount}E ${warningCount}W`;
    statusBarItem.tooltip = `ADG Governance: ${errorCount} errors, ${warningCount} warnings`;
    statusBarItem.backgroundColor = errorCount > 0
      ? new vscode.ThemeColor("statusBarItem.errorBackground")
      : new vscode.ThemeColor("statusBarItem.warningBackground");
  } else {
    statusBarItem.text = "$(shield) ADG";
    statusBarItem.tooltip = "ADG Governance: All checks passed";
    statusBarItem.backgroundColor = undefined;
  }
  statusBarItem.show();
}

// ─────────────────────────────────────────────────────────────
// Quick Fix Provider
// ─────────────────────────────────────────────────────────────

class AdgCodeActionProvider {
  provideCodeActions(document, range, context) {
    const config = vscode.workspace.getConfiguration("adg");
    if (!config.get("enableQuickFix", true)) return [];

    const actions = [];

    for (const diagnostic of context.diagnostics) {
      if (diagnostic.source !== "adg") continue;
      const ruleId = diagnostic.code;

      if (ruleId) {
        const fixAction = new vscode.CodeAction(
          `ADG: Fix "${ruleId}"`,
          vscode.CodeActionKind.QuickFix
        );
        fixAction.command = { command: "adg.fix", title: "ADG Auto-fix", arguments: [] };
        fixAction.diagnostics = [diagnostic];
        actions.push(fixAction);
      }
    }

    return actions;
  }
}

// ─────────────────────────────────────────────────────────────
// Message Display
// ─────────────────────────────────────────────────────────────

function showMessage(issues, summary) {
  const total = issues.length;
  if (total === 0) {
    vscode.window.showInformationMessage("ADG: All checks passed");
  } else if (summary?.error > 0) {
    vscode.window.showErrorMessage(`ADG: ${summary.error} error(s), ${summary.warning} warning(s)`);
  } else {
    vscode.window.showWarningMessage(`ADG: ${summary.warning} warning(s), ${summary.info} info`);
  }
}

// ─────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────

const SUPPORTED_EXTENSIONS = new Set([
  ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
  ".kt", ".rb", ".php", ".swift", ".c", ".cpp", ".cs",
  ".h", ".hh", ".hpp", ".dart", ".scala", ".clj",
  ".lua", ".hs", ".r", ".pl", ".pm", ".zig",
]);

function isSupportedFile(filename) {
  const ext = path.extname(filename).toLowerCase();
  return SUPPORTED_EXTENSIONS.has(ext);
}

module.exports = { activate, deactivate };
