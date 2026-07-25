import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';

interface AdgIssue {
    rule_id: string;
    severity: 'error' | 'warning' | 'info';
    category: string;
    file: string;
    line: number;
    column: number;
    message: string;
    fix_hint: string;
}

interface AdgResult {
    language: string;
    framework: string | null;
    files_checked: number;
    issues: AdgIssue[];
    summary: { error: number; warning: number; info: number };
}

let diagnosticCollection: vscode.DiagnosticCollection;
let statusBarItem: vscode.StatusBarItem;
let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {
    console.log('ADG Governance extension activated');

    // Create diagnostic collection
    diagnosticCollection = vscode.languages.createDiagnosticCollection('adg');
    context.subscriptions.push(diagnosticCollection);

    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.command = 'adg.showOutput';
    context.subscriptions.push(statusBarItem);

    // Create output channel
    outputChannel = vscode.window.createOutputChannel('ADG Governance');
    context.subscriptions.push(outputChannel);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('adg.check', checkCurrentFile),
        vscode.commands.registerCommand('adg.checkProject', checkProject),
        vscode.commands.registerCommand('adg.checkIncremental', checkIncremental),
        vscode.commands.registerCommand('adg.showOutput', showOutput),
        vscode.commands.registerCommand('adg.fix', fixCurrentFile),
        vscode.commands.registerCommand('adg.listRules', listRules)
    );

    // Register on save handler
    const config = vscode.workspace.getConfiguration('adg');
    if (config.get<boolean>('enableOnSave')) {
        context.subscriptions.push(
            vscode.workspace.onDidSaveTextDocument((document) => {
                if (isCodeFile(document.fileName)) {
                    checkDocument(document);
                }
            })
        );
    }

    // Check all open documents
    vscode.workspace.textDocuments.forEach((document) => {
        if (isCodeFile(document.fileName)) {
            checkDocument(document);
        }
    });

    updateStatusBar();
}

function getAdgPath(): string {
    const config = vscode.workspace.getConfiguration('adg');
    return config.get<string>('executablePath') || 'adg';
}

function isCodeFile(filename: string): boolean {
    const extensions = ['.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java', '.kt', '.rb', '.php', '.swift', '.c', '.cpp', '.cs'];
    return extensions.some(ext => filename.endsWith(ext));
}

function runAdg(args: string[]): Promise<AdgResult> {
    return new Promise((resolve, reject) => {
        const adgPath = getAdgPath();
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();
        
        const child = cp.spawn(adgPath, [...args, '--json'], {
            cwd: workspaceFolder,
            env: { ...process.env },
            stdio: ['pipe', 'pipe', 'pipe']
        });

        let stdout = '';
        let stderr = '';

        child.stdout.on('data', (data) => {
            stdout += data.toString();
        });

        child.stderr.on('data', (data) => {
            stderr += data.toString();
        });

        child.on('close', (code) => {
            if (code === 0 || code === 1) {
                try {
                    resolve(JSON.parse(stdout));
                } catch (e) {
                    reject(new Error(`Failed to parse ADG output: ${e}`));
                }
            } else {
                reject(new Error(`ADG exited with code ${code}: ${stderr}`));
            }
        });

        child.on('error', (err) => {
            reject(err);
        });
    });
}

function severityToVscode(severity: string): vscode.DiagnosticSeverity {
    switch (severity) {
        case 'error':
            return vscode.DiagnosticSeverity.Error;
        case 'warning':
            return vscode.DiagnosticSeverity.Warning;
        case 'info':
            return vscode.DiagnosticSeverity.Information;
        default:
            return vscode.DiagnosticSeverity.Warning;
    }
}

function updateDiagnostics(issues: AdgIssue[], document: vscode.TextDocument) {
    const diagnostics: vscode.Diagnostic[] = issues
        .filter(issue => issue.file === document.fileName)
        .map(issue => {
            const range = new vscode.Range(
                issue.line - 1, issue.column - 1,
                issue.line - 1, issue.column + 100
            );
            const diagnostic = new vscode.Diagnostic(
                range,
                `${issue.message}\n[${issue.rule_id}] ${issue.fix_hint}`,
                severityToVscode(issue.severity)
            );
            diagnostic.source = 'adg';
            diagnostic.code = issue.rule_id;
            return diagnostic;
        });

    diagnosticCollection.set(document.uri, diagnostics);
}

