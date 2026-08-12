import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

interface SkillScores {
    aiComprehension: number;
    engineeringIntegration: number;
    learningMethod: number;
    innovationThinking: number;
    outputQuality: number;
}

interface LearningProgress {
    documents: string[];
    lastAssessment: number;
    level: string;
}

interface DocMetadata {
    id: string;
    title: string;
    category: string;
    difficulty: string;
    tags: string[];
    readingTime: number;
    updated: string;
}

const SKILL_DIMENSIONS: Array<{ key: keyof SkillScores; name: string; description: string }> = [
    { key: 'aiComprehension', name: 'AI 理解力', description: '对 AI 能力边界、提示词工程、模型选择的理解深度' },
    { key: 'engineeringIntegration', name: '工程整合', description: '将 AI 输出整合到工程流程（CI/CD、测试、架构）的能力' },
    { key: 'learningMethod', name: '学习方法', description: '利用 AI 加速学习新技术、理解代码库、构建知识图谱的方法论' },
    { key: 'innovationThinking', name: '创新思维', description: '从"实现者"转向"定义者"，用 AI 探索新架构、新产品的能力' },
    { key: 'outputQuality', name: '输出质量', description: '对 AI 生成代码的审查、重构、安全加固、性能优化的把控力' },
];

const LEVELS = [
    { min: 0, max: 19, label: 'L0 - 观察者', desc: '刚开始接触 AI 工具，主要观望' },
    { min: 20, max: 39, label: 'L1 - 尝试者', desc: '能用 AI 完成简单任务，但缺乏系统方法' },
    { min: 40, max: 59, label: 'L2 - 实践者', desc: '熟练使用 AI 协作开发，有固定工作流' },
    { min: 60, max: 79, label: 'L3 - 专家', desc: '深度整合 AI 到全周期，能指导团队采用' },
    { min: 80, max: 100, label: 'L4 - 架构师', desc: '定义 AI 协作范式，构建组织级 AI 能力体系' },
];

const KNOWLEDGE_DOCS: DocMetadata[] = [
    { id: 'mindset/ai-native-thinking', title: 'AI 原生思维', category: '认知层', difficulty: '入门', tags: ['mindset', 'AI'], readingTime: 15, updated: '2026-07-28' },
    { id: 'mindset/capability-model', title: '开发者能力模型 (L0-L4)', category: '认知层', difficulty: '入门', tags: ['mindset', 'career'], readingTime: 10, updated: '2026-07-28' },
    { id: 'tools/ai-coding-assistants', title: 'AI 编码助手选型指南', category: '工具层', difficulty: '入门', tags: ['tools', 'selection'], readingTime: 20, updated: '2026-07-30' },
    { id: 'efficiency/full-cycle-workflow', title: '全周期工作流', category: '效率层', difficulty: '进阶', tags: ['workflow', 'SDLC'], readingTime: 25, updated: '2026-08-01' },
    { id: 'efficiency/ai-debugging-standards', title: 'AI 辅助调试规范', category: '效率层', difficulty: '进阶', tags: ['debugging', 'AI'], readingTime: 20, updated: '2026-07-25' },
    { id: 'governance/ai-governance', title: 'AI 治理框架', category: '治理层', difficulty: '高级', tags: ['governance', 'quality'], readingTime: 30, updated: '2026-08-03' },
];

export function activate(context: vscode.ExtensionContext): void {
    // Extension activated - register commands below

    const commands = [
        vscode.commands.registerCommand('ai-growth.assess', () => runAssessment(context)),
        vscode.commands.registerCommand('ai-growth.progress', () => showProgress(context)),
        vscode.commands.registerCommand('ai-growth.recommend', () => showRecommendations(context)),
        vscode.commands.registerCommand('ai-growth.browse', () => browseKnowledgeBase(context)),
        vscode.commands.registerCommand('ai-growth.quickAssess', () => quickAssessment(context)),
    ];

    context.subscriptions.push(...commands);

    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBar.text = '$(growth) AI Growth';
    statusBar.tooltip = 'AI Developer Growth - Click to open panel';
    statusBar.command = 'ai-growth.browse';
    statusBar.show();
    context.subscriptions.push(statusBar);

    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('ai-growth.dashboard', new DashboardProvider(context.extensionUri))
    );
}

