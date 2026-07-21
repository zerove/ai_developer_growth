import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    console.log('AI Developer Growth extension activated');

    // Skill Assessment command
    const assessCmd = vscode.commands.registerCommand('ai-growth.assess', async () => {
        const dimensions = [
            { name: 'AI 理解力', key: 'aiComprehension' },
            { name: '工程整合', key: 'engineeringIntegration' },
            { name: '学习方法', key: 'learningMethod' },
            { name: '创新思维', key: 'innovationThinking' },
            { name: '输出质量', key: 'outputQuality' },
        ];

        const scores: Record<string, number> = {};

        for (const dim of dimensions) {
            const input = await vscode.window.showInputBox({
                prompt: `Rate your ${dim.name} (0-100)`,
                validateInput: (value) => {
                    const num = parseInt(value);
                    if (isNaN(num) || num < 0 || num > 100) {
                        return 'Please enter a number between 0 and 100';
                    }
                    return null;
                },
            });
            if (input === undefined) return;
            scores[dim.key] = parseInt(input);
        }

        const overall = Object.values(scores).reduce((a, b) => a + b, 0) / 5;
        const level = getLevel(overall / 100);

        const panel = vscode.window.createWebviewPanel(
            'aiGrowthResult',
            'Assessment Result',
            vscode.ViewColumn.One,
            { enableScripts: false }
        );

        panel.webview.html = getResultHtml(scores, overall, level);
        vscode.window.showInformationMessage(`Assessment complete! Level: ${level}`);
    });

    // Progress command
    const progressCmd = vscode.commands.registerCommand('ai-growth.progress', async () => {
        const progress = context.globalState.get('learningProgress', [] as string[]);
        if (progress.length === 0) {
            vscode.window.showInformationMessage('No learning progress yet. Start with an assessment!');
        } else {
            vscode.window.showInformationMessage(`You've completed ${progress.length} documents!`);
        }
    });

    // Recommend command
    const recommendCmd = vscode.commands.registerCommand('ai-growth.recommend', async () => {
        const docs = [
            'mindset/ai-native-thinking.md - AI 原生思维',
            'mindset/capability-model.md - 能力模型',
            'tools/ai-coding-assistants.md -,
            'efficiency/full-cycle-workflow.md - 全周期工作流',
        ];
        const selected = await vscode.window.showQuickPick(docs, {
            placeHolder: 'Select a document to start learning',
        });
        if (selected) {
            const docPath = selected.split(' - ')[0];
            const progress = context.globalState.get('learningProgress', [] as string[]);
            if (!progress.includes(docPath)) {
                progress.push(docPath);
                await context.globalState.update('learningProgress', progress);
            }
            vscode.window.showInformationMessage(`Started learning: ${docPath}`);
        }
    });

    context.subscriptions.push(assessCmd, progressCmd, recommendCmd);
}

function getLevel(score: number): string {
    if (score < 0.2) return 'L0 - 初学者';
    if (score < 0.4) return 'L1 - 进阶';
    if (score < 0.6) return 'L2 - 胜任';
    if (score < 0.8) return 'L3 - 精通';
    return 'L4 - 专家';
}

function getResultHtml(scores: Record<string, number>, overall: number, level: string): string {
    return `<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: sans-serif; padding: 20px; }
        .score { margin: 8px 0; }
        .bar { background: #e0e0e0; height: 20px; border-radius: 4px; }
        .fill { background: #2563eb; height: 100%; border-radius: 4px; }
        .overall { font-size: 2em; color: #2563eb; text-align: center; margin: 20px 0; }
        .level { text-align: center; color: #666; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="overall">${overall.toFixed(0)}%</div>
    <div class="level">${level}</div>
    <div class="score"><strong>AI 理解力</strong><div class="bar"><div class="fill" style="width:${scores.aiComprehension}%"></div></div></div>
    <div class="score"><strong>工程整合</strong><div class="bar"><div class="fill" style="width:${scores.engineeringIntegration}%"></div></div></div>
    <div class="score"><strong>学习方法</strong><div class="bar"><div class="fill" style="width:${scores.learningMethod}%"></div></div></div>
    <div class="score"><strong>创新思维</strong><div class="bar"><div class="fill" style="width:${scores.innovationThinking}%"></div></div></div>
    <div class="score"><strong>输出质量</strong><div class="bar"><div class="fill" style="width:${scores.outputQuality}%"></div></div></div>
</body>
</html>`;
}

export function deactivate() {}
