import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

// ─────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────

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

interface AdgTrendPoint {
    timestamp: string;
    errors: number;
    warnings: number;
    info: number;
    total: number;
    language: string;
}

// ─────────────────────────────────────────────────────────────
// Global State
// ─────────────────────────────────────────────────────────────

let diagnosticCollection: vscode.DiagnosticCollection;
let statusBarItem: vscode.StatusBarItem;
let outputChannel: vscode.OutputChannel;
let diagnosticMap: Map<string, vscode.Diagnostic[]> = new Map();
let disposables: vscode.Disposable[] = [];

// ─────────────────────────────────────────────────────────────
// Activation
// ─────────────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext) {
    console.log('ADG Governance extension activated');

    // Core collections
    diagnosticCollection = vscode.languages.createDiagnosticCollection('adg');
    context.subscriptions.push(diagnosticCollection);

    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    context.subscriptions.push(statusBarItem);

    outputChannel = vscode.window.createOutputChannel('ADG Governance');
    context.subscriptions.push(outputChannel);

    // Register all commands
    registerCommands(context);

    // Register event handlers
    registerEventHandlers(context);

    // Initial status
    updateStatusBar();
}

export function deactivate() {
    diagnosticCollection.dispose();
    statusBarItem.dispose();
    outputChannel.dispose();
    disposables.forEach(d => d.dispose());
}

// ─────────────────────────────────────────────────────────────
// Command Registration
// ─────────────────────────────────────────────────────────────

function registerCommands(context: vscode.ExtensionContext) {
    const commands: [string, () => Promise<void>][] = [
        ['adg.check', cmdCheckFile],
        ['adg.checkProject', cmdCheckProject],
        ['adg.checkIncremental', cmdCheckIncremental],
        ['adg.showOutput', cmdShowOutput],
        ['adg.fix', cmdFixFile],
        ['adg.fixProject', cmdFixProject],
        ['adg.listRules', cmdListRules],
        ['adg.importSarif', cmdImportSarif],
        ['adg.showTrend', cmdShowTrend],
        ['adg.installHooks', cmdInstallHooks],
        ['adg.createRule', cmdCreateRule],
    ];

    for (const [id, handler] of commands) {
        context.subscriptions.push(vscode.commands.registerCommand(id, handler));
    }

    // Code Action Provider (Quick Fix)
    context.subscriptions.push(
        vscode.languages.registerCodeActionsProvider(
            { scheme: 'file' },
            new AdgCodeActionProvider(),
            { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
        )
    );

    // CodeLens Provider
    context.subscriptions.push(
        vscode.languages.registerCodeLensProvider(
            { scheme: 'file' },
            new AdgCodeLensProvider()
        )
    );
}

// ─────────────────────────────────────────────────────────────
// Event Handlers
// ─────────────────────────────────────────────────────────────

function registerEventHandlers(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('adg');

    // On save
    if (config.get<boolean>('enableOnSave')) {
        context.subscriptions.push(
            vscode.workspace.onDidSaveTextDocument((doc) => {
                if (isSupportedFile(doc.fileName)) {
                    checkDocument(doc);
                }
            })
        );
    }

    // On open
    if (config.get<boolean>('lintOnOpen')) {
        context.subscriptions.push(
            vscode.workspace.onDidOpenTextDocument((doc) => {
                if (isSupportedFile(doc.fileName)) {
                    checkDocument(doc);
                }
            })
        );
    }

    // On type (debounced)
    if (config.get<boolean>('enableOnType')) {
        let timer: NodeJS.Timeout | undefined;
        const delay = config.get<number>('debounceDelay') || 500;
        context.subscriptions.push(
            vscode.workspace.onDidChangeTextDocument((e) => {
                if (isSupportedFile(e.document.fileName)) {
                    if (timer) { clearTimeout(timer); }
                    timer = setTimeout(() => checkDocument(e.document), delay);
                }
            })
        );
    }

    // On config change
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration((e) => {
            if (e.affectsConfiguration('adg')) {
                // Re-check all open documents
                vscode.workspace.textDocuments.forEach(doc => {
                    if (isSupportedFile(doc.fileName)) {
                        checkDocument(doc);
                    }
                });
                updateStatusBar();
            }
        })
    );

    // SARIF file watcher
    const sarifPattern = config.get<string>('sarifFilePattern') || '**/*.sarif';
    const watcher = vscode.workspace.createFileSystemWatcher(sarifPattern);
    context.subscriptions.push(watcher);
    watcher.onDidChange((uri) => importSarifFile(uri));
    watcher.onDidCreate((uri) => importSarifFile(uri));

    // Check all open documents
    vscode.workspace.textDocuments.forEach(doc => {
        if (isSupportedFile(doc.fileName)) {
            checkDocument(doc);
        }
    });
}