async function runAssessment(context: vscode.ExtensionContext) {
    const scores: SkillScores = {
        aiComprehension: 0,
        engineeringIntegration: 0,
        learningMethod: 0,
        innovationThinking: 0,
        outputQuality: 0,
    };

    for (const dim of SKILL_DIMENSIONS) {
        const input = await vscode.window.showInputBox({
            prompt: `${dim.name}: ${dim.description}`,
            placeHolder: '0-100',
            validateInput: (value) => {
                const num = parseInt(value);
                if (isNaN(num) || num < 0 || num > 100) {
                    return 'Please enter a number between 0 and 100';
                }
                return null;
            },
        });
        if (input === undefined) {
            return;
        }
        scores[dim.key] = parseInt(input);
    }

    const overall = Math.round(Object.values(scores).reduce((a, b) => a + b, 0) / 5);
    const levelInfo = LEVELS.find(l => overall >= l.min && overall <= l.max) || LEVELS[0];

    const progress: LearningProgress = {
        documents: [],
        lastAssessment: Date.now(),
        level: levelInfo.label,
    };
    await context.globalState.update('aiGrowthProgress', progress);
    await context.globalState.update('aiGrowthScores', scores);

    const panel = vscode.window.createWebviewPanel(
        'aiGrowthAssessment',
        'AI Growth Skill Assessment Result',
        vscode.ViewColumn.One,
        { enableScripts: true }
    );
    panel.webview.html = getAssessmentHtml(scores, overall, levelInfo);
    vscode.window.showInformationMessage(`Assessment complete! ${levelInfo.label} (${overall}%)`);
}

async function quickAssessment(context: vscode.ExtensionContext) {
    const quickDims = SKILL_DIMENSIONS.slice(0, 3);
    const scores: Partial<SkillScores> = {};

    for (const dim of quickDims) {
        const input = await vscode.window.showQuickPick(
            ['0-20', '21-40', '41-60', '61-80', '81-100'],
            { placeHolder: `${dim.name}: ${dim.description}`, title: 'Quick Assessment (3/3)' }
        );
        if (!input) return;
        const mid = (parseInt(input.split('-')[0]) + parseInt(input.split('-')[1])) / 2;
        scores[dim.key] = mid;
    }

    const avg = Object.values(scores).reduce((a, b) => a + b, 0) / 3;
    const estimated = Math.round(avg);
    const levelInfo = LEVELS.find(l => estimated >= l.min && estimated <= l.max) || LEVELS[0];

    vscode.window.showInformationMessage(
        `Quick Assessment: ${levelInfo.label} (~${estimated}%) - Run "AI Growth: Skill Assessment" for full assessment`
    );
}

async function showProgress(context: vscode.ExtensionContext) {
    const progress = context.globalState.get<LearningProgress>('aiGrowthProgress');
    const scores = context.globalState.get<SkillScores>('aiGrowthScores');

    if (!progress) {
        const action = await vscode.window.showInformationMessage(
            'No assessment record yet',
            'Start Assessment', 'Quick Assessment'
        );
        if (action === 'Start Assessment') await runAssessment(context);
        else if (action === 'Quick Assessment') await quickAssessment(context);
        return;
    }

    const panel = vscode.window.createWebviewPanel(
        'aiGrowthProgress',
        'AI Growth Learning Progress',
        vscode.ViewColumn.One,
        { enableScripts: true }
    );
    panel.webview.html = getProgressHtml(progress, scores);
}

async function showRecommendations(context: vscode.ExtensionContext) {
    const scores = context.globalState.get<SkillScores>('aiGrowthScores');
    if (!scores) {
        await vscode.window.showInformationMessage('Please complete skill assessment first', 'Start Assessment');
        return;
    }

    const sorted = Object.entries(scores).sort((a, b) => a[1] - b[1]);
    const weak = sorted.slice(0, 2);

    const recommendations = weak.map(([key, score]) => {
        const dim = SKILL_DIMENSIONS.find(d => d.key === key);
        if (!dim) return { dimension: key, score, docs: [] };
        const relevantDocs = KNOWLEDGE_DOCS.filter(doc => doc.tags.some(t => dim.name.includes(t) || t.includes(dim.name.split(' ')[0])));
        return {
            dimension: dim.name,
            score,
            docs: relevantDocs.slice(0, 2),
        };
    });

    const panel = vscode.window.createWebviewPanel(
        'aiGrowthRecommend',
        'AI Growth Personalized Recommendations',
        vscode.ViewColumn.One,
        { enableScripts: true }
    );
    panel.webview.html = getRecommendHtml(recommendations);
}

