use gpui::{actions, Action, AppContext, Global, MutableAppContext};
use language::{Language, LanguageServerId};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

actions!(
    adg,
    [
        CheckFile,
        CheckProject,
        CheckIncremental,
        ListRules,
        ShowOutput,
    ]
);

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdgIssue {
    pub rule_id: String,
    pub severity: String,
    pub category: String,
    pub file: String,
    pub line: usize,
    pub column: usize,
    pub message: String,
    pub fix_hint: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdgResult {
    pub language: String,
    pub framework: Option<String>,
    pub files_checked: usize,
    pub issues: Vec<AdgIssue>,
    pub summary: AdgSummary,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdgSummary {
    pub error: usize,
    pub warning: usize,
    pub info: usize,
}

pub struct AdgGlobal {
    pub enabled: bool,
    pub severity_filter: String,
}

impl Global for AdgGlobal {}

pub fn init(cx: &mut MutableAppContext) {
    cx.set_global(AdgGlobal {
        enabled: true,
        severity_filter: "warning".to_string(),
    });

    cx.add_action(check_file_action);
    cx.add_action(check_project_action);
    cx.add_action(check_incremental_action);
    cx.add_action(list_rules_action);
}

fn check_file_action(action: &CheckFile, cx: &mut MutableAppContext) {
    let workspace = cx.window_root()?;
    let workspace = workspace.read(cx);
    
    if let Some(file) = workspace.active_file() {
        let path = file.path.to_string_lossy().to_string();
        run_adg_check(&path, cx);
    }
    
    None
}

fn check_project_action(action: &CheckProject, cx: &mut MutableAppContext) {
    let workspace = cx.window_root()?;
    let workspace = workspace.read(cx);
    let root = workspace.root()?;
    
    let path = root.to_string_lossy().to_string();
    run_adg_check(&path, cx);
    
    None
}

fn check_incremental_action(action: &CheckIncremental, cx: &mut MutableAppContext) {
    let workspace = cx.window_root()?;
    let workspace = workspace.read(cx);
    let root = workspace.root()?;
    
    let path = root.to_string_lossy().to_string();
    run_adg_incremental(&path, cx);
    
    None
}

fn list_rules_action(action: &ListRules, cx: &mut MutableAppContext) {
    let language = cx.window_root()?
        .read(cx)
        .active_file()
        .map(|f| detect_language(&f.path));
    
    if let Some(lang) = language {
        run_adg_list_rules(&lang, cx);
    }
    
    None
}

fn run_adg_check(path: &str, cx: &mut MutableAppContext) {
    let global = cx.global::<AdgGlobal>();
    let severity = &global.severity_filter;
    
    let output = std::process::Command::new("adg")
        .args(&["check", path, "--severity", severity, "--json"])
        .output();
    
    match output {
        Ok(output) => {
            if let Ok(result) = serde_json::from_slice::<AdgResult>(&output.stdout) {
                // Update diagnostics in Zed
                update_zed_diagnostics(&result, cx);
            }
        }
        Err(e) => {
            eprintln!("ADG check failed: {}", e);
        }
    }
}

fn run_adg_incremental(path: &str, cx: &mut MutableAppContext) {
    let output = std::process::Command::new("adg")
        .args(&["check", path, "--since", "HEAD", "--json"])
        .output();
    
    match output {
        Ok(output) => {
            if let Ok(result) = serde_json::from_slice::<AdgResult>(&output.stdout) {
                update_zed_diagnostics(&result, cx);
            }
        }
        Err(e) => {
            eprintln!("ADG incremental check failed: {}", e);
        }
    }
}

fn run_adg_list_rules(language: &str, cx: &mut MutableAppContext) {
    let output = std::process::Command::new("adg")
        .args(&["list-rules", "--lang", language, "--json"])
        .output();
    
    match output {
        Ok(output) => {
            // Show rules in a buffer
            let rules = String::from_utf8_lossy(&output.stdout);
            // Zed would show this in a new buffer
            eprintln!("Rules for {}:\n{}", language, rules);
        }
        Err(e) => {
            eprintln!("Failed to list rules: {}", e);
        }
    }
}

fn detect_language(path: &std::path::Path) -> String {
    match path.extension().and_then(|e| e.to_str()) {
        Some("py") => "python",
        Some("js") | Some("jsx") => "javascript",
        Some("ts") | Some("tsx") => "typescript",
        Some("rs") => "rust",
        Some("go") => "go",
        Some("java") => "java",
        Some("kt") => "kotlin",
        Some("rb") => "ruby",
        Some("php") => "php",
        _ => "unknown",
    }.to_string()
}

fn update_zed_diagnostics(result: &AdgResult, cx: &mut MutableAppContext) {
    // Zed uses its own diagnostic system
    // This would integrate with Zed's language server protocol
    eprintln!("Found {} issues in {}", result.issues.len(), result.language);
}