// ─────────────────────────────────────────────────────────────
// Commands
// ─────────────────────────────────────────────────────────────

async function cmdCheckFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('ADG: No active editor');
        return;
    }

    const result = await runAdgCheck(editor.document.fileName);
    if (result) {
        updateDiagnostics(result.issues, editor.document);
        updateStatusBar();
        showMessage(result);
    }
}

async function cmdCheckProject() {
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (!folder) {
        vscode.window.showWarningMessage('ADG: No workspace folder');
        return;
    }

    outputChannel.appendLine('🔍 Running ADG project check...');
    outputChannel.show(true);

    const result = await runAdgCheck(folder.uri.fsPath);
    if (result) {
        // Update diagnostics for all open documents
        vscode.workspace.textDocuments.forEach(doc => {
            if (isSupportedFile(doc.fileName)) {
                updateDiagnostics(result.issues, doc);
            }
        });
        updateStatusBar();

        // Output report
        outputChannel.appendLine(`\nLanguage: ${result.language}`);
        outputChannel.appendLine(`Framework: ${result.framework || 'N/A'}`);
        outputChannel.appendLine(`Files checked: ${result.files_checked}`);
        outputChannel.appendLine(`Issues: ${result.issues.length}`);
        outputChannel.appendLine(`  Errors:   ${result.summary.error}`);
        outputChannel.appendLine(`  Warnings: ${result.summary.warning}`);
        outputChannel.appendLine(`  Info:     ${result.summary.info}`);

        if (result.issues.length > 0) {
            outputChannel.appendLine('\nIssues:');
            for (const issue of result.issues.slice(0, 50)) {
                outputChannel.appendLine(
                    `  ${issue.file}:${issue.line}:${issue.column} [${issue.severity}] ${issue.message}`
                );
            }
            if (result.issues.length > 50) {
                outputChannel.appendLine(`  ... and ${result.issues.length - 50} more`);
            }
        }

        showMessage(result);
    }
}

async function cmdCheckIncremental() {
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (!folder) {
        vscode.window.showWarningMessage('ADG: No workspace folder');
        return;
    }

    outputChannel.appendLine('🔍 Running incremental check (git diff)...');
    outputChannel.show(true);

    const result = await runAdgArgs(['check', folder.uri.fsPath, '--since', 'HEAD']);
    if (result) {
        outputChannel.appendLine(`Incremental: ${result.issues.length} issues in changed files`);
        for (const issue of result.issues.slice(0, 30)) {
            outputChannel.appendLine(
                `  ${issue.file}:${issue.line} [${issue.severity}] ${issue.message}`
            );
        }
        showMessage(result);
    }
}

async function cmdFixFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage('ADG: No active editor');
        return;
    }

    const result = await runAdgArgs(['fix', editor.document.fileName, '--json']);
    if (result) {
        vscode.window.showInformationMessage(
            `ADG: Applied ${result.fixed || 0} fixes to ${path.basename(editor.document.fileName)}`
        );
        // Re-check
        await checkDocument(editor.document);
    }
}

async function cmdFixProject() {
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (!folder) {
        vscode.window.showWarningMessage('ADG: No workspace folder');
        return;
    }

    outputChannel.appendLine('🔧 Running ADG auto-fix on project...');
    outputChannel.show(true);

    const result = await runAdgArgs(['fix', folder.uri.fsPath, '--json']);
    if (result) {
        outputChannel.appendLine(`Fixed: ${result.fixed || 0} issues`);
        outputChannel.appendLine(`Skipped: ${result.skipped || 0}`);
        outputChannel.appendLine(`Errors: ${result.errors || 0}`);
        vscode.window.showInformationMessage(`ADG: Fixed ${result.fixed || 0} issues in project`);

        // Re-check all open documents
        vscode.workspace.textDocuments.forEach(doc => {
            if (isSupportedFile(doc.fileName)) {
                checkDocument(doc);
            }
        });
    }
}

