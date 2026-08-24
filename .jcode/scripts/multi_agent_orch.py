#!/usr/bin/env python3
"""
jcode Skill Runner - 多 Agent 编排器

将 examples/multi-agent-orch 重构为 JCode 技能，集成到 hooks 流程中。

用法:
    python .jcode/scripts/multi_agent_orch.py run --request "<用户需求>"
    python .jcode/scripts/multi_agent_orch.py run --request "<需求>" --mode waterfall --max-iterations 3
    python .jcode/scripts/multi_agent_orch.py demo
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from _common import print_check, print_section

# ============================================================================
# Protocol 定义 (从 examples/multi-agent-orch 迁移)
# ============================================================================


class MessageRole(Enum):
    USER = "user"
    PM = "PM"
    ARCHITECT = "Architect"
    CODER = "Coder"
    REVIEWER = "Reviewer"


@dataclass(frozen=True)
class Message:
    role: MessageRole
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentResponse:
    text: str
    passed: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class Agent(Protocol):
    @property
    def role(self) -> MessageRole: ...

    def run(self, history: list[Message]) -> AgentResponse: ...


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class AgentConfig:
    role: str
    model: str = "mock"
    temperature: float = 0.0
    max_tokens: int = 2000


@dataclass
class WorkflowConfig:
    max_review_iterations: int = 3
    fail_fast: bool = True


# ============================================================================
# Errors
# ============================================================================


class AgentError(Exception):
    def __init__(self, message: str, agent_role: str = "", cause: Exception | None = None) -> None:
        super().__init__(message)
        self.agent_role = agent_role
        self.cause = cause


class AgentFailureError(AgentError):
    pass


class MaxIterationsError(AgentError):
    def __init__(self, message: str, iterations: int) -> None:
        super().__init__(message)
        self.iterations = iterations


# ============================================================================
# Mock LLM
# ============================================================================


class MockLLM:
    """无外部依赖的模拟 LLM，用于演示和测试"""

    def generate(self, role: str, prompt: str) -> str:
        if role == "PM":
            return (
                f"[PRD] 项目需求: {prompt}\n"
                "- 目标: 创建一个功能完整的工具\n"
                "- 需求: 输入金额、选择货币、输出转换值\n"
                "- 成功标准: 准确性和简洁性"
            )
        if role == "Architect":
            return (
                f"[架构设计] 基于 PRD: {prompt}\n"
                "- 组件: CurrencyConverter 类\n"
                "- 方法: convert(amount, from_curr, to_curr)\n"
                "- API: JSON 接口 { 'amount': float, 'from': str, 'to': str } -> { 'result': float }"
            )
        if role == "Coder":
            if "FIX" in prompt:
                return (
                    "def convert(amount, from_curr, to_curr):\n"
                    "    # 修正: 增加错误处理\n"
                    "    try:\n"
                    "        rate = 1.1\n"
                    "        return amount * rate\n"
                    "    except Exception as e:\n"
                    "        return str(e)"
                )
            return "def convert(amount, from_curr, to_curr):\n    rate = 1.1\n    return amount * rate"
        if role == "Reviewer":
            if "error handling" in prompt or "错误处理" in prompt:
                return "PASS: 代码看起来不错。"
            return "FAIL: 缺少对无效输入的错误处理。"
        return "我不知道如何处理这个。"


# ============================================================================
# Base Agent
# ============================================================================


class BaseAgent:
    _role: MessageRole

    def __init__(self, config: AgentConfig | None = None, llm: MockLLM | None = None) -> None:
        self._config = config or AgentConfig(role=self._role.value)
        self._llm = llm or MockLLM()

    @property
    def role(self) -> MessageRole:
        return self._role

    @property
    def config(self) -> AgentConfig:
        return self._config

    def run(self, history: list[Message]) -> AgentResponse:
        try:
            return self._generate(history)
        except AgentFailureError:
            raise
        except Exception as exc:
            raise AgentFailureError(
                f"Agent {self._role.value} failed: {exc}",
                agent_role=self._role.value,
                cause=exc,
            ) from exc

    def _generate(self, history: list[Message]) -> AgentResponse:
        raise NotImplementedError


class PMAgent(BaseAgent):
    _role = MessageRole.PM

    def _generate(self, history: list[Message]) -> AgentResponse:
        prompt = history[-1].content if history else ""
        text = self._llm.generate("PM", prompt)
        return AgentResponse(text=text, metadata={"stage": "prd"})


class ArchitectAgent(BaseAgent):
    _role = MessageRole.ARCHITECT

    def _generate(self, history: list[Message]) -> AgentResponse:
        prompt = "\n".join(m.content for m in history)
        text = self._llm.generate("Architect", prompt)
        return AgentResponse(text=text, metadata={"stage": "design"})


class CoderAgent(BaseAgent):
    _role = MessageRole.CODER

    def _generate(self, history: list[Message]) -> AgentResponse:
        prompt = "\n".join(m.content for m in history)
        text = self._llm.generate("Coder", prompt)
        return AgentResponse(text=text, metadata={"stage": "code"})


class ReviewerAgent(BaseAgent):
    _role = MessageRole.REVIEWER

    def _generate(self, history: list[Message]) -> AgentResponse:
        prompt = "\n".join(m.content for m in history)
        text = self._llm.generate("Reviewer", prompt)
        passed = text.strip().startswith("PASS")
        return AgentResponse(text=text, passed=passed, metadata={"stage": "review"})


# ============================================================================
# Orchestrators
# ============================================================================


@dataclass
class WorkflowResult:
    history: list[Message] = field(default_factory=list)
    iterations: int = 0
    success: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "history": [{"role": m.role.value, "content": m.content, "metadata": m.metadata} for m in self.history],
            "iterations": self.iterations,
            "success": self.success,
            "error": self.error,
        }


class WaterfallOrchestrator:
    def __init__(
        self,
        agents: dict[MessageRole, Agent],
        config: WorkflowConfig | None = None,
    ) -> None:
        self._agents = agents
        self._config = config or WorkflowConfig()

    def execute(self, user_request: str) -> WorkflowResult:
        history: list[Message] = [Message(role=MessageRole.USER, content=user_request)]
        self._run_phase_pm(history)
        self._run_phase_architect(history)
        return self._run_coder_reviewer_loop(history)

    def _run_phase_pm(self, history: list[Message]) -> None:
        prd_response = self._run_agent(MessageRole.PM, history)
        history.append(Message(role=MessageRole.PM, content=prd_response.text))
        print_check("PM (产品经理) 完成 PRD", True)

    def _run_phase_architect(self, history: list[Message]) -> None:
        design_response = self._run_agent(MessageRole.ARCHITECT, history)
        history.append(Message(role=MessageRole.ARCHITECT, content=design_response.text))
        print_check("Architect (架构师) 完成设计", True)

    def _run_coder_reviewer_loop(self, history: list[Message]) -> WorkflowResult:
        iterations = 0
        max_iter = self._config.max_review_iterations

        while iterations < max_iter:
            iterations += 1
            print_section(f"Coder-Reviewer 迭代 {iterations}/{max_iter}")

            # Coder
            coder_response = self._run_agent(MessageRole.CODER, history)
            history.append(Message(role=MessageRole.CODER, content=coder_response.text))
            print_check(f"Coder 完成 (迭代 {iterations})", True)

            # Reviewer
            reviewer_response = self._run_agent(MessageRole.REVIEWER, history)
            history.append(Message(role=MessageRole.REVIEWER, content=reviewer_response.text))
            print_check(f"Reviewer 审查: {'通过' if reviewer_response.passed else '未通过'}", reviewer_response.passed)

            if reviewer_response.passed:
                return WorkflowResult(
                    history=history,
                    iterations=iterations,
                    success=True,
                )

            # Feed back "FIX: <feedback>" for next iteration
            fix_msg = f"FIX: {reviewer_response.text}"
            history.append(
                Message(
                    role=MessageRole.USER,
                    content=fix_msg,
                    metadata={"purpose": "fix_request"},
                )
            )

        # Exhausted iterations
        error_msg = f"达到最大迭代次数 ({max_iter}) 仍未通过审查"
        if self._config.fail_fast:
            raise MaxIterationsError(error_msg, iterations=iterations)
        return WorkflowResult(
            history=history,
            iterations=iterations,
            success=False,
            error=error_msg,
        )

    def _run_agent(self, role: MessageRole, history: list[Message]) -> AgentResponse:
        agent = self._agents.get(role)
        if agent is None:
            msg = f"未注册 Agent: {role.value}"
            if self._config.fail_fast:
                raise AgentFailureError(msg, agent_role=role.value)
            return AgentResponse(text=f"[SKIPPED] {msg}", metadata={"skipped": "true"})
        return agent.run(history)


# ============================================================================
# Fan-out Orchestrator (并行执行示例)
# ============================================================================


class FanOutOrchestrator:
    """并行执行多个 Agent，然后汇总"""

    def __init__(self, agents: dict[MessageRole, Agent]) -> None:
        self._agents = agents

    def execute(self, user_request: str) -> WorkflowResult:
        history: list[Message] = [Message(role=MessageRole.USER, content=user_request)]

        # 并行运行 PM 和 Architect（模拟）
        pm_response = self._run_agent(MessageRole.PM, history)
        history.append(Message(role=MessageRole.PM, content=pm_response.text))

        arch_response = self._run_agent(MessageRole.ARCHITECT, history)
        history.append(Message(role=MessageRole.ARCHITECT, content=arch_response.text))

        # Coder 和 Reviewer 可以并行验证不同方面
        coder_response = self._run_agent(MessageRole.CODER, history)
        history.append(Message(role=MessageRole.CODER, content=coder_response.text))

        reviewer_response = self._run_agent(MessageRole.REVIEWER, history)
        history.append(Message(role=MessageRole.REVIEWER, content=reviewer_response.text))

        return WorkflowResult(
            history=history,
            iterations=1,
            success=reviewer_response.passed,
            error=None if reviewer_response.passed else "并行验证未通过",
        )

    def _run_agent(self, role: MessageRole, history: list[Message]) -> AgentResponse:
        agent = self._agents.get(role)
        if agent is None:
            return AgentResponse(text=f"[SKIPPED] No agent for {role.value}", metadata={"skipped": "true"})
        return agent.run(history)


# ============================================================================
# CLI Entry Points
# ============================================================================


def create_agents(llm: MockLLM | None = None) -> dict[MessageRole, Agent]:
    return {
        MessageRole.PM: PMAgent(llm=llm),
        MessageRole.ARCHITECT: ArchitectAgent(llm=llm),
        MessageRole.CODER: CoderAgent(llm=llm),
        MessageRole.REVIEWER: ReviewerAgent(llm=llm),
    }


def run_workflow(
    request: str,
    mode: str = "waterfall",
    max_iterations: int = 3,
    output_json: str | None = None,
) -> int:
    print_section("多 Agent 编排器")

    print_check(f"用户需求: {request}", True)
    print_check(f"编排模式: {mode}", True)
    print_check(f"最大迭代: {max_iterations}", True)

    llm = MockLLM()
    agents = create_agents(llm)

    orchestrator: Any
    if mode == "waterfall":
        config = WorkflowConfig(max_review_iterations=max_iterations, fail_fast=False)
        orchestrator = WaterfallOrchestrator(agents, config)
    elif mode == "fanout":
        orchestrator = FanOutOrchestrator(agents)
    else:
        print_check(f"未知模式: {mode}", False)
        return 1

    try:
        result = orchestrator.execute(request)
    except MaxIterationsError:
        print_check("达到最大迭代次数", False)
        return 1
    except Exception as e:
        print_check(f"执行失败: {e}", False)
        return 1

    # 输出结果
    print_section("执行结果")
    print_check(f"成功: {result.success}", result.success)
    print_check(f"迭代次数: {result.iterations}", True)

    if result.error:
        print(f"错误: {result.error}")

    # 显示最终代码
    for msg in reversed(result.history):
        if msg.role == MessageRole.CODER and msg.metadata.get("stage") == "code":
            print_section("最终生成代码")
            print(msg.content)
            break

    # JSON 输出
    if output_json:
        Path(output_json).write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        print_check(f"结果已写入: {output_json}", True)

    return 0 if result.success else 1


def run_demo() -> int:
    """运行内置演示"""
    print_section("多 Agent 编排器演示")

    requests = [
        "创建一个货币转换工具，支持 USD/EUR/CNY 互转",
        "创建一个待办事项管理 CLI，支持增删改查",
        "创建一个简单的计算器，支持基本四则运算",
    ]

    for i, req in enumerate(requests, 1):
        print(f"\n{'=' * 60}")
        print(f"演示 {i}: {req}")
        print("=" * 60)

        llm = MockLLM()
        agents = create_agents(llm)
        config = WorkflowConfig(max_review_iterations=2, fail_fast=False)
        orchestrator = WaterfallOrchestrator(agents, config)

        result = orchestrator.execute(req)
        status = "✅ 成功" if result.success else "❌ 失败"
        print(f"结果: {status} (迭代 {result.iterations})")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="多 Agent 编排器 - JCode 技能")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run 子命令
    run_parser = subparsers.add_parser("run", help="运行多 Agent 编排")
    run_parser.add_argument("--request", required=True, help="用户需求描述")
    run_parser.add_argument(
        "--mode", choices=["waterfall", "fanout"], default="waterfall", help="编排模式 (默认: waterfall)"
    )
    run_parser.add_argument("--max-iterations", type=int, default=3, help="最大审查迭代次数 (默认: 3)")
    run_parser.add_argument("--output-json", help="输出结果到 JSON 文件")

    # demo 子命令
    subparsers.add_parser("demo", help="运行内置演示")

    args = parser.parse_args()

    if args.command == "run":
        sys.exit(
            run_workflow(
                request=args.request,
                mode=args.mode,
                max_iterations=args.max_iterations,
                output_json=args.output_json,
            )
        )
    elif args.command == "demo":
        sys.exit(run_demo())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
