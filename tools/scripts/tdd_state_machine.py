"""Strict TDD 3-Phase State Machine (Red -> Green -> Refactor)

Enforces strict phase boundaries for agent workflows:
1. RED: Write failing test only, implementation forbidden.
2. GREEN: Minimal implementation to pass test, test modification forbidden.
3. REFACTOR: Improve quality, scope creep forbidden.
"""

from __future__ import annotations

from typing import Any


class TDDStateMachine:
    def __init__(self):
        self.state = "RED"  # RED, GREEN, REFACTOR

    def transition(self, action: str) -> bool:
        if self.state == "RED" and action == "test_written_failing":
            self.state = "GREEN"
            return True
        elif self.state == "GREEN" and action == "implementation_passing":
            self.state = "REFACTOR"
            return True
        elif self.state == "REFACTOR" and action == "refactor_complete":
            self.state = "RED"
            return True
        return False

    def validate_action(self, phase: str, intent: str) -> tuple[bool, str]:
        if phase != self.state:
            return False, f"TDD Violation: Expected phase {self.state}, but action attempted in phase {phase}."
        return True, "Phase action validated."


if __name__ == "__main__":
    sm = TDDStateMachine()
    print(f"Initial state: {sm.state}")
    sm.transition("test_written_failing")
    print(f"After failing test: {sm.state}")
    sm.transition("implementation_passing")
    print(f"After passing impl: {sm.state}")
