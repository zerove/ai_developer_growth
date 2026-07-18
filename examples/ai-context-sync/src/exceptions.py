class AISyncError(Exception):
    """Base exception for all AI-Context-Sync errors."""

class ConfigError(AISyncError):
    """Configuration loading or validation error."""

class LLMError(AISyncError):
    """LLM API call failure."""

class AuditError(AISyncError):
    """Specification audit failure."""

class GitError(AISyncError):
    """Git operation failure."""

class SynthesisError(AISyncError):
    """Context synthesis failure."""

class TestExecutionError(AISyncError):
    """Test runner execution failure."""

class WorkflowError(AISyncError):
    """Orchestrator workflow failure."""

class GuardError(AISyncError):
    """Architecture guard check failure."""