async function browseKnowledgeBase(context: vscode.ExtensionContext) {
    const panel = vscode.window.createWebviewPanel(
        'aiGrowthKnowledge',
        'AI Growth Knowledge Base',
        vscode.ViewColumn.One,
        { enableScripts: true }
    );
    panel.webview.html = getKnowledgeHtml(KNOWLEDGE_DOCS);
    panel.webview.onDidReceiveMessage(async (msg) => {
        if (msg.type === 'openDoc') {
            vscode.window.showInformationMessage(`Opening document: ${msg.docId}`);
        }
    });
}

class DashboardProvider implements vscode.WebviewViewProvider {
    constructor(private readonly extensionUri: vscode.Uri) {}

    resolveWebviewView(webviewView: vscode.WebviewView) {
        webviewView.webview.options = { enableScripts: true };
        webviewView.webview.html = this.getDashboardHtml();
        webviewView.webview.onDidReceiveMessage(async (msg) => {
            switch (msg.command) {
                case 'assess':
                    await vscode.commands.executeCommand('ai-growth.assess');
                    break;
                case 'progress':
                    await vscode.commands.executeCommand('ai-growth.progress');
                    break;
                case 'recommend':
                    await vscode.commands.executeCommand('ai-growth.recommend');
                    break;
            }
        });
    }

    getDashboardHtml(): string {
        // Webview HTML - no file handles to manage
        return `<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: var(--vscode-font-family); padding: 16px; color: var(--vscode-foreground); background: var(--vscode-editor-background); }
        .header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
        .icon { font-size: 24px; }
        .title { font-size: 16px; font-weight: 600; }
        .btn { display: block; width: 100%; padding: 10px 12px; margin: 8px 0; border: none; border-radius: 4px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); cursor: pointer; font-size: 13px; text-align: left; }
        .btn:hover { background: var(--vscode-button-hoverBackground); }
        .btn.secondary { background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); }
        .stat { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--vscode-panel-border); }
    </style>
</head>
<body>
    <div class="header"><span class="icon">🌱</span><span class="title">AI Developer Growth</span></div>
    <button class="btn" onclick="send('assess')">📊 Skill Assessment</button>
    <button class="btn" onclick="send('progress')">📈 Learning Progress</button>
    <button class="btn" onclick="send('recommend')">🎯 Personalized Recommendations</button>
    <button class="btn secondary" onclick="vscode.open('https://github.com/zerove/ai_developer_growth')">📚 View Knowledge Base</button>
    <script>
        const vscode = acquireVsCodeApi();
        function send(cmd) { vscode.postMessage({ command: cmd }); }
    </script>
</body>
</html>`;
    }
}

function getAssessmentHtml(scores: SkillScores, overall: number, level: typeof LEVELS[0]): string {
    const bars = SKILL_DIMENSIONS.map(d => `
        <div class="skill">
            <div class="skill-header"><span>${d.name}</span><span>${scores[d.key]}</span></div>
            <div class="bar"><div class="fill" style="width:${scores[d.key]}%"></div></div>
        </div>
    `).join('');

    return `<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-foreground); background: var(--vscode-editor-background); }
        .overall { text-align: center; margin: 20px 0; }
        .score-value { font-size: 48px; font-weight: 700; color: var(--vscode-textLink-foreground); }
        .level { font-size: 18px; color: var(--vscode-descriptionForeground); margin-bottom: 8px; }
        .desc { color: var(--vscode-descriptionForeground); margin-bottom: 24px; }
        .skill { margin: 16px 0; }
        .skill-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
        .bar { height: 8px; background: var(--vscode-progressBar-background); border-radius: 4px; overflow: hidden; }
        .fill { height: 100%; background: var(--vscode-progressBar-background); border-radius: 4px; }
    </style>
</head>
<body>
    <div class="overall">
        <div class="level">${level.label}</div>
        <div class="score-value">${overall}%</div>
        <div class="desc">${level.desc}</div>
    </div>
    <div class="skills">${bars}</div>
</body>
</html>`;
}