async function cmdListRules() {
    const languages = [
        'python', 'javascript', 'typescript', 'rust', 'go', 'java',
        'kotlin', 'ruby', 'php', 'csharp', 'swift', 'c', 'cpp'
    ];

    const selected = await vscode.window.showQuickPick(languages, {
        placeHolder: 'Select language'
    });

    if (selected) {
        outputChannel.appendLine(`\nRules for ${selected}:`);
        outputChannel.show(true);

        const result = await runAdgArgs(['list-rules', '--lang', selected, '--json']);
        if (result && Array.isArray(result)) {
            outputChannel.appendLine(`Total: ${result.length} anti-patterns\n`);
            for (const rule of result) {
                outputChannel.appendLine(`  [${rule.severity}] ${rule.id}: ${rule.name || ''}`);
                if (rule.message) {
                    outputChannel.appendLine(`    ${rule.message}`);
                }
            }
        }
    }
}

async function cmdImportSarif() {
    const uris = await vscode.window.showOpenDialog({
        canSelectMany: false,
        filters: { 'SARIF Files': ['sarif', 'sarif.json'] },
        title: 'Import SARIF Report'
    });

    if (uris && uris.length > 0) {
        await importSarifFile(uris[0]);
    }
}

async function cmdShowTrend() {
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (!folder) {
        vscode.window.showWarningMessage('ADG: No workspace folder');
        return;
    }

    outputChannel.appendLine('\n📈 Quality Trend:');
    outputChannel.show(true);

    // Try to load trend data
    const trendFile = path.join(folder.uri.fsPath, '.adg', 'trend.json');
    if (fs.existsSync(trendFile)) {
        try {
            const data = JSON.parse(fs.readFileSync(trendFile, 'utf-8'));
            if (Array.isArray(data) && data.length > 0) {
                outputChannel.appendLine(`Data points: ${data.length}`);
                outputChannel.appendLine('\nRecent entries:');
                for (const point of data.slice(-10)) {
                    outputChannel.appendLine(
                        `  ${point.timestamp}: ${point.total} issues (E:${point.errors} W:${point.warnings} I:${point.info})`
                    );
                }
            } else {
                outputChannel.appendLine('No trend data yet. Run check with --trend to record.');
            }
        } catch {
            outputChannel.appendLine('Error reading trend data.');
        }
    } else {
        outputChannel.appendLine('No trend data yet. Run: adg check . --trend');
    }
}

async function cmdInstallHooks() {
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (!folder) {
        vscode.window.showWarningMessage('ADG: No workspace folder');
        return;
    }

    const result = await runAdgArgs(['install-hooks', folder.uri.fsPath]);
    vscode.window.showInformationMessage('ADG: Git hooks installed');
    outputChannel.appendLine('Git hooks installed successfully');
}

async function cmdCreateRule() {
    const lang = await vscode.window.showQuickPick(
        ['python', 'javascript', 'typescript', 'rust', 'go', 'java'],
        { placeHolder: 'Select language for the rule' }
    );
    if (!lang) { return; }

    const name = await vscode.window.showInputBox({
        prompt: 'Rule name (e.g., no-eval)',
        validateInput: (v) => v ? null : 'Name is required'
    });
    if (!name) { return; }

    outputChannel.appendLine(`\nCreating rule template for ${lang}/${name}...`);
    outputChannel.show(true);

    // Create template file
    const folder = vscode.workspace.workspaceFolders?.[0];
    if (folder) {
        const ruleDir = path.join(folder.uri.fsPath, '.adg', 'rules', lang);
        fs.mkdirSync(ruleDir, { recursive: true });
        const rulePath = path.join(ruleDir, `${name}.yml`);
        fs.writeFileSync(rulePath, [
            `id: ${lang}/${name}`,
            `language: ${lang}`,
            `severity: warning`,
            `category: code_quality`,
            `pattern: ""`,
            `message: ""`,
            `fix_hint: ""`,
        ].join('\n'));
        outputChannel.appendLine(`Rule created: ${rulePath}`);

        // Open in editor
        const doc = await vscode.workspace.openTextDocument(rulePath);
        await vscode.window.showTextDocument(doc);
    }
}