function updateStatusBar() {
    const config = vscode.workspace.getConfiguration('adg');
    if (!config.get<boolean>('showStatusBar')) {
        statusBarItem.hide();
        return;
    }

    const diagnostics = vscode.languages.getDiagnostics();
    let errorCount = 0;
    let warningCount = 0;

    diagnostics.forEach(([, diags]) => {
        diags.forEach(d => {
            if (d.source === 'adg') {
                if (d.severity === vscode.DiagnosticSeverity.Error) {
                    errorCount++;
                } else if (d.severity === vscode.DiagnosticSeverity.Warning) {
                    warningCount++;
                }
            }
        });
    });

    if (errorCount > 0 || warningCount > 0) {
        statusBarItem.text = `$(warning) ADG: ${errorCount}E ${warningCount}W`;
        statusBarItem.tooltip = `ADG Governance: ${errorCount} errors, ${warningCount} warnings`;
        statusBarItem.show();
    } else {
        statusBarItem.text = `$(check) ADG`;
        statusBarItem.tooltip = 'ADG Governance: No issues';
        statusBarItem.show();
    }
}

async function checkDocument(document: vscode.TextDocument) {
    try {
        const config = vscode.workspace.getConfiguration('adg');
        const severity = config.get<string>('severityFilter') || 'warning';
        
        const result = await runAdg(['check', document.fileName, '--severity', severity]);
        updateDiagnostics(result.issues, document);
        updateStatusBar();
    } catch (err) {
        // Silently ignore errors on background check
    }
}

async function checkCurrentFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    try {
        const config = vscode.workspace.getConfiguration('adg');
        const severity = config.get<string>('severityFilter') || 'warning';
        
        const result = await runAdg(['check', editor.document.fileName, '--severity', severity]);
        updateDiagnostics(result.issues, editor.document);
        updateStatusBar();

        if (result.issues.length === 0) {
            vscode.window.showInformationMessage('ADG: No issues found!');
        } else {
            vscode.window.showWarningMessage(`ADG: Found ${result.issues.length} issues`);
        }
    } catch (err) {
        vscode.window.showErrorMessage(`ADG check failed: ${err}`);
    }
}

async function checkProject() {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        vscode.window.showWarningMessage('No workspace folder');
        return;
    }

    try {
        const config = vscode.workspace.getConfiguration('adg');
        const severity = config.get<string>('severityFilter') || 'warning';
        
        outputChannel.appendLine('Running ADG project check...');
        outputChannel.show();

        const result = await runAdg(['check', workspaceFolder.uri.fsPath, '--severity', severity]);
        
        // Update all open documents
        vscode.workspace.textDocuments.forEach(doc => {
            if (isCodeFile(doc.fileName)) {
                updateDiagnostics(result.issues, doc);
            }
        });
        updateStatusBar();

        outputChannel.appendLine(`Language: ${result.language}`);
        outputChannel.appendLine(`Files checked: ${result.files_checked}`);
        outputChannel.appendLine(`Issues: ${result.issues.length}`);
        outputChannel.appendLine(`  Errors: ${result.summary.error}`);
        outputChannel.appendLine(`  Warnings: ${result.summary.warning}`);
        outputChannel.appendLine(`  Info: ${result.summary.info}`);
    } catch (err) {
        vscode.window.showErrorMessage(`ADG project check failed: ${err}`);
    }
}

async function checkIncremental() {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        vscode.window.showWarningMessage('No workspace folder');
        return;
    }

    try {
        outputChannel.appendLine('Running ADG incremental check (git diff)...');
        outputChannel.show();

        const result = await runAdg(['check', workspaceFolder.uri.fsPath, '--since', 'HEAD']);
        
        outputChannel.appendLine(`Incremental check: ${result.issues.length} issues in changed files`);
        
        if (result.issues.length > 0) {
            result.issues.forEach(issue => {
                outputChannel.appendLine(`  ${issue.file}:${issue.line} [${issue.severity}] ${issue.message}`);
            });
        }
    } catch (err) {
        vscode.window.showErrorMessage(`ADG incremental check failed: ${err}`);
    }
}

async function fixCurrentFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    try {
        const result = await runAdg(['fix', editor.document.fileName]);
        vscode.window.showInformationMessage(`ADG: Applied fixes to ${editor.document.fileName}`);
        
        // Re-check after fix
        await checkDocument(editor.document);
    } catch (err) {
        vscode.window.showErrorMessage(`ADG fix failed: ${err}`);
    }
}

async function listRules() {
    const languages = ['python', 'javascript', 'typescript', 'rust', 'go', 'java'];
    
    const selected = await vscode.window.showQuickPick(languages, {
        placeHolder: 'Select language'
    });

    if (selected) {
        try {
            const result = await runAdg(['list-rules', '--lang', selected, '--json']);
            outputChannel.appendLine(`\nRules for ${selected}:`);
            outputChannel.appendLine(JSON.stringify(result, null, 2));
            outputChannel.show();
        } catch (err) {
            vscode.window.showErrorMessage(`Failed to list rules: ${err}`);
        }
    }
}

function showOutput() {
    outputChannel.show();
}

export function deactivate() {
    diagnosticCollection.dispose();
    statusBarItem.dispose();
    outputChannel.dispose();
}
