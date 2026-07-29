/**
 * ADG Code Quality — VS Code Extension
 *
 * 实时代码质量扫描，基于 `adg scan` CLI。
 * 在保存文件时自动运行，在 Problems 面板显示结果。
 */

const { execSync } = require("child_process");
const path = require("path");
const vscode = require("vscode");

/** @type {vscode.DiagnosticCollection} */
let diagnosticCollection;

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  console.log("ADG: activating...");

  diagnosticCollection = vscode.languages.createDiagnosticCollection("adg");
  context.subscriptions.push(diagnosticCollection);

  // 注册命令
  context.subscriptions.push(
    vscode.commands.registerCommand("adg.scanFile", () => scanActiveFile())
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("adg.scanWorkspace", () => scanWorkspace())
  );

  // 保存时自动扫描
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => {
      const config = vscode.workspace.getConfiguration("adg");
      if (config.get("scanOnSave")) {
        scanDocument(doc);
      }
    })
  );

  // 打开文件时扫描
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        scanDocument(editor.document);
      }
    })
  );

  vscode.window.showInformationMessage("ADG: 已激活");
}

function deactivate() {
  if (diagnosticCollection) {
    diagnosticCollection.clear();
    diagnosticCollection.dispose();
  }
}

/**
 * 扫描当前活动文件
 */
async function scanActiveFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("ADG: 没有活动文件");
    return;
  }
  vscode.window.withProgress(
    { location: vscode.ProgressLocation.Window, title: "ADG: 扫描中..." },
    () => {
      scanDocument(editor.document);
      return Promise.resolve();
    }
  );
}

/**
 * 扫描整个工作区
 */
async function scanWorkspace() {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders) {
    vscode.window.showWarningMessage("ADG: 没有打开的工作区");
    return;
  }

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "ADG: 扫描工作区...",
      cancellable: true,
    },
    async (progress, token) => {
      const files = await vscode.workspace.findFiles(
        "**/*.{py,js,ts,rs,go,java}",
        "**/node_modules/**"
      );

      for (let i = 0; i < files.length; i++) {
        if (token.isCancellationRequested) break;
        progress.report({
          message: `${i + 1}/${files.length}`,
          increment: (100 / files.length),
        });

        try {
          const doc = await vscode.workspace.openTextDocument(files[i]);
          scanDocument(doc);
        } catch (e) {
          // skip binary files
        }
      }
    }
  );

  vscode.window.showInformationMessage(`ADG: 扫描完成 (${files.length} files)`);
}

/**
 * 扫描单个文档
 * @param {vscode.TextDocument} doc
 */
function scanDocument(doc) {
  if (!doc || doc.isUntitled || doc.lineCount === 0) return;

  const filePath = doc.uri.fsPath;
  const ext = path.extname(filePath).toLowerCase();
  const SUPPORTED = [".py", ".js", ".ts", ".rs", ".go", ".java", ".rb", ".php", ".swift", ".cpp", ".cs", ".kt"];

  if (!SUPPORTED.includes(ext)) return;

  try {
    const stdout = execSync(`adg scan "${filePath}" --json 2>/dev/null`, {
      timeout: 10000,
      encoding: "utf-8",
    });

    const results = JSON.parse(stdout);
    const diagnostics = [];

    const config = vscode.workspace.getConfiguration("adg");
    const threshold = config.get("severityThreshold");
    const sevRank = { error: 0, warning: 1, info: 2 };

    for (const file of results) {
      if (!file.issues) continue;
      for (const issue of file.issues) {
        // Filter by severity threshold
        if (sevRank[issue.severity] < sevRank[threshold]) continue;

        const sevMap = {
          error: vscode.DiagnosticSeverity.Error,
          warning: vscode.DiagnosticSeverity.Warning,
          info: vscode.DiagnosticSeverity.Information,
        };

        const diagnostic = new vscode.Diagnostic(
          new vscode.Range(
            new vscode.Position(issue.line - 1, 0),
            new vscode.Position(issue.line - 1, 1000)
          ),
          `[ADG] [${issue.category}] ${issue.message}`,
          sevMap[issue.severity] || vscode.DiagnosticSeverity.Information
        );

        diagnostic.code = issue.rule_id;
        diagnostic.source = "adg";
        diagnostics.push(diagnostic);
      }
    }

    diagnosticCollection.set(doc.uri, diagnostics);
  } catch (e) {
    // adg not installed or file not supported
    if (e.stderr && e.stderr.includes("adg: command not found")) {
      diagnosticCollection.set(doc.uri, [
        new vscode.Diagnostic(
          new vscode.Range(0, 0, 0, 0),
          "ADG: 'adg' 命令未安装。运行: pip install ai-dev-framework",
          vscode.DiagnosticSeverity.Information
        ),
      ]);
    }
  }
}

module.exports = { activate, deactivate };