// ─────────────────────────────────────────────────────────────
// ADG Runner
// ─────────────────────────────────────────────────────────────

function getAdgPath(): string {
    const config = vscode.workspace.getConfiguration('adg');
    return config.get<string>('executablePath') || 'adg';
}

function getWorkspaceFolder(): string {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd();
}

function runAdgCheck(target: string): Promise<AdgResult | null> {
    const config = vscode.workspace.getConfiguration('adg');
    const severity = config.get<string>('severityFilter') || 'warning';
    return runAdgArgs(['check', target, '--severity', severity]);
}

function runAdgArgs(args: string[]): Promise<AdgResult | null> {
    return new Promise((resolve) => {
        const adgPath = getAdgPath();

        const child = cp.spawn(adgPath, [...args, '--json'], {
            cwd: getWorkspaceFolder(),
            env: { ...process.env },
            stdio: ['pipe', 'pipe', 'pipe']
        });

        let stdout = '';
        let stderr = '';

        child.stdout.on('data', (data: Buffer) => { stdout += data.toString(); });
        child.stderr.on('data', (data: Buffer) => { stderr += data.toString(); });

        child.on('close', (code: number | null) => {
            if (code === 0 || code === 1) {
                try {
                    const result = JSON.parse(stdout);
                    resolve(result);
                } catch {
                    outputChannel.appendLine(`Failed to parse ADG output: ${stdout.substring(0, 200)}`);
                    resolve(null);
                }
            } else {
                outputChannel.appendLine(`ADG error (exit ${code}): ${stderr}`);
                resolve(null);
            }
        });

        child.on('error', (err: Error) => {
            outputChannel.appendLine(`ADG not found or failed: ${err.message}`);
            vscode.window.showWarningMessage(
                `ADG executable not found. Set "adg.executablePath" in settings.`
            );
            resolve(null);
        });
    });
}

// ─────────────────────────────────────────────────────────────
// Diagnostics
// ─────────────────────────────────────────────────────────────

function severityToVscode(severity: string): vscode.DiagnosticSeverity {
    switch (severity) {
        case 'error': return vscode.DiagnosticSeverity.Error;
        case 'warning': return vscode.DiagnosticSeverity.Warning;
        case 'info': return vscode.DiagnosticSeverity.Information;
        default: return vscode.DiagnosticSeverity.Warning;
    }
}

function updateDiagnostics(issues: AdgIssue[], document: vscode.TextDocument) {
    const diagnostics: vscode.Diagnostic[] = issues
        .filter(issue => normalizePath(issue.file) === normalizePath(document.fileName))
        .map(issue => {
            const line = Math.max(0, issue.line - 1);
            const col = Math.max(0, issue.column - 1);
            const range = new vscode.Range(line, col, line, col + 80);

            const diagnostic = new vscode.Diagnostic(
                range,
                `[${issue.rule_id}] ${issue.message}\nFix: ${issue.fix_hint}`,
                severityToVscode(issue.severity)
            );
            diagnostic.source = 'adg';
            diagnostic.code = issue.rule_id;

            // Attach related info
            if (issue.fix_hint) {
                diagnostic.relatedInformation = [
                    new vscode.DiagnosticRelatedInformation(
                        new vscode.Location(document.uri, range),
                        `Hint: ${issue.fix_hint}`
                    )
                ];
            }

            return diagnostic;
        });

    diagnosticCollection.set(document.uri, diagnostics);
    diagnosticMap.set(document.fileName, diagnostics);
}

function clearDiagnostics(document: vscode.TextDocument) {
    diagnosticCollection.delete(document.uri);
    diagnosticMap.delete(document.fileName);
}

function normalizePath(p: string): string {
    return path.normalize(p).toLowerCase();
}

async function checkDocument(document: vscode.TextDocument) {
    const config = vscode.workspace.getConfiguration('adg');
    const excludePatterns = config.get<string[]>('excludePatterns') || [];
    const fileName = document.fileName;

    // Check exclusions
    if (excludePatterns.some(pat => fileName.includes(pat.replace(/\*\*/g, '')))) {
        return;
    }

    const result = await runAdgCheck(fileName);
    if (result) {
        updateDiagnostics(result.issues, document);
        updateStatusBar();
    }
}