function getProgressHtml(progress: LearningProgress, scores: SkillScores | undefined): string {
    const lastDate = progress.lastAssessment ? new Date(progress.lastAssessment).toLocaleDateString() : 'Not assessed';
    const docCount = progress.documents?.length || 0;
    return `<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-foreground); background: var(--vscode-editor-background); }
        .stat { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid var(--vscode-panel-border); }
        .stat-label { color: var(--vscode-descriptionForeground); }
        .stat-value { font-weight: 600; }
        .progress-list { margin-top: 16px; }
        .progress-item { padding: 8px; background: var(--vscode-textBlockQuote-background); border-radius: 4px; margin: 4px 0; font-size: 13px; }
    </style>
</head>
<body>
    <h3>Learning Progress Overview</h3>
    <div class="stat"><span class="stat-label">Current Level</span><span class="stat-value">${progress.level}</span></div>
    <div class="stat"><span class="stat-label">Last Assessment</span><span class="stat-value">${lastDate}</span></div>
    <div class="stat"><span class="stat-label">Documents Completed</span><span class="stat-value">${docCount}</span></div>
    ${scores ? `
    <h4>Dimension Scores</h4>
    ${SKILL_DIMENSIONS.map(d => `<div class="stat"><span class="stat-label">${d.name}</span><span class="stat-value">${scores[d.key]}</span></div>`).join('')}
    ` : ''}
    <div class="progress-list">
        <div class="progress-item">No learning records yet. Complete assessment to see recommended documents.</div>
    </div>
</body>
</html>`;
}

function getRecommendHtml(recommendations: Array<{dimension: string, score: number, docs: DocMetadata[]}>): string {
    const items = recommendations.map(r => `
        <div class="rec">
            <h4>${r.dimension} (${r.score}%)</h4>
            ${r.docs.map(d => `<div class="doc"><a href="#" data-id="${d.id}">${d.title}</a> <span class="meta">[${d.category}] ${d.readingTime}min</span></div>`).join('')}
        </div>
    `).join('');

    return `<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-foreground); background: var(--vscode-editor-background); }
        .rec { margin-bottom: 20px; padding: 16px; background: var(--vscode-textBlockQuote-background); border-radius: 8px; border-left: 4px solid var(--vscode-textLink-foreground); }
        .doc { margin: 8px 0; }
        .doc a { color: var(--vscode-textLink-foreground); text-decoration: none; }
        .meta { color: var(--vscode-descriptionForeground); font-size: 12px; margin-left: 8px; }
    </style>
</head>
<body>
    <h3>Personalized Recommendations Based on Weak Areas</h3>
    ${items}
    <script>
        document.querySelectorAll('a').forEach(a => a.addEventListener('click', e => {
            e.preventDefault();
            acquireVsCodeApi().postMessage({ type: 'openDoc', docId: a.dataset.id });
        }));
    </script>
</body>
</html>`;
}

function getKnowledgeHtml(docs: DocMetadata[]): string {
    const cats = [...new Set(docs.map(d => d.category))];
    return `<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: var(--vscode-font-family); padding: 16px; color: var(--vscode-foreground); background: var(--vscode-editor-background); }
        .cat { margin-bottom: 16px; }
        .cat-title { font-weight: 600; color: var(--vscode-textLink-foreground); margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid var(--vscode-panel-border); }
        .doc { padding: 8px; margin: 4px 0; background: var(--vscode-textBlockQuote-background); border-radius: 4px; cursor: pointer; transition: background 0.15s; }
        .doc:hover { background: var(--vscode-list-hoverBackground); }
        .doc-title { font-weight: 500; }
        .doc-meta { font-size: 11px; color: var(--vscode-descriptionForeground); margin-top: 4px; }
    </style>
</head>
<body>
    ${cats.map(cat => `
        <div class="cat">
            <div class="cat-title">${cat}</div>
            ${docs.filter(d => d.category === cat).map(d => `
                <div class="doc" data-id="${d.id}">
                    <div class="doc-title">${d.title}</div>
                    <div class="doc-meta">${d.difficulty} • ${d.readingTime}min • ${d.updated}</div>
                </div>
            `).join('')}
        </div>
    `).join('')}
    <script>
        document.querySelectorAll('.doc').forEach(d => d.addEventListener('click', () => {
            acquireVsCodeApi().postMessage({ type: 'openDoc', docId: d.dataset.id });
        }));
    </script>
</body>
</html>`;
}

export function deactivate(): void {}
