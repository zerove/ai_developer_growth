use std::collections::HashMap;
use std::process::Command;

use serde::{Deserialize, Serialize};

// ─────────────────────────────────────────────────────────────
// Types matching `adg check --json` output
// ─────────────────────────────────────────────────────────────

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdgIssue {
    pub rule_id: String,
    pub severity: String,
    pub category: String,
    pub file: String,
    pub line: u64,
    pub column: u64,
    pub message: String,
    pub fix_hint: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdgSummary {
    pub error: u64,
    pub warning: u64,
    pub info: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdgCheckResult {
    pub language: String,
    pub framework: Option<String>,
    pub files_checked: u64,
    pub issues: Vec<AdgIssue>,
    pub summary: AdgSummary,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdgFixResult {
    pub fixed: u64,
    pub skipped: u64,
    pub errors: u64,
}

// ─────────────────────────────────────────────────────────────
// Extension state
// ─────────────────────────────────────────────────────────────

pub struct AdgState {
    pub enabled: bool,
    pub severity_filter: String,
    /// Tracks active diagnostics per file path
    pub diagnostics: HashMap<String, Vec<AdgIssue>>,
}

impl Default for AdgState {
    fn default() -> Self {
        Self {
            enabled: true,
            severity_filter: "warning".to_string(),
            diagnostics: HashMap::new(),
        }
    }
}

// ─────────────────────────────────────────────────────────────
// ADG CLI Runner
// ─────────────────────────────────────────────────────────────

pub fn run_adg_check(path: &str, severity: &str) -> Result<AdgCheckResult, String> {
    let output = Command::new("adg")
        .args(["check", path, "--severity", severity, "--json"])
        .output()
        .map_err(|e| format!("Failed to run adg: {}", e))?;

    if !output.status.success() && !output.stdout.is_empty() {
        // Even exit code 1 can have valid JSON output (issues found)
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout).map_err(|e| format!("Failed to parse adg output: {}", e))
}

pub fn run_adg_fix(path: &str) -> Result<AdgFixResult, String> {
    let output = Command::new("adg")
        .args(["fix", "--json", path])
        .output()
        .map_err(|e| format!("Failed to run adg fix: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout).map_err(|e| format!("Failed to parse adg fix output: {}", e))
}

pub fn run_adg_list_rules(language: &str) -> Result<Vec<serde_json::Value>, String> {
    let output = Command::new("adg")
        .args(["list-rules", "--lang", language, "--json"])
        .output()
        .map_err(|e| format!("Failed to list rules: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(&stdout).map_err(|e| format!("Failed to parse rules output: {}", e))
}

/// Detect language from file extension (matches adg's built-in detection)
pub fn detect_language(path: &std::path::Path) -> Option<String> {
    let ext = path.extension()?.to_str()?.to_lowercase();
    let lang = match ext.as_str() {
        "py" => "python",
        "js" | "jsx" => "javascript",
        "ts" | "tsx" => "typescript",
        "rs" => "rust",
        "go" => "go",
        "java" => "java",
        "kt" | "kts" => "kotlin",
        "rb" => "ruby",
        "php" => "php",
        "cs" => "csharp",
        "swift" => "swift",
        "c" | "h" => "c",
        "cpp" | "hpp" | "cc" | "cxx" => "cpp",
        "scala" => "scala",
        "dart" => "dart",
        "lua" => "lua",
        "hs" => "haskell",
        "clj" | "cljs" | "cljc" => "clojure",
        "r" | "R" => "r",
        "pl" | "pm" => "perl",
        "zig" => "zig",
        _ => return None,
    };
    Some(lang.to_string())
}

/// Convert ADG severity to Zed diagnostic severity (0=error, 1=warning, 2=info)
pub fn severity_to_zed(severity: &str) -> u64 {
    match severity {
        "error" => 0,
        "warning" => 1,
        _ => 2,
    }
}

/// Convert ADG issues to Zed diagnostic entries
pub fn issues_to_zed_diagnostics(issues: &[AdgIssue]) -> Vec<serde_json::Value> {
    issues
        .iter()
        .map(|issue| {
            let line = issue.line.saturating_sub(1);
            serde_json::json!({
                "range": {
                    "start": {"line": line, "character": issue.column.saturating_sub(1)},
                    "end": {"line": line, "character": issue.column + 80},
                },
                "severity": severity_to_zed(&issue.severity),
                "source": "adg",
                "message": format!("[{}] {}", issue.rule_id, issue.message),
                "code": issue.rule_id,
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_language() {
        assert_eq!(detect_language(std::path::Path::new("main.py")), Some("python".into()));
        assert_eq!(detect_language(std::path::Path::new("app.tsx")), Some("typescript".into()));
        assert_eq!(detect_language(std::path::Path::new("main.rs")), Some("rust".into()));
        assert_eq!(detect_language(std::path::Path::new("unknown.xyz")), None);
    }

    #[test]
    fn test_severity_conversion() {
        assert_eq!(severity_to_zed("error"), 0);
        assert_eq!(severity_to_zed("warning"), 1);
        assert_eq!(severity_to_zed("info"), 2);
        assert_eq!(severity_to_zed("unknown"), 2);
    }

    #[test]
    fn test_issues_to_diagnostics() {
        let issues = vec![AdgIssue {
            rule_id: "test-rule".into(),
            severity: "error".into(),
            category: "test".into(),
            file: "/test.py".into(),
            line: 10,
            column: 5,
            message: "Test issue".into(),
            fix_hint: "Fix it".into(),
        }];
        let diags = issues_to_zed_diagnostics(&issues);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0]["severity"], 0);
        assert!(diags[0]["message"].as_str().unwrap().contains("test-rule"));
    }
}