// ─────────────────────────────────────────────────────────────
// Status Bar
// ─────────────────────────────────────────────────────────────

function updateStatusBar() {
    const config = vscode.workspace.getConfiguration('adg');
    if (!config.get<boolean>('showStatusBar')) {
        statusBarItem.hide();
        return;
    }

    let errorCount = 0;
    let warningCount = 0;

    diagnosticMap.forEach((diags) => {
        for (const d of diags) {
            if (d.severity === vscode.DiagnosticSeverity.Error) { errorCount++; }
            else if (d.severity === vscode.DiagnosticSeverity.Warning) { warningCount++; }
        }
    });

    if (errorCount > 0 || warningCount > 0) {
        statusBarItem.text = `$(shield) ADG: ${errorCount}E ${warningCount}W`;
        statusBarItem.tooltip = `ADG Governance: ${errorCount} errors, ${warningCount} warnings`;
        statusBarItem.backgroundColor = errorCount > 0
            ? new vscode.ThemeColor('statusBarItem.errorBackground')
            : new vscode.ThemeColor('statusBarItem.warningBackground');
    } else {
        statusBarItem.text = `$(shield) ADG`;
        statusBarItem.tooltip = 'ADG Governance: All checks passed';
        statusBarItem.backgroundColor = undefined;
    }
    statusBarItem.show();
}

// ─────────────────────────────────────────────────────────────
// Message Display
// ─────────────────────────────────────────────────────────────

function showMessage(result: AdgResult) {
    const total = result.issues.length;
    if (total === 0) {
        vscode.window.showInformationMessage('ADG: All checks passed');
    } else if (result.summary.error > 0) {
        vscode.window.showErrorMessage(
            `ADG: ${result.summary.error} error(s), ${result.summary.warning} warning(s)`
        );
    } else {
        vscode.window.showWarningMessage(
            `ADG: ${result.summary.warning} warning(s), ${result.summary.info} info`
        );
    }
}

// ─────────────────────────────────────────────────────────────
// SARIF Import
// ─────────────────────────────────────────────────────────────

async function importSarifFile(uri: vscode.Uri) {
    try {
        const content = fs.readFileSync(uri.fsPath, 'utf-8');
        const sarif = JSON.parse(content);

        if (!sarif.runs || !Array.isArray(sarif.runs)) {
            return;
        }

        let totalIssues = 0;

        for (const run of sarif.runs) {
            if (!run.results) { continue; }

            const rules = new Map<string, any>();
            if (run.tool?.driver?.rules) {
                for (const rule of run.tool.driver.rules) {
                    rules.set(rule.id, rule);
                }
            }

            for (const result of run.results) {
                const ruleId = result.ruleId || 'unknown';
                const level = result.level || 'warning';
                const message = result.message?.text || 'No message';

                if (result.locations) {
                    for (const loc of result.locations) {
                        const physical = loc.physicalLocation;
                        if (!physical) { continue; }

                        const filePath = physical.artifactLocation?.uri;
                        const line = physical.region?.startLine || 1;
                        const col = physical.region?.startColumn || 1;

                        if (filePath) {
                            const absPath = path.isAbsolute(filePath)
                                ? filePath
                                : path.join(getWorkspaceFolder(), filePath);

                            // Convert SARIF level to vscode severity
                            let severity: vscode.DiagnosticSeverity;
                            switch (level) {
                                case 'error': severity = vscode.DiagnosticSeverity.Error; break;
                                case 'note': severity = vscode.DiagnosticSeverity.Information; break;
                                default: severity = vscode.DiagnosticSeverity.Warning;
                            }

                            const range = new vscode.Range(line - 1, col - 1, line - 1, col + 80);
                            const diagnostic = new vscode.Diagnostic(
                                range,
                                `[${ruleId}] ${message}`,
                                severity
                            );
                            diagnostic.source = 'adg-sarif';
                            diagnostic.code = ruleId;

                            try {
                                diagnosticCollection.append(
                                    vscode.Uri.file(absPath),
                                    [diagnostic]
                                );
                            } catch {
                                // File might not be in workspace
                            }

                            totalIssues++;
                        }
                    }
                }
            }
        }

        vscode.window.showInformationMessage(`ADG: Imported ${totalIssues} issues from SARIF`);
    } catch (err) {
        vscode.window.showErrorMessage(`Failed to import SARIF: ${err}`);
    }
}

