import os
import time
from typing import Any, TYPE_CHECKING
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .logger import logger

if TYPE_CHECKING:
    from .core import AIContextSync


class AuditHandler(FileSystemEventHandler):
    def __init__(self, sync_tool: "AIContextSync") -> None:
        self.sync_tool = sync_tool
        self.last_trigger: float = 0
        self.debounce_interval: float = self.sync_tool.config.settings.watcher_debounce

    def on_modified(self, event: Any) -> None:
        if event.is_directory:
            return
        
        # Filter out irrelevant files
        filename = str(os.path.basename(event.src_path))
        if filename.startswith('.') or any(str(ignore) in event.src_path for ignore in self.sync_tool.config.settings.ignore):
            return

        # Debounce to avoid multiple triggers for a single save
        current_time = time.time()
        if current_time - self.last_trigger < self.debounce_interval:
            return
        self.last_trigger = current_time

        logger.info(f"📝 File changed: {filename}. Triggering real-time audit...")
        
        # Perform structured audit
        violations = self.sync_tool.auditor.audit("N/A", "Real-time watch") 
        
        # Format report and generate fixes for Critical violations
        if not violations:
            report = "✅ All changes comply with specifications."
        else:
            report_lines = [f"Found {len(violations)} violation(s):"]
            for i, v in enumerate(violations, 1):
                line = f"{i}. [{v.severity}] {v.rule_id}: {v.message}"
                report_lines.append(line)
                
                if v.severity == 'Critical':
                    specs = self.sync_tool.auditor.get_relevant_specs("N/A")
                    fix = self.sync_tool.auditor.generate_fix(v, "N/A", specs)
                    report_lines.append(f"   💡 Suggested Fix:\n   ```python\n   {fix}\n   ```\n   👉 Run `dx apply-fix {v.rule_id}` to apply.")
            report = "\n".join(report_lines)
        
        # Write to live report file
        self._write_live_report(filename, report)

    def _write_live_report(self, filename: str, report: str) -> None:
        report_rel = self.sync_tool.config.settings.live_report_path
        config_dir = os.path.dirname(os.path.abspath(self.sync_tool.config.config_path))
        report_path = os.path.join(config_dir, report_rel)
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# 🔴 AI-Native Real-time Audit Dashboard\n\n")
            f.write(f"**Last Updated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Current File:** `{filename}`\n\n")
            f.write(f"## Audit Results\n\n")
            f.write(f"{report}\n\n")
            f.write(f"---\n*Tip: Keep this file open in a split pane to see instant feedback.*")

class WatchManager:
    def __init__(self, sync_tool: "AIContextSync") -> None:
        self.sync_tool = sync_tool
        self.observer = Observer()

    def start(self, path: str = ".") -> None:
        logger.info(f"🛡️ Starting Real-time Guard on path: {path}")
        event_handler = AuditHandler(self.sync_tool)
        self.observer.schedule(event_handler, path, recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        logger.info("🛑 Stopping Real-time Guard...")
        self.observer.stop()
        self.observer.join()
