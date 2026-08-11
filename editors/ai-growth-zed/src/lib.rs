use zed_extension_api as zed;

struct AIGrowthExtension;

impl zed::Extension for AIGrowthExtension {
    fn new() -> Self {
        Self
    }

    fn language_server_command(
        &mut self,
        _language_server_id: &zed::LanguageServerId,
        _worktree: &zed::Worktree,
    ) -> zed::Result<zed::Command> {
        Ok(zed::Command {
            command: "python3".to_string(),
            args: vec!["-m".to_string(), "tools.scripts.rules_engine.lsp_server".to_string()],
            env: vec![],
        })
    }
}

zed::register_extension!(AIGrowthExtension);