// ─────────────────────────────────────────────────────────────
// Code Action Provider (Quick Fix)
// ─────────────────────────────────────────────────────────────

class AdgCodeActionProvider implements vscode.CodeActionProvider {
    provideCodeActions(
        document: vscode.TextDocument,
        range: vscode.Range | vscode.Selection,
        context: vscode.CodeActionContext,
        token: vscode.CancellationToken
    ): vscode.CodeAction[] {
        const config = vscode.workspace.getConfiguration('adg');
        if (!config.get<boolean>('enableQuickFix')) {
            return [];
        }

        const actions: vscode.CodeAction[] = [];

        for (const diagnostic of context.diagnostics) {
            if (diagnostic.source !== 'adg') { continue; }

            const ruleId = diagnostic.code as string;

            // Fix action
            if (ruleId) {
                const fixAction = new vscode.CodeAction(
                    `ADG: Auto-fix "${ruleId}"`,
                    vscode.CodeActionKind.QuickFix
                );
                fixAction.command = {
                    command: 'adg.fix',
                    title: 'ADG Auto-fix',
                    arguments: []
                };
                fixAction.diagnostics = [diagnostic];
                actions.push(fixAction);
            }

            // Suppress action
            if (ruleId) {
                const suppressAction = new vscode.CodeAction(
                    `ADG: Suppress "${ruleId}" (add to skip_patterns)`,
                    vscode.CodeActionKind.QuickFix
                );
                suppressAction.command = {
                    command: 'adg.suppressRule',
                    title: 'Suppress Rule',
                    arguments: [ruleId]
                };
                actions.push(suppressAction);
            }

            // Show documentation action
            if (ruleId) {
                const docAction = new vscode.CodeAction(
                    `ADG: Learn about "${ruleId}"`,
                    vscode.CodeActionKind.QuickFix
                );
                docAction.command = {
                    command: 'vscode.open',
                    title: 'Open Documentation',
                    arguments: [
                        vscode.Uri.parse(`https://github.com/ai-developer-growth/rules#${ruleId.toLowerCase()}`)
                    ]
                };
                actions.push(docAction);
            }
        }

        return actions;
    }
}

// ─────────────────────────────────────────────────────────────
// CodeLens Provider
// ─────────────────────────────────────────────────────────────

class AdgCodeLensProvider implements vscode.CodeLensProvider {
    provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
        const config = vscode.workspace.getConfiguration('adg');
        if (!config.get<boolean>('showCodeLens')) {
            return [];
        }

        const diagnostics = diagnosticMap.get(document.fileName) || [];
        if (diagnostics.length === 0) { return []; }

        const lenses: vscode.CodeLens[] = [];

        // Summary lens at top of file
        const errorCount = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Error).length;
        const warnCount = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Warning).length;
        const infoCount = diagnostics.filter(d => d.severity === vscode.DiagnosticSeverity.Information).length;

        const summary = `$(shield) ADG: ${diagnostics.length} issues` +
            (errorCount ? ` (${errorCount} errors)` : '') +
            (warnCount ? ` (${warnCount} warnings)` : '') +
            (infoCount ? ` (${infoCount} info)` : '');

        lenses.push(new vscode.CodeLens(
            new vscode.Range(0, 0, 0, 0),
            { title: summary, command: 'adg.showOutput', tooltip: 'Show ADG details' }
        ));

        return lenses;
    }
}

// ─────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────

const SUPPORTED_EXTENSIONS = new Set([
    '.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java',
    '.kt', '.rb', '.php', '.swift', '.c', '.cpp', '.cs',
    '.h', '.hh', '.hpp', '.dart', '.scala', '.clj'
]);

function isSupportedFile(filename: string): boolean {
    const ext = path.extname(filename).toLowerCase();
    return SUPPORTED_EXTENSIONS.has(ext);
}
