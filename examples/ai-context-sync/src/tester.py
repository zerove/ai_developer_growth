import subprocess
import tempfile
import os
import shutil
import sys
from typing import Callable, NamedTuple, Optional
from .logger import logger
from .exceptions import TestExecutionError

class TestResult(NamedTuple):
    success: bool
    output: str
    exit_code: int

class TestRunner:
    """
    TestRunner is responsible for executing verification tests in an isolated
    sandbox environment and capturing the output.
    """
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def _sanitize_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = ""
        sensitive_keys = [
            "AI_SYNC_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
            "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "GH_TOKEN",
        ]
        for key in sensitive_keys:
            env.pop(key, None)
        return env

    @staticmethod
    def _make_sandbox_limits() -> Optional[Callable[[], None]]:
        if sys.platform != "linux":
            return None
        try:
            import resource
            def _limit() -> None:
                resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
                resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
            return _limit
        except (ImportError, ValueError, OSError):
            return None

    def run_test(self, test_code: str, target_files: list[str]) -> TestResult:
        """
        Executes the provided test_code against the target_files in a sandboxed
        subprocess with resource limits, environment cleanup, and process
        isolation.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            for file_path in target_files:
                if os.path.exists(file_path):
                    dest_path = os.path.join(tmpdir, file_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(file_path, dest_path)
                else:
                    logger.warning(f"Target file {file_path} not found for testing.")

            test_file_path = os.path.join(tmpdir, "test_verification.py")
            with open(test_file_path, "w", encoding="utf-8") as f:
                f.write(test_code)

            env = self._sanitize_env()
            env["PYTHONPATH"] = tmpdir + os.pathsep + env.get("PYTHONPATH", "")

            sandbox_limits = self._make_sandbox_limits()

            try:
                logger.info(f"🧪 Running verification test in {tmpdir}...")
                result = subprocess.run(
                    ["pytest", test_file_path, "-q"],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir,
                    start_new_session=True,
                    preexec_fn=sandbox_limits,
                    env=env,
                )
                return TestResult(
                    success=result.returncode == 0,
                    output=result.stdout + result.stderr,
                    exit_code=result.returncode,
                )
            except FileNotFoundError:
                logger.warning("pytest not found, falling back to unittest...")
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "unittest", test_file_path],
                        capture_output=True,
                        text=True,
                        timeout=self.timeout,
                        cwd=tmpdir,
                        start_new_session=True,
                        preexec_fn=sandbox_limits,
                        env=env,
                    )
                    return TestResult(
                        success=result.returncode == 0,
                        output=result.stdout + result.stderr,
                        exit_code=result.returncode,
                    )
                except (OSError, subprocess.SubprocessError) as e:
                    return TestResult(False, f"Execution failed: {str(e)}", -1)
            except subprocess.TimeoutExpired as e:
                stdout = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
                return TestResult(False, f"Test timed out after {self.timeout}s\n{stdout}", 124)
            except (OSError, subprocess.SubprocessError) as e:
                return TestResult(False, f"Unexpected error: {str(e)}", -1)

