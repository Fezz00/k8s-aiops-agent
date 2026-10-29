"""The agent loop: the model decides which tools to call until it can answer.

send conversation + tool menu → reply has tool_calls?
    yes → run each tool, add the results to the conversation, send again
    no  → the reply is the answer
after MAX_STEPS tool calls → one last request without tools, so the model has to answer
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from aiops import config, llm, prompts
from aiops.tools import registry


@dataclass
class Step:
    tool: str
    arguments: dict | str
    result: str


@dataclass
class Run:
    answer: str
    steps: list[Step] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)  # the whole conversation, for debugging and the eval
    hit_step_limit: bool = False


def run(question: str, max_steps: int | None = None, on_step: Callable[[Step], None] | None = None) -> Run:
    """Answer a question about the cluster. on_step is called after every tool call (the CLI prints it)."""
    max_steps = max_steps or config.MAX_STEPS
    messages = [
        {"role": "system", "content": prompts.SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    steps: list[Step] = []

    while len(steps) < max_steps:
        reply = llm.chat(messages, registry.TOOLS)
        messages.append(reply)
        tool_calls = reply.get("tool_calls")
        if not tool_calls:
            return Run(reply.get("content", ""), steps, messages)

        for call in tool_calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", {})
            step = Step(name, arguments, registry.run_tool(name, arguments))
            steps.append(step)
            if on_step:
                on_step(step)
            messages.append({"role": "tool", "tool_name": name, "content": step.result})

    messages.append({"role": "user", "content": prompts.STEP_LIMIT_REACHED})
    reply = llm.chat(messages)  # no tools offered, so the reply is text
    messages.append(reply)
    return Run(reply.get("content", ""), steps, messages, hit_step_limit=True)
